from collections import defaultdict
from math import fsum
from statistics import median


def groups_for_slot_backcheck(raw):
    seats, filled, spill, minutes, bins, stairs = raw
    if minutes<=20:
        yield '排片紧邻'
    if filled>=78:
        yield '高上座'
    if spill>=14:
        yield '溅污多'
    if stairs>=25:
        yield '三层以上台阶'
    if bins<=4:
        yield '桶位少'

def window_losses(view, line):
    actual = view.raw.outcome
    if not view.raw.observed or actual is None:
        return None
    calendar = view.estimate-actual
    urgent = actual >= line
    accounted = view.estimate >= line
    overrun = actual-line if urgent and not accounted else None
    lower = view.lower
    upper = view.upper
    missing_band = lower is None or upper is None
    breach = None if missing_band else actual < lower or actual > upper
    return calendar, overrun, breach


def replay_slices(points, threshold, *, risk_model=False):
    eligible = defaultdict(list)
    for judgment in points:
        loss = window_losses(judgment,threshold)
        if loss is None:
            continue
        for work_area in groups_for_slot_backcheck(judgment.raw.input_values):
            eligible[work_area].append(loss)
    table = []
    for title in ('排片紧邻', '高上座', '溅污多', '三层以上台阶', '桶位少'):
        decisions = eligible[title]
        if not decisions:
            table.append({'难点':title,'实绩数':0,'状态':'未到实绩回报时间'})
            continue
        deltas = [bias for bias,_,_ in decisions]
        delays = [loss for _,loss,_ in decisions if loss is not None]
        violations = [observed for _,_,observed in decisions if observed is not None]
        table.append({'难点':title,'实绩数':len(decisions),'容量偏置中位':round(median(deltas),4),
                      '低估超线':len(delays),'最差超线余量':round(max(delays,default=0),3),
                      '超线累计损失':round(fsum(delays),3),'区间可识别实绩':len(violations),
                      '未覆盖实绩':sum(violations)})
    return table
