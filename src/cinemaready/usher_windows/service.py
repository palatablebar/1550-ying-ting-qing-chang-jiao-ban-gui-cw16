from .operating_ledger import operating_ledger
from collections import Counter, defaultdict
from math import exp, isfinite

from .contracts import RuleNotice, Job, Plan, Policy, RISK_CUTOFF
from .constraints import WorkOrder, apply_usher_windows


def measures(raw):
    return tuple(raw)


def signals(data, estimate, missing=()):
    absent=frozenset(missing)
    seats, filled, spill, minutes, bins, stairs = data
    hits = []
    if not absent.intersection(('filled', 'minutes')) and (minutes <= 16 and filled >= 81):
        hits.append(RuleNotice('NARROW_CLEAR_WINDOW', '两场间隔不足', hard=True))
    if not absent.intersection(('spill', 'stairs')) and (stairs > 28 and spill > 16):
        hits.append(RuleNotice('STAIR_EXTRA', '需双人清理阶梯', hard=False))
    if not absent.intersection(('filled', 'bins')) and (bins <= 3 and filled > 71):
        hits.append(RuleNotice('BAG_CAPACITY', '垃圾桶先补袋', hard=False))
    return tuple(hits)


def expected_load(measurements):
    seats, filled, spill, minutes, bins, stairs = measurements
    return 1 + int(seats >= 220) + int(spill >= 18)


def dispatch_pressure(values, estimate):
    seats, filled, spill, minutes, bins, stairs = values
    return max(0,estimate+2-minutes)/5 + spill/23


def confidence_weight(estimate, cutoff):
    shifted = (estimate - cutoff) / max(.5, abs(cutoff) * .35)
    if shifted >= 0:
        return 1 / (1 + exp(-shifted))
    bounded = exp(shifted)
    return bounded / (1 + bounded)


def recommend(assessment, attention, policy):
    raw = assessment.raw
    data = measures(raw.input_values)
    estimate = assessment.estimate
    domain_codes = signals(data, estimate, raw.missing)
    level = confidence_weight(estimate, policy.trigger)
    cost = expected_load(data)
    if not isfinite(estimate) or not 1 <= cost <= 12:
        raise ValueError('处置量不在有效范围')
    if domain_codes and domain_codes[0].hard:
        state = '暂停'
        reason = domain_codes[0].rule_id
        summary = domain_codes[0].meaning
    elif raw.key in attention or assessment.uncertain:
        state = '人工判读'
        reason = 'OUT_OF_REFERENCE' if raw.key in attention else 'INSUFFICIENT_CALIBRATION'
        summary = '分布偏移或校准量不足，需核对原始单据'
    elif domain_codes or estimate >= policy.trigger:
        state = '候选'
        reason = domain_codes[0].rule_id if domain_codes else 'ABOVE_TRIGGER'
        summary = domain_codes[0].meaning if domain_codes else '达到本班复核阈值'
    else:
        state = '观察'
        reason = 'BELOW_TRIGGER'
        summary = '保留记录并等待下一次巡查'
    return Job(raw.key, raw.cohort, round(estimate, 4), assessment.lower, assessment.upper, cost,
               state, reason, summary, round(level, 5), tuple(item.rule_id for item in domain_codes))


def allocate(assessments, attention, policy):
    selected={}
    waiting=[]
    for sample in assessments:
        signed=recommend(sample,attention,policy)
        if signed.key in selected:
            raise ValueError('处置登记号重复')
        selected[signed.key]=signed
        if signed.state=='候选':
            waiting.append(WorkOrder(signed,sample))
    allocation=Counter()
    def defer(unit, code, explanation):
        job=unit.job
        selected[job.key]=job.change('候补',code,explanation)

    def plan(unit):
        job=unit.job
        under_group=allocation[job.cohort]+job.cost<=policy.group_quota
        under_shift=allocation.total()+job.cost<=policy.capacity
        if under_group and under_shift:
            allocation[job.cohort]+=job.cost
            selected[job.key]=job.change('已分派',job.reason,job.summary)
            return True
        low_shift='本班占用上限已达'
        low_group='本区复核位已占满'
        defer(unit,'GROUP_CAP_REACHED' if under_shift else 'CAPACITY_REACHED',low_group if under_shift else low_shift)
        return False

    def rank(unit):
        data=unit.assessment.raw.input_values
        physical=dispatch_pressure(data,unit.assessment.estimate)
        category=room_timing(data)
        return (len(unit.job.rule_hits)==0,-physical,category,-unit.job.estimate,unit.job.key)
    apply_usher_windows(sorted(waiting,key=rank),plan,defer)
    if any(item.state=='候选' for item in selected.values()):
        raise ArithmeticError('存在尚未排完的作业')
    balance=policy.capacity-allocation.total()
    handoff=sorted(selected.values(),key=lambda item:(item.state!='已分派',-item.priority,item.cost,item.key))
    return Plan(tuple(handoff),policy.capacity,balance,tuple(sorted(allocation.items())))


def plan_jobs(assessments, attention, capacity, mode='balanced'):
    return allocate(assessments, frozenset(attention), Policy.select(capacity, mode))


def action_evidence(plan):
    counts = Counter(job.state for job in plan.jobs)
    status = [{'处置': state, '单量': count} for state, count in sorted(counts.items())]
    status.extend({'处置': '分区 ' + group, '额度': cost} for group, cost in plan.used_by_group)
    status += [{'处置': '剩余额度', '额度': plan.balance}]
    return status


def room_timing(raw):
    minutes = raw[3]
    return int(minutes//9)


def operating_group(assessments, progression):
    source={line.raw.key:line.raw.input_values for line in assessments}
    cells=Counter()
    for work in progression.jobs:
        if work.state != '已分派':
            continue
        band=room_timing(source[work.key])
        cells[work.cohort,band] += work.cost
    return [{ '作业区': zone, '排片窗': band, '班组用量': total } for (zone,band),total in sorted(cells.items())]
