def collect_entry_handoff(measures, missing, estimate):
    minutes = measures['minutes']
    if not (minutes<=24):
        return None
    value=minutes-estimate
    return {'现场复核':'开厅倒计时','可复查值':round(value,3),'单位':'分钟','归档要求':'与放映员核对片尾落幕时点',
            '需补测':not set(missing).isdisjoint(('minutes',))}


def collect_floor_clear(measures, missing, estimate):
    spill = measures['spill']
    if not (spill>=10):
        return None
    value=spill
    return {'现场复核':'分派污渍位','可复查值':round(value,3),'单位':'处','归档要求':'记录上下层污渍点位置',
            '需补测':not set(missing).isdisjoint(('spill',))}


def collect_waste_refill(measures, missing, estimate):
    seats = measures['seats']
    filled = measures['filled']
    bins = measures['bins']
    if not (bins<=5):
        return None
    value=seats*filled/(100*bins)
    return {'现场复核':'换桶','可复查值':round(value,3),'单位':'顾客/桶','归档要求':'确认垃圾袋在走廊可取',
            '需补测':not set(missing).isdisjoint(('seats', 'filled', 'bins'))}


def collect_stair_layout(measures, missing, estimate):
    stairs = measures['stairs']
    if not (stairs>=23):
        return None
    value=stairs
    return {'现场复核':'复盘阶梯','可复查值':round(value,3),'单位':'级','归档要求':'从上层到闸机口签交接',
            '需补测':not set(missing).isdisjoint(('stairs',))}


def check_hall_handover(records):
    guide = []
    for ticket in records:
        if ticket['state'] not in ('已分派','暂停','人工判读'):
            continue
        measures=ticket['measurements']
        absent=ticket['unmeasured']
        estimate=ticket['estimate']
        checks = (
            collect_entry_handoff(measures,absent,estimate),
            collect_floor_clear(measures,absent,estimate),
            collect_waste_refill(measures,absent,estimate),
            collect_stair_layout(measures,absent,estimate),
        )
        required=tuple(check for check in checks if check is not None)
        if not required:
            continue
        review=ticket['key']
        for check in required:
            guide.append({'签收单':review,'作业区':ticket['zone'],'处置':ticket['state'],**check})
    return guide
