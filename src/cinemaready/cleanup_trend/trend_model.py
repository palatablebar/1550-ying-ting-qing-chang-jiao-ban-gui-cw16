from collections import defaultdict
from math import exp, fsum
from statistics import median


def fit_kernel(rows):
    chronology = tuple(sorted(rows, key=lambda item: (item.day, item.key)))
    counts = defaultdict(list)
    smooth = chronology[0].outcome
    history = []
    for show in chronology:
        intensity = show.values[0] + .72 * show.values[1] + .28 * show.values[3]
        detail = show.outcome - smooth
        counts[show.cohort].append(detail)
        history.append((show.day, intensity, detail))
        smooth = .18 * show.outcome + .82 * smooth
    origins = fsum(item[1] for item in history) / len(history)
    deviations = fsum((item[1]-origins) ** 2 for item in history)
    slope = fsum((item[1]-origins) * item[2] for item in history) / (deviations + 8.0)
    last_known = chronology[-1].day
    seasonal = tuple((group, median(values) * len(values)/(len(values)+8)) for group, values in sorted(counts.items()))
    return (last_known, smooth, origins, slope, seasonal), (('平滑结束日', last_known), ('平滑交班耗时', smooth), ('清场强度系数', slope))


def score_kernel(history, sample):
    last_day, level, centre, slope, seasonal = history
    trend = (sample.values[0] + .72 * sample.values[1] + .28 * sample.values[3] - centre) * slope
    season = dict(seasonal).get(sample.cohort, 0.)
    ageing = exp(-max(0., sample.day - last_day - 30)/220)
    return max(0., level + (trend+season)*ageing), (trend, season, ageing)
