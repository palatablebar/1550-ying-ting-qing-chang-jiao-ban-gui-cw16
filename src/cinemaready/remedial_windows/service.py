from collections import Counter
from dataclasses import replace

from ..cleanup_trend.service import predict_one
from ..hall_signature.contracts import RAW_KEYS
from ..slot_backcheck.service import check_point
from ..usher_windows.operating_ledger import backward_sweep, overlaps
from .contracts import (
    DELAYED, ON_TIME, REASON_CAPACITY_REACHED, REASON_GROUP_CAP_REACHED,
    REASON_NO_VIABLE_PLAN, REASON_SLOT_OVERLAP, PendingRemedy,
    RemedialBatch, SignedRemedy,
)
from .options import remedial_options


def base_estimate(vector, kernel, calibration):
    return check_point(predict_one(kernel, vector), calibration).estimate


def _option_rank(option):
    # 准时优先；同为准时或同为延后时，估计上界最稳、措施用量最省、工位最少者优先
    return (0 if option.on_time else 1,
            option.upper if option.upper is not None else float('inf'),
            option.work_units, option.cost, option.kind, option.action)


def plan_remedial_windows(vectors, base_states, base_balance, group_quota,
                          reference, kernel, calibration, *, used_by_group=(),
                          base_costs=()):
    """对倒排赶不上开门的当班场次签发补救排窗。

    vectors: 当班全部 FeatureVector
    base_states: {单号: 常规处置状态}，暂停/人工判读单不参与补救
    base_balance: 常规分派后剩余工位（补救也用本班工位）
    group_quota: 单作业区工位限额（与常规派单同一 Policy）
    used_by_group: 常规分派已占用的分区工位
    base_costs: {单号: 常规工位成本}；已分派单转补救时先释放原占用再重计
    """
    normal_cost = dict(base_costs)
    by_key = {vector.key: vector for vector in vectors}
    candidates = []
    # 常规"已分派"窗口先占用同厅相对时轴，补救窗口须与其他场次的窗口错开。
    reserved = []
    for vector in vectors:
        state = base_states.get(vector.key)
        slot = backward_sweep({
            'measurements': dict(zip(RAW_KEYS, vector.input_values, strict=True)),
            'estimate': base_estimate(vector, kernel, calibration),
        })
        if state == '已分派':
            reserved.append((vector.key, vector.cohort, slot))
        # 暂停/人工判读单不参与补救；其余倒排为负的场次进入候选
        if state not in ('暂停', '人工判读') and slot.start < 0:
            candidates.append(vector.key)

    group_spent = Counter(dict(used_by_group))
    shift_used = sum(group_spent.values())
    capacity = shift_used + base_balance
    signed = []
    pending = []

    for key in sorted(candidates, key=lambda item: (by_key[item].input_values[3], item)):
        vector = by_key[key]
        options = remedial_options(vector, reference, kernel, calibration)
        viable = [item for item in options if item.viable]
        # 优先保住原开门时刻：先完整尝试准时方案
        ordered_on_time = sorted((item for item in viable if item.on_time),
                                 key=_option_rank)
        # 准点方案过不了验收或工位不够，再签排得下的延后方案
        ordered_delayed = sorted((item for item in viable if not item.on_time),
                                 key=_option_rank)

        chosen_schedule = None
        chosen_option = None
        chosen_slot = None
        blocked = Counter()
        # 已分派单转补救：先把它原本占用的工位释放回余额，按补救成本重新核对
        released = normal_cost.get(key, 0) if base_states.get(key) == '已分派' else 0
        for schedule, tier in ((ON_TIME, ordered_on_time), (DELAYED, ordered_delayed)):
            for option in tier:
                slot, reason = _admit(option, vector, reserved, group_spent,
                                      shift_used, capacity, group_quota, released)
                if slot is None:
                    blocked[reason] += 1
                    continue
                chosen_schedule, chosen_option, chosen_slot = schedule, option, slot
                break
            if chosen_option is not None:
                break

        if chosen_option is None:
            reason, explanation = _pending_reason(options, viable, blocked)
            pending.append(PendingRemedy(key, vector.cohort, reason, explanation,
                                         len(options) - len(viable), len(viable)))
            continue

        # 释放原占用、计入补救成本，保持本班工位总量守恒
        shift_used += chosen_option.cost - released
        group_spent[vector.cohort] += chosen_option.cost - released
        # 已分派候选转补救：用补救窗口替换它在同厅时轴上的原窗口，
        # 避免已被取代的原窗口错误阻挡后续场次
        if released:
            reserved = [(ticket, zone, slot) for (ticket, zone, slot) in reserved
                        if ticket != key]
        reserved.append((key, vector.cohort, chosen_slot))
        signed.append(SignedRemedy(
            ticket=key, cohort=vector.cohort, kind=chosen_option.kind,
            action=chosen_option.action, schedule=chosen_schedule,
            delay=chosen_option.delay, cost=chosen_option.cost,
            work_units=chosen_option.work_units, estimate=chosen_option.estimate,
            upper=chosen_option.upper, slot_start=chosen_option.slot_start,
            door_finish=chosen_option.door_finish, changes=chosen_option.changes,
            measured=tuple(field for field, _, _ in chosen_option.changes),
        ))

    # 补救净增工位 = 补救成本合计 − 已分派候选被释放的原占用
    gross = sum(item.cost for item in signed)
    released_total = sum(normal_cost.get(item.ticket, 0)
                         for item in signed
                         if base_states.get(item.ticket) == '已分派')
    remedial_used = gross - released_total
    return RemedialBatch(
        signed=tuple(signed), pending=tuple(pending),
        candidates=tuple(sorted(candidates)), capacity=capacity,
        base_balance=base_balance, remedial_used=remedial_used,
        final_balance=base_balance - remedial_used,
        used_by_group=tuple(sorted(group_spent.items())),
    )


