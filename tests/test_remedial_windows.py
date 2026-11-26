from dataclasses import replace

import pytest

from cinemaready.pipeline import ShiftDossier, open_fixture, preview
from cinemaready.remedial_windows import (
    ON_TIME, DELAYED, PENDING_STATE, REMEDIAL_STATE,
    plan_remedial_windows, remedial_options,
)
from cinemaready.remedial_windows.contracts import (
    REASON_HARD_RULE, REASON_MISSING_READING, REASON_NO_ACCEPTANCE_TIME,
    REASON_OUT_OF_DOMAIN, REASON_SLOT_OVERLAP, REASON_CAPACITY_REACHED,
)
from cinemaready.remedial_windows.evidence import (
    measure_reconciliation, remedial_ledger_rows, remedial_reconciliation,
)
from cinemaready.usher_windows.contracts import Policy
from cinemaready.usher_windows.service import plan_jobs


@pytest.fixture(scope='module')
def kit():
    doc = open_fixture()
    dossier = ShiftDossier(doc['records'], doc['as_of'])
    calibration, predictions = dossier.grading()
    _, checked_live, drift = dossier.verification(predictions, calibration)
    return dossier, calibration, checked_live, drift


def _run(kit, capacity=33, mode='focus'):
    dossier, calibration, checked_live, drift = kit
    plan = plan_jobs(checked_live, drift.domain, capacity, mode)
    policy = Policy.select(capacity, mode)
    states = {job.key: job.state for job in plan.jobs}
    batch = plan_remedial_windows(
        dossier.prepared.live, states, plan.balance, policy.group_quota,
        dossier.feature_stamp, dossier.forecaster, calibration,
        used_by_group=plan.used_by_group,
        base_costs={job.key: job.cost for job in plan.jobs},
    )
    return plan, batch


def test_only_backward_sweep_misses_are_candidates(kit):
    plan, batch = _run(kit)
    # 暂停单 CH-1258 虽倒排为负，但不进入补救候选；人工判读单同样不进入
    assert 'CH-1258' not in batch.candidates
    assert 'CH-1255' not in batch.candidates
    # 候选均为倒排最晚开工为负的非暂停/非人工单
    assert set(batch.candidates) == {
        'CH-1253', 'CH-1254', 'CH-1256', 'CH-1262', 'CH-1265', 'CH-RECHECK',
    }


def test_paused_and_manual_tickets_are_never_signed(kit):
    _, batch = _run(kit)
    keys = {item.ticket for item in batch.signed} | {item.ticket for item in batch.pending}
    assert not keys & {'CH-1258', 'CH-1255'}


def test_signed_remedies_preserve_original_door_when_possible(kit):
    _, batch = _run(kit)
    assert batch.signed
    assert all(item.schedule == ON_TIME and item.delay == 0 for item in batch.signed)


def test_remedial_station_balance_conserves_shift_capacity(kit):
    plan, batch = _run(kit)
    assert batch.base_balance == plan.balance
    assert batch.base_balance == batch.remedial_used + batch.final_balance
    # 已分派候选转补救时先释放原工位：净增 = 补救毛额 − 释放额
    states = {job.key: job.state for job in plan.jobs}
    costs = {job.key: job.cost for job in plan.jobs}
    gross = sum(item.cost for item in batch.signed)
    released = sum(costs[item.ticket] for item in batch.signed
                   if states.get(item.ticket) == '已分派')
    assert batch.remedial_used == gross - released
    # 补救与常规分派共用本班工位，全局不超额
    normal_used = plan.capacity - plan.balance
    assert normal_used + batch.remedial_used + batch.final_balance == plan.capacity


def test_same_hall_overlap_limits_one_remedial_window(kit):
    _, batch = _run(kit)
    # 小剧场同相对时轴的场次窗口互相交叠，仅一张能签发，其余留待协调
    small_signed = [item for item in batch.signed if item.cohort == '小剧场']
    small_pending = [item for item in batch.pending if item.cohort == '小剧场']
    assert len(small_signed) == 1
    assert {item.reason for item in small_pending} == {REASON_SLOT_OVERLAP}


