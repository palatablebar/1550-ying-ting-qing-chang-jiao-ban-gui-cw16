from collections import defaultdict
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class CleaningSlot:
    start: int
    finish: int
    needs_extra: bool
    proof: tuple[int, int, int]


def backward_sweep(entry):
    measures = entry['measurements']
    crowd = ceil(measures['seats'] * measures['filled'] / 100)
    bag_time = max(2, ceil(crowd/(26*measures['bins'])))
    stairs = ceil(measures['stairs']/7)
    interior = max(3, ceil(measures['spill']*.65 + crowd/85))
    finish = max(0, int(measures['minutes'])-2)
    total_work = max(bag_time + max(stairs,interior) + 2, ceil(entry['estimate']))
    return CleaningSlot(finish-total_work,finish,stairs>=5 and interior>=8,(bag_time,stairs,interior))


def overlaps(first, other):
    return first.start < other.finish and other.start < first.finish


def operating_ledger(rows):
    theater = defaultdict(list)
    printout = []
    for entry in rows:
        if entry['unmeasured']:
            printout.append({'业务安排': '核对片尾交接时刻', '关联单据': entry['key'], '距开门': '待复核'})
        else:
            theater[entry['zone']].append((entry,backward_sweep(entry)))
    for hall, schedule in sorted(theater.items()):
        reserved = []
        broken = 0
        for entry, slot in sorted(schedule,key=lambda pair:(pair[1].finish,pair[1].start,pair[0]['key'])):
            conflict = [assignment for assignment, prior in reserved if overlaps(slot, prior)]
            if slot.start < 0 or entry['state']=='暂停':
                verdict = '通知售票台顺延入场'
                broken += 1
            elif conflict:
                verdict = '联系隔壁厅双班支援'
            elif entry['state']=='已分派':
                reserved.append((entry['key'],slot))
                verdict = '预排清场'
            elif slot.needs_extra:
                verdict = '确认双人阶梯清场'
            else:
                continue
            printout.append({'业务安排':verdict, '关联单据':entry['key'], '影厅':hall,
                             '片尾后最晚开工':slot.start, '开门留存时点':slot.finish,
                             '垃圾桶／阶梯／内厅分钟':'/'.join(map(str,slot.proof)),
                             '交叠班组单号':'、'.join(conflict) or '—'})
        printout.append({'业务安排':'清场换厅汇总','影厅':hall,
                         '待协调开门单量':broken,'本班已排窗口':len(reserved)})
    return printout
