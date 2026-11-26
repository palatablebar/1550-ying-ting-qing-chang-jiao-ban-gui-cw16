from dataclasses import replace
from statistics import median

from .contracts import HallSignature, Proposal


def measure_hall_signature(values) -> HallSignature:
    seats, filled, spill, minutes, bins, stairs = values
    return HallSignature(
        attendance=seats*filled/100,
        spill_by_person=100*spill/(seats*filled/100),
        window_slack=minutes-(6+spill*.6+stairs*.14),
        seat_turnover=seats*filled/(100*minutes),
        bag_counts=seats*filled/(100*bins),
        stairs_steps=stairs*(1+spill/14),
        extra_minutes=minutes-22,
        exit_pressure=filled*max(0,22-minutes)/100,
    )


def propose_usher_windows(values, missing=()):
    seats, filled, spill, minutes, bins, stairs = values
    if 'minutes' not in missing and (minutes<=41):
        yield Proposal('片尾后增开清场时间', 'minutes', minutes, min(48,minutes+7), 0)
    if 'spill' not in missing and (spill>=5):
        yield Proposal('先做溅污预清', 'spill', spill, max(0,spill-5), 2)
    if 'bins' not in missing and (bins<=10):
        yield Proposal('厅外添置两个桶位', 'bins', bins, min(12,bins+2), 1)
    if 'stairs' not in missing and (stairs>=13):
        yield Proposal('缩短清理动线', 'stairs', stairs, max(5,stairs-8), 1)
