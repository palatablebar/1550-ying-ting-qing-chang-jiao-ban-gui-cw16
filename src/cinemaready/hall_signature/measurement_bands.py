from dataclasses import replace
from statistics import mean, median
from collections import Counter
from math import fsum

from .contracts import FEATURE_NAMES, FEATURE_KEYS, RAW_KEYS


def current_attendance(vector):
    seats = vector.input_values[0]
    filled = vector.input_values[1]
    return float(seats*filled/100)


def compare_attendance(training, target):
    usual_attendance = take_sample(training, current_attendance)
    recent_attendance = take_sample(target, current_attendance)
    if len(usual_attendance) < 4 or not recent_attendance:
        return {'作业量': '实到观众', '有效读数': len(recent_attendance), '判断': '参考不足'}
    anchor_attendance = median(usual_attendance)
    measured_attendance = median(recent_attendance)
    band_attendance = max(1.0, abs(anchor_attendance)*.2, median(abs(value-anchor_attendance) for value in usual_attendance))
    change_attendance = (measured_attendance-anchor_attendance) / band_attendance
    outside_attendance = sum(abs(value-anchor_attendance)>2.5*band_attendance for value in recent_attendance)
    return {'作业量': '实到观众', '训练参考': round(anchor_attendance, 4), '现场中位': round(measured_attendance, 4),
            '变动': round(change_attendance, 4), '越界量': outside_attendance, '有效读数': len(recent_attendance)}


def current_spill_by_person(vector):
    seats = vector.input_values[0]
    filled = vector.input_values[1]
    spill = vector.input_values[2]
    return float(100*spill/(seats*filled/100))


