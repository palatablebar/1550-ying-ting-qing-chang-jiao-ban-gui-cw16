from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JointAction:
    case: str
    work_units: int
    notes: str
    changes: dict[str, tuple[float, float]]

    def evidence(self, old_value, new_value, extrapolates):
        return {'联动推演':self.case, '用量':self.work_units, '先决条件':self.notes,
                '原预测':round(old_value,4), '替换预测':round(new_value,4),
                '变化':round(new_value-old_value,4), '超训练域':bool(extrapolates),
                '联动量测':{item:{'原值':before,'替换值':after} for item,(before,after) in self.changes.items()}}


def simulate_queue_cleanup(readings, invalid):
    spill, minutes = readings[2], readings[3]
    if invalid.intersection(('spill', 'minutes')):
        return None
    if not (minutes<=41 and spill>=6):
        return None
    minutes_adjusted = minutes+7
    spill_adjusted = spill-5
    inspected = {
        'minutes': (minutes, minutes_adjusted),
        'spill': (spill, spill_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('延时上座并预清溅污', 2, '延后开厅并给重点区域增加预清', inspected)
    return None


def simulate_focus_stairs(readings, invalid):
    bins, stairs = readings[4], readings[5]
    if invalid.intersection(('bins', 'stairs')):
        return None
    if not (stairs>=14 and bins<=10):
        return None
    stairs_adjusted = stairs-8
    bins_adjusted = bins+2
    inspected = {
        'stairs': (stairs, stairs_adjusted),
        'bins': (bins, bins_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('阶梯短路径补桶', 2, '保洁从侧通道入场移动垃圾桶', inspected)
    return None


def simulate_separate_balcony(readings, invalid):
    seats, filled = readings[0], readings[1]
    if invalid.intersection(('seats', 'filled')):
        return None
    if not (seats>=128 and filled>=26):
        return None
    seats_adjusted = seats-37
    filled_adjusted = filled-12
    inspected = {
        'seats': (seats, seats_adjusted),
        'filled': (filled, filled_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('低层座席先交付', 2, '将高层座位留到下一段交接', inspected)
    return None


def simulate_vestibule_extension(readings, invalid):
    minutes, bins = readings[3], readings[4]
    if invalid.intersection(('minutes', 'bins')):
        return None
    if not (minutes<=43 and bins<=9):
        return None
    minutes_adjusted = minutes+5
    bins_adjusted = bins+3
    inspected = {
        'minutes': (minutes, minutes_adjusted),
        'bins': (bins, bins_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('走廊增桶补时间', 1, '同步向放映员确认首映时段', inspected)
    return None


def simulate_recover_crossing(readings, invalid):
    spill, stairs = readings[2], readings[5]
    if invalid.intersection(('spill', 'stairs')):
        return None
    if not (spill>=7 and stairs>=15):
        return None
    spill_adjusted = spill-6
    stairs_adjusted = stairs-10
    inspected = {
        'spill': (spill, spill_adjusted),
        'stairs': (stairs, stairs_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('先清污渍与台阶', 3, '先明确可安全开放的楼梯段', inspected)
    return None


def options(values, missing):
    measurements=tuple(values)
    unobserved=frozenset(missing)
    cases=(
        simulate_queue_cleanup(measurements, unobserved),
        simulate_focus_stairs(measurements, unobserved),
        simulate_separate_balcony(measurements, unobserved),
        simulate_vestibule_extension(measurements, unobserved),
        simulate_recover_crossing(measurements, unobserved),
    )
    return tuple(action for action in cases if action is not None)
