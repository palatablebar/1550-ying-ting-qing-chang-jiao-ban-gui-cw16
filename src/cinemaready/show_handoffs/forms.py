from collections.abc import Mapping
from decimal import Decimal

from .contracts import MeasureIssue


from dataclasses import dataclass


def form_number(form, sheet, name, minimum, maximum):
    from .service import number

    table = form.get(sheet)
    if not isinstance(table, Mapping):
        raise MeasureIssue(sheet, 'FORM_SECTION_REQUIRED')
    return Decimal(str(number(table.get(name), name, minimum, maximum)))


@dataclass(frozen=True, slots=True)
class ShowHandoffsSheet:
    licensed_seats: Decimal
    attendance_basis: Decimal
    floor_spills: Decimal
    before_next_seconds: Decimal
    waste_units: Decimal
    stairs_to_mop: Decimal

    def fields(self):
        return {
            'seats': float(self.licensed_seats),
            'filled': float(self.attendance_basis) / 100,
            'spill': float(self.floor_spills),
            'minutes': float(self.before_next_seconds) / 60,
            'bins': float(self.waste_units),
            'stairs': float(self.stairs_to_mop),
        }

    def validation(self):
        fields = self.fields()
        seats = fields['seats']
        filled = fields['filled']
        spill = fields['spill']
        minutes = fields['minutes']
        bins = fields['bins']
        stairs = fields['stairs']
        patron_total = seats*filled/100
        floor_ratio = spill/max(1,patron_total)
        headclear = minutes-2
        stair_per_bucket = stairs/bins
        alerts = []
        if floor_ratio>1:
            alerts.append(('floor_spills', 'SPILLS_EXCEED_AUDIENCE'))
        if headclear<8:
            alerts.append(('before_next_seconds', 'ENTRY_ALARM_REQUIRED'))
        if stair_per_bucket>=46 and patron_total>180:
            alerts.append(('waste_units', 'CHECK_CLEANUP_CREW_LOG'))
        return tuple(alerts)


def read_show_handoffs(form):
    return ShowHandoffsSheet(
        licensed_seats=form_number(form, '排片座席', 'licensed_seats', 85, 320),
        attendance_basis=form_number(form, '排片座席', 'attendance_basis', 900, 9900),
        floor_spills=form_number(form, '场内巡查', 'floor_spills', 0, 27),
        before_next_seconds=form_number(form, '场内巡查', 'before_next_seconds', 720, 2880),
        waste_units=form_number(form, '保洁交班', 'waste_units', 1, 12),
        stairs_to_mop=form_number(form, '保洁交班', 'stairs_to_mop', 5, 48),
    )


def explicit_rows(form):
    if not isinstance(form, Mapping):
        raise MeasureIssue('form', 'FORM_OBJECT_REQUIRED')
    note = read_show_handoffs(form)
    return note.fields(), note.validation()


def check_native_history(source):
    if not isinstance(source, Mapping) or 'form' not in source:
        return source
    if any(key in source for key in ('seats', 'filled', 'spill', 'minutes', 'bins', 'stairs')):
        raise MeasureIssue('form','MIXED_FORM_AND_FLAT_READING')
    converted, flags = explicit_rows(source['form'])
    if flags:
        raise MeasureIssue(*flags[0])
    return {**source, **converted}
