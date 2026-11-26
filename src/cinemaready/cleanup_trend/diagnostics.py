from math import exp, log, fsum, sqrt
from statistics import median, mean, quantiles

from .trend_model import score_kernel



def explain_cleanup_trend(fit, calibration, replay, live):
    final_day, trend, center, slope, corridor = fit.parameters
    rows = []
    for zone, seasonal in corridor:
        actual = [item for item in replay if item.cohort == zone and item.outcome is not None]
        if not actual:
            continue
        hidden = [score_kernel(fit.parameters,item)[0]-item.outcome for item in actual]
        raw = [trend-item.outcome for item in actual]
        rows.append({'影厅档':zone,'平滑停止日':final_day,'季节偏移分':round(seasonal,3),
                     '班次回放':len(actual), '调厅后绝对偏差':round(mean(map(abs,hidden)),3),
                     '全厅基准绝对偏差':round(mean(map(abs,raw)),3)})
    return rows