def _slot_for(option):
    slot = backward_sweep({
        'measurements': dict(zip(RAW_KEYS, option.adjusted_values, strict=True)),
        'estimate': option.estimate,
    })
    if option.delay:
        # 延后开门：整个相对时轴顺延，开门留存时点与最晚开工同步后移
        slot = replace(slot, start=slot.start + option.delay,
                       finish=slot.finish + option.delay)
    return slot


def _admit(option, vector, reserved, group_spent, shift_used, capacity, group_quota,
           released=0):
    """工位余额与同厅交叠核对；排不下返回 (None, 原因码)。

    released 为本单原本占用、转补救时释放回余额的工位数。
    """
    net_group = group_spent[vector.cohort] - released
    net_shift = shift_used - released
    if net_group + option.cost > group_quota:
        return None, REASON_GROUP_CAP_REACHED
    if net_shift + option.cost > capacity:
        return None, REASON_CAPACITY_REACHED
    slot = _slot_for(option)
    if any(ticket != vector.key and zone == vector.cohort and overlaps(slot, prior)
           for ticket, zone, prior in reserved):
        return None, REASON_SLOT_OVERLAP
    return slot, None


def _pending_reason(options, viable, blocked):
    if not viable:
        codes = Counter(code for item in options for code in item.excluded)
        reason = codes.most_common(1)[0][0] if codes else REASON_NO_VIABLE_PLAN
        return reason, '全部补救方案未通过开门验收，留待协调'
    # 存在可验收方案但排不下：以最主要的工位/交叠约束登记原因
    reason = blocked.most_common(1)[0][0]
    explanation = {'REMEDIAL_CAPACITY_REACHED': '本班剩余工位不足，留待协调',
                   'REMEDIAL_GROUP_CAP_REACHED': '本区工位限额已达，留待协调',
                   'REMEDIAL_SLOT_OVERLAP': '同厅保洁窗口交叠，留待协调'}[reason]
    return reason, explanation