def compare_spill_by_person(training, target):
    usual_spill_by_person = take_sample(training, current_spill_by_person)
    recent_spill_by_person = take_sample(target, current_spill_by_person)
    if len(usual_spill_by_person) < 4 or not recent_spill_by_person:
        return {'作业量': '每百人污渍', '有效读数': len(recent_spill_by_person), '判断': '参考不足'}
    anchor_spill_by_person = median(usual_spill_by_person)
    measured_spill_by_person = median(recent_spill_by_person)
    ordered_spill_by_person = sorted(usual_spill_by_person)
    low_spill_by_person, high_spill_by_person = ordered_spill_by_person[len(ordered_spill_by_person)//10], ordered_spill_by_person[(len(ordered_spill_by_person)*9)//10]
    change_spill_by_person = measured_spill_by_person-anchor_spill_by_person
    outside_spill_by_person = sum(value<low_spill_by_person or value>high_spill_by_person for value in recent_spill_by_person)
    return {'作业量': '每百人污渍', '训练参考': round(anchor_spill_by_person, 4), '现场中位': round(measured_spill_by_person, 4),
            '变动': round(change_spill_by_person, 4), '越界量': outside_spill_by_person, '有效读数': len(recent_spill_by_person)}


def current_window_slack(vector):
    spill = vector.input_values[2]
    minutes = vector.input_values[3]
    stairs = vector.input_values[5]
    return float(minutes-(6+spill*.6+stairs*.14))


def compare_window_slack(training, target):
    usual_window_slack = take_sample(training, current_window_slack)
    recent_window_slack = take_sample(target, current_window_slack)
    if len(usual_window_slack) < 4 or not recent_window_slack:
        return {'作业量': '估计现场交班余量', '有效读数': len(recent_window_slack), '判断': '参考不足'}
    anchor_window_slack = median(usual_window_slack)
    measured_window_slack = median(recent_window_slack)
    ordered_window_slack = sorted(usual_window_slack)
    low_window_slack, high_window_slack = ordered_window_slack[len(ordered_window_slack)//10], ordered_window_slack[(len(ordered_window_slack)*9)//10]
    change_window_slack = measured_window_slack-anchor_window_slack
    outside_window_slack = sum(value<low_window_slack or value>high_window_slack for value in recent_window_slack)
    return {'作业量': '估计现场交班余量', '训练参考': round(anchor_window_slack, 4), '现场中位': round(measured_window_slack, 4),
            '变动': round(change_window_slack, 4), '越界量': outside_window_slack, '有效读数': len(recent_window_slack)}


def current_seat_turnover(vector):
    seats = vector.input_values[0]
    filled = vector.input_values[1]
    minutes = vector.input_values[3]
    return float(seats*filled/(100*minutes))


def compare_seat_turnover(training, target):
    usual_seat_turnover = take_sample(training, current_seat_turnover)
    recent_seat_turnover = take_sample(target, current_seat_turnover)
    if len(usual_seat_turnover) < 4 or not recent_seat_turnover:
        return {'作业量': '开厅前每分钟清座', '有效读数': len(recent_seat_turnover), '判断': '参考不足'}
    anchor_seat_turnover = median(usual_seat_turnover)
    measured_seat_turnover = median(recent_seat_turnover)
    band_seat_turnover = max(1.0, abs(anchor_seat_turnover)*.2, median(abs(value-anchor_seat_turnover) for value in usual_seat_turnover))
    change_seat_turnover = (measured_seat_turnover-anchor_seat_turnover) / band_seat_turnover
    outside_seat_turnover = sum(abs(value-anchor_seat_turnover)>2.5*band_seat_turnover for value in recent_seat_turnover)
    return {'作业量': '开厅前每分钟清座', '训练参考': round(anchor_seat_turnover, 4), '现场中位': round(measured_seat_turnover, 4),
            '变动': round(change_seat_turnover, 4), '越界量': outside_seat_turnover, '有效读数': len(recent_seat_turnover)}


def current_bag_counts(vector):
    seats = vector.input_values[0]
    filled = vector.input_values[1]
    bins = vector.input_values[4]
    return float(seats*filled/(100*bins))


def compare_bag_counts(training, target):
    usual_bag_counts = take_sample(training, current_bag_counts)
    recent_bag_counts = take_sample(target, current_bag_counts)
    if len(usual_bag_counts) < 4 or not recent_bag_counts:
        return {'作业量': '每桶客流', '有效读数': len(recent_bag_counts), '判断': '参考不足'}
    anchor_bag_counts = median(usual_bag_counts)
    measured_bag_counts = median(recent_bag_counts)
    band_bag_counts = max(1.0, abs(anchor_bag_counts)*.2, median(abs(value-anchor_bag_counts) for value in usual_bag_counts))
    change_bag_counts = (measured_bag_counts-anchor_bag_counts) / band_bag_counts
    outside_bag_counts = sum(abs(value-anchor_bag_counts)>2.5*band_bag_counts for value in recent_bag_counts)
    return {'作业量': '每桶客流', '训练参考': round(anchor_bag_counts, 4), '现场中位': round(measured_bag_counts, 4),
            '变动': round(change_bag_counts, 4), '越界量': outside_bag_counts, '有效读数': len(recent_bag_counts)}


def current_stairs_steps(vector):
    spill = vector.input_values[2]
    stairs = vector.input_values[5]
    return float(stairs*(1+spill/14))


def compare_stairs_steps(training, target):
    usual_stairs_steps = take_sample(training, current_stairs_steps)
    recent_stairs_steps = take_sample(target, current_stairs_steps)
    if len(usual_stairs_steps) < 4 or not recent_stairs_steps:
        return {'作业量': '楼梯污渍配合工作', '有效读数': len(recent_stairs_steps), '判断': '参考不足'}
    anchor_stairs_steps = median(usual_stairs_steps)
    measured_stairs_steps = median(recent_stairs_steps)
    band_stairs_steps = max(1.0, abs(anchor_stairs_steps)*.2, median(abs(value-anchor_stairs_steps) for value in usual_stairs_steps))
    change_stairs_steps = (measured_stairs_steps-anchor_stairs_steps) / band_stairs_steps
    outside_stairs_steps = sum(abs(value-anchor_stairs_steps)>2.5*band_stairs_steps for value in recent_stairs_steps)
    return {'作业量': '楼梯污渍配合工作', '训练参考': round(anchor_stairs_steps, 4), '现场中位': round(measured_stairs_steps, 4),
            '变动': round(change_stairs_steps, 4), '越界量': outside_stairs_steps, '有效读数': len(recent_stairs_steps)}


def current_extra_minutes(vector):
    minutes = vector.input_values[3]
    return float(minutes-22)


def compare_extra_minutes(training, target):
    usual_extra_minutes = take_sample(training, current_extra_minutes)
    recent_extra_minutes = take_sample(target, current_extra_minutes)
    if len(usual_extra_minutes) < 4 or not recent_extra_minutes:
        return {'作业量': '距常规窗口差', '有效读数': len(recent_extra_minutes), '判断': '参考不足'}
    anchor_extra_minutes = median(usual_extra_minutes)
    measured_extra_minutes = median(recent_extra_minutes)
    ordered_extra_minutes = sorted(usual_extra_minutes)
    low_extra_minutes, high_extra_minutes = ordered_extra_minutes[len(ordered_extra_minutes)//10], ordered_extra_minutes[(len(ordered_extra_minutes)*9)//10]
    change_extra_minutes = measured_extra_minutes-anchor_extra_minutes
    outside_extra_minutes = sum(value<low_extra_minutes or value>high_extra_minutes for value in recent_extra_minutes)
    return {'作业量': '距常规窗口差', '训练参考': round(anchor_extra_minutes, 4), '现场中位': round(measured_extra_minutes, 4),
            '变动': round(change_extra_minutes, 4), '越界量': outside_extra_minutes, '有效读数': len(recent_extra_minutes)}


def current_exit_pressure(vector):
    filled = vector.input_values[1]
    minutes = vector.input_values[3]
    return float(filled*max(0,22-minutes)/100)


def compare_exit_pressure(training, target):
    usual_exit_pressure = take_sample(training, current_exit_pressure)
    recent_exit_pressure = take_sample(target, current_exit_pressure)
    if len(usual_exit_pressure) < 4 or not recent_exit_pressure:
        return {'作业量': '散场与下一场重叠代偿', '有效读数': len(recent_exit_pressure), '判断': '参考不足'}
    anchor_exit_pressure = median(usual_exit_pressure)
    measured_exit_pressure = median(recent_exit_pressure)
    ordered_exit_pressure = sorted(usual_exit_pressure)
    low_exit_pressure, high_exit_pressure = ordered_exit_pressure[len(ordered_exit_pressure)//10], ordered_exit_pressure[(len(ordered_exit_pressure)*9)//10]
    change_exit_pressure = measured_exit_pressure-anchor_exit_pressure
    outside_exit_pressure = sum(value<low_exit_pressure or value>high_exit_pressure for value in recent_exit_pressure)
    return {'作业量': '散场与下一场重叠代偿', '训练参考': round(anchor_exit_pressure, 4), '现场中位': round(measured_exit_pressure, 4),
            '变动': round(change_exit_pressure, 4), '越界量': outside_exit_pressure, '有效读数': len(recent_exit_pressure)}


def take_sample(vectors, measure):
    return tuple(measure(record) for record in vectors if not record.missing)


def measure_hall_signature_band(history, daybook):
    yield compare_attendance(history, daybook)
    yield compare_spill_by_person(history, daybook)
    yield compare_window_slack(history, daybook)
    yield compare_seat_turnover(history, daybook)
    yield compare_bag_counts(history, daybook)
    yield compare_stairs_steps(history, daybook)
    yield compare_extra_minutes(history, daybook)
    yield compare_exit_pressure(history, daybook)


def evaluate_shift(training, current):
    return list(measure_hall_signature_band(training, current))
