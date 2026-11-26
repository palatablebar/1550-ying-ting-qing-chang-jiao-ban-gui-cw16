from dataclasses import replace
from math import ceil, isfinite

from ..hall_signature.contracts import RAW_KEYS
from ..hall_signature.interventions import propose_usher_windows
from ..hall_signature.joint import options as joint_options
from ..hall_signature.service import numeric_fields
from ..cleanup_trend.service import predict_one
from ..slot_backcheck.service import check_point
from ..usher_windows.operating_ledger import backward_sweep
from ..usher_windows.service import expected_load, signals
from .contracts import (
    ACCEPTANCE_BUFFER,
    REASON_HARD_RULE, REASON_MISSING_READING, REASON_NO_ACCEPTANCE_TIME,
    REASON_NO_UPPER_BOUND, REASON_OUT_OF_DOMAIN, RemedialOption,
)


def _score(vector, kernel, calibration):
    """用原班冻结模型与校准重算一条（可能被措施调整过的）向量。"""
    return check_point(predict_one(kernel, vector), calibration)


def _hard_rule_hit(values, missing):
    notices = signals(values, None, missing)
    return any(notice.hard for notice in notices)


def build_option(ticket, kind, action, work_units, changes, base_vector, reference,
                 kernel, calibration):
    """按措施改动读数重算单个补救方案，并完成开门验收判定。"""
    missing = frozenset(base_vector.missing)
    changed_fields = tuple(field for field, _, _ in changes)
    # 措施所改的读数得有实测：缺测字段不允许作为补救改动量
    missing_reading = bool(missing.intersection(changed_fields))
    adjusted = tuple(next(after for field, _, after in changes if field == key)
                     if key in changed_fields else value
                     for key, value in zip(RAW_KEYS, base_vector.input_values, strict=True))
    scaled, factors, excursions = numeric_fields(adjusted, reference)
    scenario = replace(base_vector, values=scaled, factors=factors,
                       input_values=adjusted, excursions=excursions)
    assessment = _score(scenario, kernel, calibration)
    if not isfinite(assessment.estimate):
        raise ValueError('补救方案的模型重算结果无效')
    measurements = dict(zip(RAW_KEYS, adjusted, strict=True))
    slot = backward_sweep({'measurements': measurements, 'estimate': assessment.estimate})
    hard = _hard_rule_hit(adjusted, base_vector.missing)
    out_of_domain = bool(excursions)
    minutes = adjusted[RAW_KEYS.index('minutes')]
    has_upper = assessment.upper is not None
    upper_fits = has_upper and assessment.upper + ACCEPTANCE_BUFFER <= minutes
    on_time = slot.start >= 0 and upper_fits
    delay = 0 if on_time else (max(0, ceil(assessment.upper) + ACCEPTANCE_BUFFER - int(minutes))
                               if has_upper else None)
    excluded = []
    if missing_reading:
        excluded.append(REASON_MISSING_READING)
    if hard:
        excluded.append(REASON_HARD_RULE)
    if out_of_domain:
        excluded.append(REASON_OUT_OF_DOMAIN)
    if not has_upper:
        excluded.append(REASON_NO_UPPER_BOUND)
    elif not upper_fits:
        excluded.append(REASON_NO_ACCEPTANCE_TIME)
    return RemedialOption(
        ticket=ticket, kind=kind, action=action, work_units=work_units,
        changes=tuple(changes), estimate=assessment.estimate, lower=assessment.lower,
        upper=assessment.upper, adjusted_values=tuple(adjusted),
        cost=expected_load(adjusted), slot_start=slot.start, door_finish=slot.finish,
        delay=0 if delay is None else delay, on_time=on_time,
        excluded=tuple(excluded), out_of_domain=out_of_domain,
        missing_reading=missing_reading,
    )


def remedial_options(vector, reference, kernel, calibration):
    """汇总一张当班单的全部单项与联动补救方案，同批使用冻结参数重算。"""
    raw = vector.input_values
    missing = vector.missing
    options = []
    for proposal in propose_usher_windows(raw, missing):
        changes = ((proposal.field, proposal.before, proposal.after),)
        options.append(build_option(vector.key, '单项调整', proposal.name,
                                    proposal.work, changes, vector,
                                    reference, kernel, calibration))
    for joint in joint_options(raw, missing):
        changes = tuple((field, before, after)
                        for field, (before, after) in sorted(joint.changes.items()))
        options.append(build_option(vector.key, '联动措施', joint.case,
                                    joint.work_units, changes, vector,
                                    reference, kernel, calibration))
    return tuple(options)