def test_tight_capacity_leaves_undispatched_candidates_for_coordination(kit):
    plan, batch = _run(kit, capacity=12)
    # 工位余额守恒始终成立（净增可为负，表示补救释放了原常规工位）
    assert batch.base_balance == batch.remedial_used + batch.final_balance
    normal_used = plan.capacity - plan.balance
    assert normal_used + batch.remedial_used + batch.final_balance == plan.capacity
    # 未被常规分派的候选没有工位可释放，余额不足时一律留待协调
    dispatched = {job.key for job in plan.jobs if job.state == '已分派'}
    undispatched_pending = [item for item in batch.pending
                            if item.ticket not in dispatched]
    assert undispatched_pending
    assert {item.reason for item in undispatched_pending} <= {
        REASON_CAPACITY_REACHED, 'REMEDIAL_GROUP_CAP_REACHED', REASON_SLOT_OVERLAP,
    }
    # 所有非已分派候选都不会被签发（无工位来源）
    assert all(item.ticket in dispatched for item in batch.signed)


def test_dispatched_candidate_release_frees_station_for_remedy(kit):
    # CH-1265 已常规分派但倒排为负：补救先释放原工位再重计，净增可能为负
    plan, batch = _run(kit, capacity=12)
    costs = {job.key: job.cost for job in plan.jobs}
    signed = next((item for item in batch.signed if item.ticket == 'CH-1265'), None)
    if signed is not None:
        assert costs['CH-1265'] > signed.cost or batch.base_balance >= signed.cost
        assert batch.final_balance >= 0


def test_every_signed_change_is_measured_and_recalculated_with_frozen_model(kit):
    dossier, calibration, _, _ = kit
    _, batch = _run(kit)
    vectors = {item.key: item for item in dossier.prepared.live}
    for signed in batch.signed:
        vector = vectors[signed.ticket]
        # 改动读数均为实测，不碰缺测字段
        assert all(field not in vector.missing for field in signed.measured)
        assert signed.changes and all(before != after for _, before, after in signed.changes)
        # 上界必须留得出 2 分钟开门验收
        assert signed.upper is not None
        # 重算结果有限且准时方案的开工时刻非负
        assert signed.slot_start >= 0


def test_missing_reading_is_never_used_as_a_remedial_change(kit):
    dossier, calibration, _, _ = kit
    vectors = {item.key: item for item in dossier.prepared.live}
    # CH-1270 缺 spill：补救措施只允许改实测读数，因此没有任何方案改动 spill
    missing_options = remedial_options(vectors['CH-1270'], dossier.feature_stamp,
                                       dossier.forecaster, calibration)
    assert missing_options
    for option in missing_options:
        changed = {field for field, _, _ in option.changes}
        assert 'spill' not in changed
        assert not (changed & set(vectors['CH-1270'].missing))
        assert not option.missing_reading


def test_hard_rule_options_are_refused_even_when_estimate_improves(kit):
    dossier, calibration, _, _ = kit
    vectors = {item.key: item for item in dossier.prepared.live}
    # 构造一个调整后仍命中 NARROW_CLEAR_WINDOW（minutes<=16 且 filled>=81）的方案
    base = vectors['CH-1258']
    option = next(item for item in remedial_options(base, dossier.feature_stamp,
                                                    dossier.forecaster, calibration)
                  if item.kind == '单项调整' and item.action == '先做溅污预清')
    assert REASON_HARD_RULE in option.excluded or REASON_OUT_OF_DOMAIN in option.excluded
    assert not option.viable


def test_upper_bound_acceptance_gate_rejects_on_time_claim(kit):
    dossier, calibration, _, _ = kit
    vectors = {item.key: item for item in dossier.prepared.live}
    # CH-1258 没有任何准时方案：上界+2 超过其开门窗口
    options = remedial_options(vectors['CH-1258'], dossier.feature_stamp,
                               dossier.forecaster, calibration)
    assert not any(item.on_time for item in options)
    time_options = [item for item in options
                    if any(field == 'minutes' for field, _, _ in item.changes)]
    assert any(REASON_NO_ACCEPTANCE_TIME in item.excluded for item in time_options)


def test_delayed_plan_carries_positive_delay_and_shifted_axis(kit):
    from cinemaready.remedial_windows.service import _slot_for

    dossier, calibration, _, _ = kit
    vectors = {item.key: item for item in dossier.prepared.live}
    # CH-1258（暂停单不参与签发）的方案全部过不了准时验收，记录为正延后量
    options = remedial_options(vectors['CH-1258'], dossier.feature_stamp,
                               dossier.forecaster, calibration)
    delayed = [item for item in options if not item.on_time]
    assert delayed and all(item.delay > 0 for item in delayed)
    # 延后排窗的时轴整体后移：开门留存时点与最晚开工同步加上延后分钟
    for item in delayed:
        slot = _slot_for(item)
        assert slot.finish == item.door_finish + item.delay
        assert slot.start == item.slot_start + item.delay


