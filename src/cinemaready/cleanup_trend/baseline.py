from collections import defaultdict
from math import fabs, fsum
from statistics import mean, median

from .trend_model import score_kernel


def typical_turnaround(sessions):
    halls = defaultdict(list)
    for room in sorted(sessions,key=lambda turn:(turn.day,turn.key)):
        halls[room.cohort].append(room.outcome)
    frozen = {name:median(duration[-7:]) for name,duration in halls.items()}
    return frozen, median(turn.outcome for turn in sessions)


def last_clean_minutes(record,show):
    by_hall, typical = record
    return by_hall.get(show.cohort,typical)


def baseline_review(fit, training, replay):
    convention = typical_turnaround(training)
    production = defaultdict(list)
    for sample in replay:
        if not sample.observed or sample.outcome is None:
            continue
        estimate, _ = score_kernel(fit.parameters,sample)
        baseline = last_clean_minutes(convention, sample)
        actual = sample.outcome
        loss, prior = abs(actual-estimate),abs(actual-baseline)
        production[sample.cohort].append((loss,prior,estimate-actual,baseline-actual))
    reports = []
    for sector, comparison in sorted(production.items()):
        model_loss, base_loss, error, original = zip(*comparison,strict=True)
        paired = tuple(old-new for old,new in zip(base_loss,model_loss,strict=True))
        n = len(comparison)
        reports.append({'回放组':sector,'实绩数':n,'基线':'每厅最后七场使用中位','估计代价':round(mean(model_loss),4),
                        '业务基线代价':round(mean(base_loss),4),'模型偏误中位':round(median(error),4),
                        '参照偏误中位':round(median(original),4),'同单误差减少中位':round(median(paired),4),
                        '改善单数':sum(delta>0 for delta in paired),'恶化单数':sum(delta<0 for delta in paired)})
    return reports
