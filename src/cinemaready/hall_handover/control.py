from collections import Counter
from math import isfinite


def accountable_plan(rows, actual_balance, starting_capacity):
    seen = set()
    counts = Counter()
    total = 0
    for row in rows:
        if row['key'] in seen:
            raise ArithmeticError('复核凭证的关联单号不唯一')
        key = row['key']
        seen.add(key)
        state = row['state']
        counts[state] += 1
        if state == '已分派':
            total += row['cost']
        if not isfinite(row['estimate']):
            raise ArithmeticError('非有限估计不能签发')
    if total + actual_balance != starting_capacity:
        raise ArithmeticError('处置清册与工位余额不符')
    return counts, total


def register_hall_handover(measurements, estimate):
    seats = measurements['seats']
    filled = measurements['filled']
    spill = measurements['spill']
    minutes = measurements['minutes']
    bins = measurements['bins']
    stairs = measurements['stairs']
    return {
        '实到观众': round(seats*filled/100, 3),
        '估计现场交班余量': round(minutes-(6+spill*.6+stairs*.14), 3),
        '距常规窗口差': round(minutes-22, 3),
        '散场与下一场重叠代偿': round(filled*max(0,22-minutes)/100, 3),
        '复核代价指标': round(max(0,estimate+2-minutes)/5 + spill/23, 4),
    }


def document_control(rows):
    register = []
    for row in rows:
        if row['state'] not in {'已分派', '暂停', '人工判读'}:
            continue
        note = register_hall_handover(row['measurements'], row['estimate'])
        register.append({'单号': row['key'], '区段': row['zone'], '处置': row['state'], **note})
    return register
