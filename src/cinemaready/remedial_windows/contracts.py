from dataclasses import dataclass

# 倒排以片尾为 0 时刻，开门验收必须预留的分钟数
ACCEPTANCE_BUFFER = 2
# 补救排窗在导出凭证中的处置标签
REMEDIAL_STATE = '补救签发'
PENDING_STATE = '留待协调'
# 准时 / 延后两类排窗
ON_TIME = '准时开门'
DELAYED = '延后开门'

# 方案不签发原因码
REASON_HARD_RULE = 'REMEDIAL_HARD_RULE'
REASON_OUT_OF_DOMAIN = 'REMEDIAL_OUT_OF_DOMAIN'
REASON_MISSING_READING = 'REMEDIAL_MISSING_READING'
REASON_NO_UPPER_BOUND = 'REMEDIAL_NO_UPPER_BOUND'
REASON_NO_ACCEPTANCE_TIME = 'REMEDIAL_NO_ACCEPTANCE_TIME'
REASON_NO_VIABLE_PLAN = 'REMEDIAL_NO_VIABLE_PLAN'
REASON_CAPACITY_REACHED = 'REMEDIAL_CAPACITY_REACHED'
REASON_GROUP_CAP_REACHED = 'REMEDIAL_GROUP_CAP_REACHED'
REASON_SLOT_OVERLAP = 'REMEDIAL_SLOT_OVERLAP'


@dataclass(frozen=True, slots=True)
class RemedialOption:
    """单项或联动措施用冻结模型与校准重算后的补救方案。"""
    ticket: str
    kind: str                      # 单项调整 / 联动措施
    action: str                    # 措施名称
    work_units: int                # 措施本身的用量（凭证留存，不占工位余额）
    changes: tuple[tuple[str, float, float], ...]  # (字段, 原值, 替换值)，替换值须为实测读数
    estimate: float
    lower: float | None
    upper: float | None
    adjusted_values: tuple[float, ...]
    cost: int                      # 重算后的所需工位数
    slot_start: int                # 相对片尾的最晚开工分钟
    door_finish: int               # 开门留存时点（相对片尾）
    delay: int                     # 相对原开门时刻的延后分钟，0 为准时
    on_time: bool
    excluded: tuple[str, ...]      # 不签发原因码（空表示通过验收）
    out_of_domain: bool
    missing_reading: bool

    @property
    def viable(self):
        return not self.excluded


@dataclass(frozen=True, slots=True)
class SignedRemedy:
    ticket: str
    cohort: str
    kind: str
    action: str
    schedule: str                  # ON_TIME / DELAYED
    delay: int
    cost: int
    work_units: int
    estimate: float
    upper: float | None
    slot_start: int
    door_finish: int
    changes: tuple[tuple[str, float, float], ...]
    measured: tuple[str, ...]      # 措施改动且具备实测读数的字段

    def evidence(self):
        return {'关联单据': self.ticket, '作业区': self.cohort, '补救措施': self.action,
                '措施类别': self.kind, '开门时刻': self.schedule, '延后分钟': self.delay,
                '占用工位': self.cost, '措施用量': self.work_units,
                '替换预测': round(self.estimate, 4), '估计上界': None if self.upper is None else round(self.upper, 4),
                '片尾后最晚开工': self.slot_start, '开门留存时点': self.door_finish,
                '实测改动读数': tuple({'量测': field, '原值': before, '替换值': after}
                                     for field, before, after in self.changes)}


@dataclass(frozen=True, slots=True)
class PendingRemedy:
    ticket: str
    cohort: str
    reason: str
    explanation: str
    rejected_options: int
    domain_options: int

    def evidence(self):
        return {'关联单据': self.ticket, '作业区': self.cohort, '处置': PENDING_STATE,
                '原因码': self.reason, '说明': self.explanation,
                '被拒方案数': self.rejected_options, '通过验收方案数': self.domain_options}


@dataclass(frozen=True, slots=True)
class RemedialBatch:
    signed: tuple[SignedRemedy, ...]
    pending: tuple[PendingRemedy, ...]
    candidates: tuple[str, ...]
    capacity: int
    base_balance: int              # 常规分派后的工位余额
    remedial_used: int             # 补救净增工位（补救成本 − 已分派候选释放的原占用）
    final_balance: int
    used_by_group: tuple[tuple[str, int], ...]

    def __post_init__(self):
        if self.base_balance != self.remedial_used + self.final_balance:
            raise ArithmeticError('补救排窗工位余额不平')
        signed_keys = tuple(item.ticket for item in self.signed)
        pending_keys = tuple(item.ticket for item in self.pending)
        if len(signed_keys) + len(pending_keys) != len(self.candidates):
            raise ArithmeticError('补救候选与签发/留待清单无法对账')
        if set(signed_keys) & set(pending_keys):
            raise ArithmeticError('同一场次不能同时签发与留待协调')
        # 补救净增工位可为负：负数表示补救后该单所需工位少于原常规占用，净释放回余额
