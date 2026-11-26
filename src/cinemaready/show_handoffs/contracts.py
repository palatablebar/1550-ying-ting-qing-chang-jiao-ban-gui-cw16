from dataclasses import dataclass

FIELDS = {'seats': ('总座数', '席', 85, 320),
 'filled': ('本场上座', '%', 9, 99),
 'spill': ('报告污渍点', '处', 0, 27),
 'minutes': ('片尾结束至下一场', 'min', 12, 48),
 'bins': ('厅外垃圾桶', '个', 1, 12),
 'stairs': ('清理阶梯', '级', 5, 48)}
LIMITS = {'result_max': 10000}


class MeasureIssue(ValueError):
    def __init__(self, field: str, code: str):
        super().__init__(f'{field}:{code}')
        self.field = field
        self.code = code


@dataclass(frozen=True, slots=True)
class CinemareadyRecord:
    key: str
    cohort: str
    day: int
    received: int
    revision: int
    result_day: int | None
    outcome: float | None
    observed: bool
    seats: float | None
    filled: float | None
    spill: float | None
    minutes: float | None
    bins: float | None
    stairs: float | None

    def signature(self):
        return (self.key, self.cohort, self.day, self.revision, self.result_day, self.outcome, self.observed,
                *(getattr(self, key) for key in FIELDS))


@dataclass(frozen=True, slots=True)
class Issue:
    source_row: int
    key: str
    field: str
    code: str

    def evidence(self):
        return {'行号': self.source_row, '单号': self.key, '字段': FIELDS.get(self.field, (self.field,))[0],
                '原因': self.code}


@dataclass(frozen=True, slots=True)
class DecodeResult:
    entries: tuple[CinemareadyRecord, ...]
    issues: tuple[Issue, ...]
    source_rows: int
