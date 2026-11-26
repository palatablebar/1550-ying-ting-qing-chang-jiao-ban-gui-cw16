from math import ceil, isfinite, sqrt
from statistics import mean

from .contracts import Verification, Assessment, ModelReport
from .slices import replay_slices


def physical_residual_scale(point):
    return max(3., point.input_values[3]/5)


def ranked_error(samples, coverage):
    if not 0 < coverage < 1:
        raise ValueError('区间比例应在零和一之间')
    ordered = sorted(samples)
    if not ordered:
        return None
    order = min(len(ordered)-1,ceil((len(ordered)+1)*coverage)-1)
    return ordered[order]


def cleaning_overrun_bound(entries, assurance):
    scaled = []
    for observation in entries:
        denom = physical_residual_scale(observation)
        scaled.append((observation.score - observation.outcome) / denom)
    inside = ranked_error([max(0,x) for x in scaled], max(assurance,.78))
    outside = ranked_error([max(0,-x) for x in scaled], max(assurance,.92))
    return (inside,outside)


def prepare_verification(pairs, *, coverage=.85):
    known = [item for item in pairs if item.outcome is not None and item.observed]
    if any(not isfinite(ticket.score) or not isfinite(ticket.outcome) for ticket in known):
        raise ValueError('区间估计要求有限的实绩和模型输出')
    if not known:
        return Verification('sparse-interval',(),0,None)
    return Verification('cleaning_overrun_bound',cleaning_overrun_bound(known,coverage),len(known),None)


def check_point(scored, bounds):
    if not isfinite(scored.score) or scored.score < 0:
        raise ValueError('连续预测必须为非负有限值')
    if not bounds.parameters:
        return Assessment(scored,scored.score,None,None,True)
    inner, outer = bounds.parameters
    scale = physical_residual_scale(scored)
    return Assessment(scored,scored.score,max(0.,scored.score-inner*scale),
                      scored.score+outer*scale,False)


def validate_predictions(scored, prepared):
    return tuple(check_point(record, prepared) for record in scored)


def performance(assessments):
    differences = []
    covered = []
    for view in assessments:
        outcome = view.raw.outcome
        if outcome is None or not view.raw.observed:
            continue
        differences.append(view.estimate - outcome)
        if view.lower is not None:
            covered.append(view.lower<=outcome<=view.upper)
    if not differences:
        return ModelReport('NO_MATURE_RESULT',0,None,None,(),None)
    return ModelReport('READY',len(differences),mean(map(abs,differences)),
                       sqrt(mean(delta**2 for delta in differences)),(),mean(covered) if covered else None)


def calibration_evidence(report):
    return [{'核验':report.status,'样本':report.count,'平均绝对误差':report.mae,
             '均方根误差':report.error,'区间覆盖':report.auxiliary}]


def sector_replay(checked, line):
    return replay_slices(checked,line,risk_model=False)


def boundary_diagnostics(checks, threshold):
    missed = high = above = seen = 0
    for review in checks:
        measured = review.raw.outcome
        if measured is not None and review.raw.observed:
            above += measured>=threshold
            seen += review.estimate>=threshold
            missed += review.estimate<threshold<=measured
            high += measured<threshold<=review.estimate
    return {'临界判断':'清场超窗', '实绩超线':above, '估计超线':seen, '额外复测':high, '漏查':missed}
