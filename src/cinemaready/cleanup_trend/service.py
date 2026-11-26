from hashlib import sha256
from math import fsum, isfinite, sqrt
from statistics import median

from .contracts import MODEL_NAME, Fit, Prediction
from .baseline import baseline_review
from .diagnostics import explain_cleanup_trend
from .trend_model import fit_kernel, score_kernel


def train_series(history):
    timetable = {}
    for item in history:
        if item.key in timetable:
            raise ValueError('出现相同单号的两个拟合目标')
        if item.outcome is None or not isfinite(item.outcome) or not all(map(isfinite,item.values)):
            raise ValueError('连续量测和实绩必须有限')
        timetable[item.key] = item
    return tuple(sorted(timetable.values(),key=lambda row:(row.day,row.key)))


def fit_model(history, feature_stamp):
    ordered = train_series(history)
    if len(ordered)<8 or not feature_stamp:
        raise ValueError('拟合时段失效或有效连续量测少于八条')
    fitted, details = fit_kernel(ordered)
    actuals = tuple(item.outcome for item in ordered)
    centre = median(actuals)
    spread = sqrt(fsum((value-centre)**2 for value in actuals)/len(actuals))
    signature = tuple((item.day,item.key,item.cohort,item.values,item.outcome,item.observed) for item in ordered)
    digest = sha256(repr((feature_stamp,MODEL_NAME,signature)).encode()).hexdigest()[:16]
    return Fit(MODEL_NAME,feature_stamp,digest,fitted,(*details,('实绩中位',centre),('实绩中位根偏差',spread)))


def predict_one(fit, sample):
    predicted, coefficients = score_kernel(fit.parameters,sample)
    inspected = (predicted,*coefficients)
    if not all(isfinite(number) for number in inspected):
        raise ValueError('连续值计算溢出')
    if predicted<0:
        raise ArithmeticError('连续计算结果低于物理下限')
    data = sample.excursions, sample.outcome, sample.observed, sample.input_values
    return Prediction(sample.key,sample.cohort,sample.day,predicted,tuple(coefficients),sample.missing,*data)


def predict(fit, observations, feature_stamp):
    if fit.feature == feature_stamp:
        return tuple(predict_one(fit,point) for point in observations)
    raise ValueError('连续模型与拟合量测版本不相容')


def compare_batches(fit, groups, feature_stamp):
    separate = tuple(prediction for group in groups for prediction in predict(fit, group, feature_stamp))
    return separate == predict(fit, (row for group in groups for row in group), feature_stamp)


def inspection_rows(fit, sections):
    """Return model-specific evidence for the current run without retraining."""
    return (explain_cleanup_trend(fit, sections.calibration, sections.replay, sections.live)
            + baseline_review(fit, sections.train, sections.replay))
