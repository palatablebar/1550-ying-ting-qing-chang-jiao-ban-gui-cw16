from collections import Counter

from .contracts import DELAYED, ON_TIME, PENDING_STATE, REMEDIAL_STATE


def remedial_ledger_rows(batch):
    """工作台与导出凭证：按措施、开门时刻和工位对账的补救排窗台账。"""
    rows = []
    for item in batch.signed:
        evidence = item.evidence()
        rows.append({
            '业务安排': REMEDIAL_STATE,
            '关联单据': item.ticket,
            '影厅': item.cohort,
            '措施类别': item.kind,
            '补救措施': item.action,
            '开门时刻': item.schedule,
            '延后分钟': item.delay,
            '占用工位': item.cost,
            '措施用量': item.work_units,
            '片尾后最晚开工': item.slot_start,
            '开门留存时点': item.door_finish,
            '实测改动读数': '；'.join(f"{field} {before}→{after}"
                                    for field, before, after in item.changes),
        })
    for item in batch.pending:
        evidence = item.evidence()
        rows.append({
            '业务安排': PENDING_STATE,
            '关联单据': item.ticket,
            '影厅': item.cohort,
            '开门时刻': '—',
            '延后分钟': '—',
            '占用工位': 0,
            '措施用量': 0,
            '原因码': item.reason,
            '说明': item.explanation,
            '通过验收方案数': item.domain_options,
            '被拒方案数': item.rejected_options,
        })
    return rows


def remedial_reconciliation(batch):
    """工位余额与签发一致性的对账行。"""
    on_time = sum(1 for item in batch.signed if item.schedule == ON_TIME)
    delayed = sum(1 for item in batch.signed if item.schedule == DELAYED)
    gross = sum(item.cost for item in batch.signed)
    by_group = Counter()
    for item in batch.signed:
        by_group[item.cohort] += item.cost
    rows = [
        {'核对项': '倒排赶不上开门场次', '数量': len(batch.candidates)},
        {'核对项': '补救签发（准时开门）', '数量': on_time},
        {'核对项': '补救签发（延后开门）', '数量': delayed},
        {'核对项': '留待协调', '数量': len(batch.pending)},
        {'核对项': '补救前工位余额', '数量': batch.base_balance},
        {'核对项': '补救签发病房工位（毛额）', '数量': gross},
        {'核对项': '补救净增工位', '数量': batch.remedial_used},
        {'核对项': '补救后工位余额', '数量': batch.final_balance},
    ]
    rows.extend({'核对项': f'补救工位·{zone}', '数量': cost}
                for zone, cost in sorted(by_group.items()))
    return rows


def measure_reconciliation(batch):
    """按措施汇总：每条签发都要能回查到措施和实测改动读数。"""
    tally = Counter()
    measured = Counter()
    work = Counter()
    for item in batch.signed:
        label = f'{item.kind}·{item.action}'
        tally[label] += 1
        measured[label] += len(item.measured)
        work[label] += item.work_units
    return [{'补救措施': label, '签发单量': tally[label],
             '实测改动读数项': measured[label], '措施总用量': work[label]}
            for label in sorted(tally)]
