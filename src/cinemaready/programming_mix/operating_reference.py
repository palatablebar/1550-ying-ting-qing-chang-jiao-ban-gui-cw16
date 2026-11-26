from dataclasses import dataclass
from math import sqrt, fsum
from statistics import median


@dataclass(frozen=True, slots=True)
class DomainStudy:
    counts: tuple[int, int, int]
    rate: float | None
    midpoint: float | None
    expected: float | None
    drift: float | None

def programming_mix_domains(vectors):
    attendance = []
    spill_by_person = []
    window_slack = []
    seat_turnover = []
    bag_counts = []
    stairs_steps = []
    extra_minutes = []
    exit_pressure = []
    for measurement in vectors:
        unobserved = frozenset(measurement.missing)
        seats, filled, spill, minutes, bins, stairs = measurement.input_values
        if unobserved.isdisjoint(('seats', 'filled', 'minutes')):
            attendance.append((round(seats*filled/100, 4), minutes<=20))
        if unobserved.isdisjoint(('seats', 'filled', 'spill')):
            spill_by_person.append((round(100*spill/(seats*filled/100), 4), filled>=78))
        if unobserved.isdisjoint(('spill', 'minutes', 'stairs')):
            window_slack.append((round(minutes-(6+spill*.6+stairs*.14), 4), spill>=14))
        if unobserved.isdisjoint(('seats', 'filled', 'minutes', 'stairs')):
            seat_turnover.append((round(seats*filled/(100*minutes), 4), stairs>=25))
        if unobserved.isdisjoint(('seats', 'filled', 'bins')):
            bag_counts.append((round(seats*filled/(100*bins), 4), bins<=4))
        if unobserved.isdisjoint(('spill', 'minutes', 'stairs')):
            stairs_steps.append((round(stairs*(1+spill/14), 4), minutes<=20))
        if unobserved.isdisjoint(('filled', 'minutes')):
            extra_minutes.append((round(minutes-22, 4), filled>=78))
        if unobserved.isdisjoint(('filled', 'spill', 'minutes')):
            exit_pressure.append((round(filled*max(0,22-minutes)/100, 4), spill>=14))
    return {
        '实到观众 · 排片紧邻': tuple(attendance),
        '每百人污渍 · 高上座': tuple(spill_by_person),
        '估计现场交班余量 · 溅污多': tuple(window_slack),
        '开厅前每分钟清座 · 三层以上台阶': tuple(seat_turnover),
        '每桶客流 · 桶位少': tuple(bag_counts),
        '楼梯污渍配合工作 · 排片紧邻': tuple(stairs_steps),
        '距常规窗口差 · 高上座': tuple(extra_minutes),
        '散场与下一场重叠代偿 · 溅污多': tuple(exit_pressure),
    }


def evaluate_domains(training, current):
    references = programming_mix_domains(training)
    activity = programming_mix_domains(current)
    diagnostics = []
    for domain, observed in activity.items():
        baseline = references.get(domain, ())
        study = characterize(baseline, observed)
        diagnostics.append({'观察维度': domain, '训练有效量': study.counts[0], '当班有效量': study.counts[1],
                            '越线量':study.counts[2], '越线比例':study.rate, '参考中位':study.midpoint,
                            '当班中位':study.expected, '相对训练变化':study.drift})
    return diagnostics


def characterize(before, after):
    history = tuple(value for value, _ in before)
    observed = tuple(value for value, _ in after)
    violating = sum(flag for _, flag in after)
    old = median(history) if history else None
    new = median(observed) if observed else None
    pct = round(violating / len(after), 4) if after else None
    movement = round(new - old, 4) if old is not None and new is not None else None
    return DomainStudy((len(before),len(after),violating),pct,old,new,movement)