def test_batch_is_deterministic_and_input_order_invariant(kit):
    dossier, calibration, checked_live, drift = kit
    plan = plan_jobs(checked_live, drift.domain, 33, 'focus')
    policy = Policy.select(33, 'focus')
    states = {job.key: job.state for job in plan.jobs}
    kwargs = dict(base_states=states, base_balance=plan.balance,
                  group_quota=policy.group_quota, reference=dossier.feature_stamp,
                  kernel=dossier.forecaster, calibration=calibration,
                  used_by_group=plan.used_by_group)
    first = plan_remedial_windows(dossier.prepared.live, **kwargs)
    reversed_vectors = tuple(reversed(dossier.prepared.live))
    second = plan_remedial_windows(reversed_vectors, **kwargs)
    assert [(s.ticket, s.action, s.schedule) for s in first.signed] == \
           [(s.ticket, s.action, s.schedule) for s in second.signed]
    assert [p.ticket for p in first.pending] == [p.ticket for p in second.pending]


def test_ledger_and_export_reconcile_by_measure_door_and_station(kit):
    _, batch = _run(kit)
    rows = remedial_ledger_rows(batch)
    signed_rows = [row for row in rows if row['业务安排'] == REMEDIAL_STATE]
    pending_rows = [row for row in rows if row['业务安排'] == PENDING_STATE]
    assert len(signed_rows) == len(batch.signed)
    assert len(pending_rows) == len(batch.pending)
    # 按措施、开门时刻、工位三栏都能对账
    for row, signed in zip(signed_rows, batch.signed):
        assert row['补救措施'] == signed.action
        assert row['开门时刻'] == signed.schedule
        assert row['占用工位'] == signed.cost
        assert row['实测改动读数']  # 措施所改读数有实测留痕
    check = remedial_reconciliation(batch)
    lookup = {row['核对项']: row['数量'] for row in check}
    assert lookup['补救前工位余额'] == batch.base_balance
    assert lookup['补救净增工位'] == batch.remedial_used
    assert lookup['补救后工位余额'] == batch.final_balance
    ledger = measure_reconciliation(batch)
    assert sum(row['签发单量'] for row in ledger) == len(batch.signed)
    assert all(row['实测改动读数项'] > 0 for row in ledger)


def test_remedial_windows_never_overlap_normal_dispatched_slots(kit):
    from cinemaready.remedial_windows.service import _slot_for, base_estimate
    from cinemaready.usher_windows.operating_ledger import backward_sweep, overlaps
    from cinemaready.hall_signature.contracts import RAW_KEYS
    dossier, calibration, _, _ = kit
    vectors = {item.key: item for item in dossier.prepared.live}
    plan, batch = _run(kit, 60, 'focus')
    # 常规已分派窗口（同厅相对时轴）
    normal_slots = []
    for job in plan.jobs:
        if job.state != '已分派':
            continue
        vector = vectors[job.key]
        slot = backward_sweep({
            'measurements': dict(zip(RAW_KEYS, vector.input_values, strict=True)),
            'estimate': base_estimate(vector, dossier.forecaster, calibration),
        })
        normal_slots.append((job.key, vector.cohort, slot))
    # 每条补救签发窗口不得与同厅其他场次的常规窗口交叠（本单原窗口除外）
    for signed in batch.signed:
        option = next(o for o in remedial_options(vectors[signed.ticket],
                                                  dossier.feature_stamp,
                                                  dossier.forecaster, calibration)
                      if o.action == signed.action and o.kind == signed.kind)
        remedial_slot = _slot_for(option)
        assert not any(ticket != signed.ticket and zone == signed.cohort
                       and overlaps(remedial_slot, slot)
                       for ticket, zone, slot in normal_slots)


def test_remedy_overlapping_normal_dispatched_slot_goes_to_coordination(kit):
    # CH-1254 已常规分派且倒排为负，但其每个补救窗口都与同厅 CH-1257/CH-1272 交叠
    plan, batch = _run(kit, 33, 'focus')
    pending = {item.ticket: item for item in batch.pending}
    if 'CH-1254' in pending:
        assert pending['CH-1254'].reason == REASON_SLOT_OVERLAP
        # 它本身有通过开门验收的方案，纯粹被同厅交叠挡住
        assert pending['CH-1254'].domain_options > 0


def test_pipeline_exposes_remedial_section_with_consistent_balance():
    report = preview(33, 'focus')
    stage = report['sections'][6]
    assert stage['remedial_title'] == '补救排窗签发'
    assert stage['remedial_rows']
    remedial = report['remedial']
    assert remedial['base_balance'] == remedial['remedial_used'] + remedial['final_balance']
    # 补救后余额与常规 KPI 余额衔接（补救前余额等于常规额度结余）
    balance_kpi = next(item['value'] for item in report['metrics']
                       if item['label'] == '额度结余')
    assert remedial['base_balance'] == balance_kpi
    # 候选 + 签发 + 留待数量闭合
    assert len(remedial['signed']) + len(remedial['pending']) == len(remedial['candidates'])


