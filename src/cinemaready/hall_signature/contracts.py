from dataclasses import dataclass
from math import isfinite
from ..show_handoffs.contracts import CinemareadyRecord as RawObservation

RAW_KEYS = ('seats', 'filled', 'spill', 'minutes', 'bins', 'stairs')
FEATURE_KEYS = ('people', 'spill_load', 'release_pace', 'stair_paths', 'contamination')
FEATURE_NAMES = ('本场人数', '单桶污渍压力', '交班节奏', '楼梯移动压力', '污渍与人流交互')


@dataclass(frozen=True, slots=True)
class FeatureState:
    fill: tuple[float, ...]
    offsets: tuple[float, ...]
    scales: tuple[float, ...]
    floor: tuple[float, ...]
    ceil: tuple[float, ...]
    fingerprint: str

    def __post_init__(self):
        if len(self.fill) != len(RAW_KEYS):
            raise ValueError('补值向量维数与字段表不匹配')
        if any(len(column) != len(FEATURE_KEYS) for column in (self.offsets, self.scales, self.floor, self.ceil)):
            raise ValueError('特征状态维数不匹配')
        if min(self.scales) <= 0:
            raise ValueError('特征尺度必须为正')


@dataclass(frozen=True, slots=True)
class FeatureVector:
    key: str
    cohort: str
    day: int
    values: tuple[float, ...]
    factors: tuple[float, ...]
    missing: tuple[str, ...]
    excursions: tuple[str, ...]
    outcome: float | None
    observed: bool
    input_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PreparedRuns:
    train: tuple[FeatureVector, ...]
    calibration: tuple[FeatureVector, ...]
    replay: tuple[FeatureVector, ...]
    live: tuple[FeatureVector, ...]

    def segments(self):
        return tuple((name, getattr(self, name)) for name in ('train', 'calibration', 'replay', 'live'))


@dataclass(frozen=True, slots=True)
class Proposal:
    name: str
    field: str
    before: float
    after: float
    work: int

    def __post_init__(self):
        if self.before == self.after or not isfinite(self.after) or self.work < 0:
            raise ValueError('推演动作需要实质变动和有效额度')

    def evidence(self):
        return {'情形': self.name, '变更项': self.field, '原值': self.before,
                '置换值': self.after, '用量': self.work}

@dataclass(frozen=True, slots=True)
class HallSignature:
    attendance: float
    spill_by_person: float
    window_slack: float
    seat_turnover: float
    bag_counts: float
    stairs_steps: float
    extra_minutes: float
    exit_pressure: float

    def __post_init__(self):
        if not all(isfinite(amount) for amount in (self.attendance, self.spill_by_person, self.window_slack, self.seat_turnover, self.bag_counts, self.stairs_steps, self.extra_minutes, self.exit_pressure)):
            raise ValueError('影厅场次存在无效的作业量测')

    def explain(self, labels=None):
        return (
            ('实到观众', round(self.attendance, 4)),
            ('每百人污渍', round(self.spill_by_person, 4)),
            ('估计现场交班余量', round(self.window_slack, 4)),
            ('开厅前每分钟清座', round(self.seat_turnover, 4)),
            ('每桶客流', round(self.bag_counts, 4)),
            ('楼梯污渍配合工作', round(self.stairs_steps, 4)),
            ('距常规窗口差', round(self.extra_minutes, 4)),
            ('散场与下一场重叠代偿', round(self.exit_pressure, 4)),
        )
