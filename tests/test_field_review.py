from cinemaready.pipeline import preview
from cinemaready.usher_windows.service import operating_ledger


def note(key, measures, *, zone='甲区', state='已分派', estimate=0, hits=(), missing=()):
    return {'key':key,'zone':zone,'state':state,'estimate':estimate,'hits':hits,
            'unmeasured':missing,'measurements':dict(zip(('seats', 'filled', 'spill', 'minutes', 'bins', 'stairs'),measures,strict=True))}


def test_field_plan_is_visible_and_references_real_tickets():
    desk = preview()
    plan = desk['sections'][6]
    assert plan['operating_title'] == '清场倒排窗口'
    assert plan['operating_rows']
    scoped = {item['关联单据'] for item in plan['operating_rows'] if '关联单据' in item}
    assert scoped and scoped <= {row['key'] for row in desk['rows']}
    assert all(item['业务安排'] for item in plan['operating_rows'])


def test_impossible_back_schedule_requests_supervisor_notification():
    show = note('CH-1',(300,91,21,15,2,48),estimate=22,state='暂停')
    alert, account = operating_ledger([show])
    assert alert['片尾后最晚开工']<0
    assert alert['业务安排']=='通知售票台顺延入场'
    assert account['待协调开门单量']==1 and account['本班已排窗口']==0