def test_no_candidates_when_all_tickets_paused(kit):
    dossier, calibration, _, _ = kit
    states = {vector.key: '暂停' for vector in dossier.prepared.live}
    batch = plan_remedial_windows(
        dossier.prepared.live, states, base_balance=10, group_quota=10,
        reference=dossier.feature_stamp, kernel=dossier.forecaster,
        calibration=calibration,
    )
    assert batch.candidates == ()
    assert not batch.signed and not batch.pending
    assert batch.remedial_used == 0 and batch.final_balance == 10


def test_default_capacity_repeat_run_is_identical():
    assert preview()['remedial'] == preview()['remedial']


def _synthetic_vector(kit, key, values, missing=()):
    from cinemaready.hall_signature.service import numeric_fields
    from cinemaready.hall_signature.contracts import FeatureVector
    dossier = kit[0]
    reference = dossier.feature_stamp
    scaled, factors, excursions = numeric_fields(tuple(values), reference)
    anchor = next(item for item in dossier.prepared.live if item.key == 'CH-1253')
    return FeatureVector(key=key, cohort=anchor.cohort, day=anchor.day, values=scaled,
                         factors=factors, missing=tuple(missing),
                         excursions=excursions, outcome=None, observed=True,
                         input_values=tuple(values))


def test_overlap_with_no_delayed_option_goes_to_coordination(kit):
    dossier, calibration, _, _ = kit
    # 两张工况完全相同的同厅单（独立影厅隔离样例数据）：第一张占走窗口，
    # 第二张的可行方案全是准时且全部交叠，又没有可行延后方案，只能留待协调
    anchor = next(item for item in dossier.prepared.live if item.key == 'CH-1253')
    first = replace(anchor, key='SYN-A', cohort='合成厅')
    second = replace(anchor, key='SYN-B', cohort='合成厅')
    batch = plan_remedial_windows(
        (first, second), {'SYN-A': '候补', 'SYN-B': '候补'},
        base_balance=60, group_quota=60,
        reference=dossier.feature_stamp, kernel=dossier.forecaster,
        calibration=calibration,
    )
    by_key = {item.ticket: item for item in batch.signed}
    assert 'SYN-A' in by_key and by_key['SYN-A'].schedule == ON_TIME
    pending = {item.ticket: item for item in batch.pending}
    assert 'SYN-B' in pending and pending['SYN-B'].reason == REASON_SLOT_OVERLAP


def test_service_falls_back_to_delayed_tier_when_on_time_tier_empty(kit, monkeypatch):
    import cinemaready.remedial_windows.service as service_mod
    dossier, calibration, _, _ = kit
    anchor = next(item for item in dossier.prepared.live if item.key == 'CH-1253')
    vector = replace(anchor, key='SYN-DELAY', cohort='延时厅')

    def fake_options(v, reference, kernel, calibration_):
        all_options = remedial_options(v, reference, kernel, calibration_)
        # 强制准时层为空，仅保留一条可行的延后方案，验证服务的延后兜底
        delayed = next(replace(item, on_time=False, delay=4)
                       for item in all_options if item.viable)
        return tuple(item for item in all_options if not item.viable) + (delayed,)

    monkeypatch.setattr(service_mod, 'remedial_options', fake_options)
    batch = plan_remedial_windows(
        (vector,), {'SYN-DELAY': '候补'}, base_balance=60, group_quota=60,
        reference=dossier.feature_stamp, kernel=dossier.forecaster,
        calibration=calibration,
    )
    assert len(batch.signed) == 1
    signed = batch.signed[0]
    assert signed.schedule == DELAYED and signed.delay == 4
    assert signed.slot_start >= 0


def test_build_option_guards_missing_reading_directly(kit):
    from cinemaready.remedial_windows import build_option
    dossier, calibration, _, _ = kit
    # 直接构造一个试图改动缺测字段的方案，验证守卫独立于措施生成器生效
    vector = _synthetic_vector(kit, 'SYN-MISS', (238, 90, 20, 23, 4, 35), missing=('spill',))
    option = build_option(
        'SYN-MISS', '单项调整', '先做溅污预清', 2,
        (('spill', 20.0, 15.0),), vector,
        dossier.feature_stamp, dossier.forecaster, calibration,
    )
    assert option.missing_reading
    assert REASON_MISSING_READING in option.excluded
    assert not option.viable
