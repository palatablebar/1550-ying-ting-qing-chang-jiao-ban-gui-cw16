from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import Job


@dataclass(frozen=True, slots=True)
class WorkOrder:
    job: Job
    assessment: Any

    def __post_init__(self):
        if self.job.key != self.assessment.raw.key:
            raise ValueError('处置工位与单据不匹配')


def apply_usher_windows(showings, admit: Callable, wait: Callable):
    hall_crews = set()
    ordered = sorted(showings, key=lambda item: (item.assessment.raw.input_values[3], -item.job.priority, item.job.key))
    for show in ordered:
        seating, filled, effort, minutes, bags, stairs = show.assessment.raw.input_values
        gap = int(minutes//8)
        key = show.job.cohort, gap
        if show.assessment.estimate + 3 > minutes and key in hall_crews:
            wait(show, 'OVERLAPPING_CLEANING_SLOT', '本厅同段保洁已在另一场次')
            continue
        if effort >= 20 and bags <= 3 and filled >= 50:
            wait(show, 'SUPPLY_NOT_ON_FLOOR', '补充袋位后再安排清场人手')
        elif admit(show):
            hall_crews.add(key)
