"""Excel-backed staff, shift, assignment, and attendance storage."""

from __future__ import annotations

import os
import re
import tempfile
import threading
from copy import copy
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange
from openpyxl.utils.exceptions import InvalidFileException


EXCEL_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / "staff_records"
    / "hospital_staff_management_template.xlsx"
)

STAFF_SHEET = "Staff"
SHIFTS_SHEET = "Shifts"
ASSIGNMENTS_SHEET = "Duty Assignments"
ATTENDANCE_SHEET = "Attendance"
INSTRUCTIONS_SHEET = "Instructions"

STAFF_HEADERS = (
    "Staff_ID",
    "Full_Name",
    "Role",
    "Department",
    "Contact_Number",
    "Email",
    "Employment_Status",
    "Joining_Date",
    "Notes",
)
SHIFT_HEADERS = (
    "Shift_ID",
    "Shift_Name",
    "Start_Time",
    "End_Time",
    "Crosses_Midnight",
    "Description",
    "Shift_Status",
)
ASSIGNMENT_HEADERS = (
    "Assignment_ID",
    "Staff_ID",
    "Duty_Date",
    "Shift_ID",
    "Assigned_By",
    "Assignment_Status",
    "Notes",
)
ATTENDANCE_HEADERS = (
    "Attendance_ID",
    "Assignment_ID",
    "Staff_ID",
    "Duty_Date",
    "Check_In_DateTime",
    "Check_Out_DateTime",
    "Attendance_Status",
    "Recorded_By",
    "Correction_Reason",
    "Notes",
)

SHEET_HEADERS = {
    STAFF_SHEET: STAFF_HEADERS,
    SHIFTS_SHEET: SHIFT_HEADERS,
    ASSIGNMENTS_SHEET: ASSIGNMENT_HEADERS,
    ATTENDANCE_SHEET: ATTENDANCE_HEADERS,
}
REQUIRED_SHEETS = (*SHEET_HEADERS, INSTRUCTIONS_SHEET)
HEADERS = SHEET_HEADERS

STAFF_ROLES = frozenset(
    {
        "Doctor",
        "Nurse",
        "Receptionist",
        "Lab Technician",
        "Pharmacist",
        "Administrator",
        "Other",
    }
)
EMPLOYMENT_STATUSES = frozenset({"Active", "Inactive", "On Leave", "Resigned"})
SHIFT_STATUSES = frozenset({"Active", "Inactive"})
CROSSES_MIDNIGHT_OPTIONS = frozenset({"Yes", "No"})
ASSIGNMENT_STATUSES = frozenset({"Assigned", "Cancelled", "Completed"})
ATTENDANCE_STATUSES = frozenset(
    {"Present", "Late", "Absent", "Half-day", "On Leave"}
)

_STAFF_EDITABLE = frozenset(STAFF_HEADERS) - {"Staff_ID"}
_SHIFT_EDITABLE = frozenset(SHIFT_HEADERS) - {"Shift_ID"}
_ASSIGNMENT_EDITABLE = frozenset(ASSIGNMENT_HEADERS) - {"Assignment_ID"}
_ATTENDANCE_EDITABLE = frozenset(ATTENDANCE_HEADERS) - {"Attendance_ID"}
_DATE_FIELDS = {
    STAFF_SHEET: frozenset({"Joining_Date"}),
    ASSIGNMENTS_SHEET: frozenset({"Duty_Date"}),
    ATTENDANCE_SHEET: frozenset({"Duty_Date"}),
}
_TIME_FIELDS = frozenset({"Start_Time", "End_Time"})
_DATETIME_FIELDS = frozenset({"Check_In_DateTime", "Check_Out_DateTime"})
_ENUM_FIELDS = {
    STAFF_SHEET: {
        "Role": STAFF_ROLES,
        "Employment_Status": EMPLOYMENT_STATUSES,
    },
    SHIFTS_SHEET: {
        "Crosses_Midnight": CROSSES_MIDNIGHT_OPTIONS,
        "Shift_Status": SHIFT_STATUSES,
    },
    ASSIGNMENTS_SHEET: {"Assignment_Status": ASSIGNMENT_STATUSES},
    ATTENDANCE_SHEET: {"Attendance_Status": ATTENDANCE_STATUSES},
}
_ID_FIELDS = {
    STAFF_SHEET: "Staff_ID",
    SHIFTS_SHEET: "Shift_ID",
    ASSIGNMENTS_SHEET: "Assignment_ID",
    ATTENDANCE_SHEET: "Attendance_ID",
}
_ROW_ID_FIELDS = {
    "Staff_ID",
    "Shift_ID",
    "Assignment_ID",
    "Attendance_ID",
}
_MAX_CELL_TEXT = 32767
LATE_GRACE_MINUTES = 5

# Serializes access within this process. Atomic replacement protects against a
# partially written workbook; coordinating separate processes requires a
# database or an OS-level lock and is outside this module's scope.
_file_lock = threading.RLock()


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _validate_headers(worksheet: Any, headers: tuple[str, ...]) -> None:
    actual = tuple(
        worksheet.cell(row=1, column=column).value
        for column in range(1, len(headers) + 1)
    )
    extra_headers = (
        worksheet.cell(row=1, column=column).value
        for column in range(len(headers) + 1, worksheet.max_column + 1)
    )
    if actual != headers or any(not _is_blank(value) for value in extra_headers):
        raise ValueError(
            f"The {worksheet.title!r} sheet headers do not match the expected "
            "hospital staff template. Keep column names and order unchanged."
        )


def _load_workbook(*, read_only: bool = False, data_only: bool = False):
    if not EXCEL_FILE.is_file():
        raise FileNotFoundError(f"Staff-record workbook not found: {EXCEL_FILE}")

    try:
        workbook = load_workbook(
            EXCEL_FILE,
            read_only=read_only,
            data_only=data_only,
        )
    except (BadZipFile, EOFError, InvalidFileException) as error:
        raise ValueError("The staff-record workbook is corrupt or unsupported.") from error

    try:
        missing_sheets = set(REQUIRED_SHEETS) - set(workbook.sheetnames)
        if missing_sheets:
            missing = ", ".join(sorted(missing_sheets))
            raise ValueError(f"Staff-record workbook is missing worksheet(s): {missing}.")
        for sheet_name, headers in SHEET_HEADERS.items():
            _validate_headers(workbook[sheet_name], headers)
        _validate_workbook_integrity(workbook)
        return workbook
    except Exception:
        workbook.close()
        raise


def _parse_text(field: str, value: Any, *, required: bool = False) -> str | None:
    if value is None:
        text_value = None
    elif isinstance(value, str):
        text_value = value.strip() or None
    else:
        raise ValueError(f"{field} must be text.")

    if required and text_value is None:
        raise ValueError(f"{field} is required.")
    if text_value is not None and len(text_value) > _MAX_CELL_TEXT:
        raise ValueError(f"{field} exceeds the Excel cell text limit.")
    return text_value


def _parse_date(field: str, value: Any, *, required: bool = False) -> date | None:
    if value is None or _is_blank(value):
        if required:
            raise ValueError(f"{field} is required.")
        return None
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = date.fromisoformat(value.strip())
        except ValueError as error:
            raise ValueError(f"{field} must use YYYY-MM-DD format.") from error
    else:
        raise ValueError(f"{field} must be a date in YYYY-MM-DD format.")
    return parsed


def _parse_time(field: str, value: Any, *, required: bool = False) -> time | None:
    if value is None or _is_blank(value):
        if required:
            raise ValueError(f"{field} is required.")
        return None
    if isinstance(value, datetime):
        parsed = value.time()
    elif isinstance(value, time):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = time.fromisoformat(value.strip())
        except ValueError as error:
            raise ValueError(f"{field} must be a valid 24-hour time (HH:MM).") from error
    else:
        raise ValueError(f"{field} must be a valid 24-hour time (HH:MM).")
    if parsed.tzinfo is not None:
        raise ValueError(f"{field} cannot include a timezone.")
    return parsed


def _parse_datetime(
    field: str,
    value: Any,
    *,
    required: bool = False,
) -> datetime | None:
    if value is None or _is_blank(value):
        if required:
            raise ValueError(f"{field} is required.")
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError as error:
            raise ValueError(
                f"{field} must be a full ISO date-time, such as 2026-11-10T09:00:00."
            ) from error
    else:
        raise ValueError(f"{field} must be a full date-time.")
    if parsed.tzinfo is not None:
        raise ValueError(f"{field} cannot include a timezone.")
    return parsed


def _validate_enum(field: str, value: str | None, options: frozenset[str]) -> None:
    if value is not None and value not in options:
        allowed = ", ".join(sorted(options))
        raise ValueError(f"{field} must be one of: {allowed}.")


def _check_payload(
    data: dict[str, Any],
    allowed_fields: frozenset[str],
    entity_name: str,
) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{entity_name} data must be a dictionary.")
    if any(not isinstance(field, str) for field in data):
        raise ValueError(f"{entity_name} field names must be strings.")
    unknown = set(data) - allowed_fields
    if unknown:
        raise ValueError(f"Unsupported {entity_name} field(s): {', '.join(sorted(unknown))}.")


def _clean_staff_data(staff_data: dict[str, Any]) -> dict[str, Any]:
    _check_payload(staff_data, _STAFF_EDITABLE, "staff")
    cleaned: dict[str, Any] = {field: None for field in _STAFF_EDITABLE}
    for field, value in staff_data.items():
        if field == "Joining_Date":
            cleaned[field] = _parse_date(field, value)
        else:
            cleaned[field] = _parse_text(
                field,
                value,
                required=(field == "Full_Name"),
            )
    if not cleaned.get("Full_Name"):
        raise ValueError("Full_Name is required.")
    for field, options in _ENUM_FIELDS[STAFF_SHEET].items():
        _validate_enum(field, cleaned.get(field), options)
    return cleaned


def _validate_shift_times(start: time, end: time, crosses_midnight: str) -> None:
    if start == end:
        raise ValueError("Start_Time and End_Time must be different.")
    if crosses_midnight == "Yes" and end >= start:
        raise ValueError(
            "Crosses_Midnight must be Yes only when End_Time is earlier than Start_Time."
        )
    if crosses_midnight == "No" and end <= start:
        raise ValueError(
            "Crosses_Midnight must be No only when End_Time is later than Start_Time."
        )


def _clean_shift_data(shift_data: dict[str, Any]) -> dict[str, Any]:
    _check_payload(shift_data, _SHIFT_EDITABLE, "shift")
    cleaned: dict[str, Any] = {field: None for field in _SHIFT_EDITABLE}
    for field, value in shift_data.items():
        if field in {"Start_Time", "End_Time"}:
            cleaned[field] = _parse_time(field, value, required=True)
        else:
            cleaned[field] = _parse_text(
                field,
                value,
                required=(field == "Shift_Name"),
            )

    cleaned["Shift_Name"] = _parse_text(
        "Shift_Name", cleaned.get("Shift_Name"), required=True
    )
    cleaned["Start_Time"] = _parse_time(
        "Start_Time", cleaned.get("Start_Time"), required=True
    )
    cleaned["End_Time"] = _parse_time(
        "End_Time", cleaned.get("End_Time"), required=True
    )
    if cleaned.get("Crosses_Midnight") is None:
        raise ValueError("Crosses_Midnight is required.")
    if cleaned.get("Shift_Status") is None:
        raise ValueError("Shift_Status is required.")
    _validate_enum(
        "Crosses_Midnight",
        cleaned["Crosses_Midnight"],
        CROSSES_MIDNIGHT_OPTIONS,
    )
    _validate_enum("Shift_Status", cleaned["Shift_Status"], SHIFT_STATUSES)
    _validate_shift_times(
        cleaned["Start_Time"], cleaned["End_Time"], cleaned["Crosses_Midnight"]
    )
    return cleaned


def _clean_assignment_data(assignment_data: dict[str, Any]) -> dict[str, Any]:
    _check_payload(assignment_data, _ASSIGNMENT_EDITABLE, "duty assignment")
    cleaned: dict[str, Any] = {field: None for field in _ASSIGNMENT_EDITABLE}
    for field, value in assignment_data.items():
        if field == "Duty_Date":
            cleaned[field] = _parse_date(field, value, required=True)
        else:
            cleaned[field] = _parse_text(
                field,
                value,
                required=(field in {"Staff_ID", "Shift_ID"}),
            )
    cleaned["Staff_ID"] = _parse_text("Staff_ID", cleaned.get("Staff_ID"), required=True)
    cleaned["Shift_ID"] = _parse_text("Shift_ID", cleaned.get("Shift_ID"), required=True)
    cleaned["Duty_Date"] = _parse_date("Duty_Date", cleaned.get("Duty_Date"), required=True)
    if cleaned.get("Assignment_Status") is None:
        cleaned["Assignment_Status"] = "Assigned"
    _validate_enum(
        "Assignment_Status",
        cleaned["Assignment_Status"],
        ASSIGNMENT_STATUSES,
    )
    return cleaned


def _clean_attendance_data(attendance_data: dict[str, Any]) -> dict[str, Any]:
    _check_payload(attendance_data, _ATTENDANCE_EDITABLE, "attendance")
    cleaned: dict[str, Any] = {field: None for field in _ATTENDANCE_EDITABLE}
    for field, value in attendance_data.items():
        if field == "Duty_Date":
            cleaned[field] = _parse_date(field, value)
        elif field in _DATETIME_FIELDS:
            cleaned[field] = _parse_datetime(field, value)
        else:
            cleaned[field] = _parse_text(
                field,
                value,
                required=(field in {"Assignment_ID", "Staff_ID", "Recorded_By"}),
            )

    cleaned["Assignment_ID"] = _parse_text(
        "Assignment_ID", cleaned.get("Assignment_ID"), required=True
    )
    cleaned["Staff_ID"] = _parse_text(
        "Staff_ID", cleaned.get("Staff_ID"), required=True
    )
    cleaned["Duty_Date"] = _parse_date(
        "Duty_Date", cleaned.get("Duty_Date"), required=True
    )
    cleaned["Recorded_By"] = _parse_text(
        "Recorded_By", cleaned.get("Recorded_By"), required=True
    )
    status = cleaned.get("Attendance_Status")
    if status is None:
        raise ValueError("Attendance_Status is required.")
    _validate_enum("Attendance_Status", status, ATTENDANCE_STATUSES)
    _validate_attendance_timestamps(
        status,
        cleaned.get("Check_In_DateTime"),
        cleaned.get("Check_Out_DateTime"),
    )
    return cleaned


def _validate_attendance_timestamps(
    status: str,
    check_in: datetime | None,
    check_out: datetime | None,
) -> None:
    if status in {"Absent", "On Leave"}:
        if check_in is not None or check_out is not None:
            raise ValueError(
                f"{status} attendance must not include check-in or check-out times."
            )
        return
    if check_in is None:
        raise ValueError(f"Check_In_DateTime is required for {status} attendance.")
    if check_out is not None:
        if check_out <= check_in:
            raise ValueError("Check_Out_DateTime must be later than Check_In_DateTime.")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat(timespec="seconds")
    return value


def _serialize_record(sheet_name: str, record: dict[str, Any]) -> dict[str, Any]:
    headers = SHEET_HEADERS[sheet_name]
    id_field = _ID_FIELDS[sheet_name]
    serialized: dict[str, Any] = {}
    for field in headers:
        value = record.get(field)
        if field in _DATE_FIELDS.get(sheet_name, ()):
            parsed = _parse_date(field, value, required=(field in {"Duty_Date"}))
            serialized[field] = parsed.isoformat() if parsed is not None else None
        elif field in _TIME_FIELDS:
            parsed = _parse_time(field, value, required=True)
            serialized[field] = _serialize_value(parsed)
        elif field in _DATETIME_FIELDS:
            parsed = _parse_datetime(field, value)
            serialized[field] = _serialize_value(parsed) if parsed is not None else None
        else:
            required = field == id_field or (
                sheet_name == STAFF_SHEET and field == "Full_Name"
            )
            serialized[field] = _parse_text(field, value, required=required)

    for field, options in _ENUM_FIELDS.get(sheet_name, {}).items():
        _validate_enum(field, serialized.get(field), options)

    if sheet_name == SHIFTS_SHEET:
        if serialized.get("Crosses_Midnight") is None or serialized.get("Shift_Status") is None:
            raise ValueError("Stored shifts must include Crosses_Midnight and Shift_Status.")
        _validate_shift_times(
            _parse_time("Start_Time", serialized["Start_Time"], required=True),
            _parse_time("End_Time", serialized["End_Time"], required=True),
            serialized["Crosses_Midnight"],
        )
    elif sheet_name == ASSIGNMENTS_SHEET:
        if serialized.get("Assignment_Status") is None:
            raise ValueError("Stored duty assignments must include Assignment_Status.")
        for field in ("Staff_ID", "Shift_ID"):
            _parse_text(field, record.get(field), required=True)
    elif sheet_name == ATTENDANCE_SHEET:
        if serialized.get("Attendance_Status") is None:
            raise ValueError("Stored attendance must include Attendance_Status.")
        if serialized.get("Recorded_By") is None:
            raise ValueError("Stored attendance must include Recorded_By.")
        _validate_attendance_timestamps(
            serialized["Attendance_Status"],
            _parse_datetime("Check_In_DateTime", record.get("Check_In_DateTime")),
            _parse_datetime("Check_Out_DateTime", record.get("Check_Out_DateTime")),
        )
    return serialized


def _scan_records(workbook: Any, sheet_name: str) -> list[tuple[int, dict[str, Any]]]:
    worksheet = workbook[sheet_name]
    headers = SHEET_HEADERS[sheet_name]
    id_field = _ID_FIELDS[sheet_name]
    seen_ids: set[str] = set()
    records: list[tuple[int, dict[str, Any]]] = []
    for row_number, values in enumerate(
        worksheet.iter_rows(
            min_row=2,
            max_col=len(headers),
            values_only=True,
        ),
        start=2,
    ):
        if all(_is_blank(value) for value in values):
            continue
        raw_record = dict(zip(headers, values))
        raw_id = _parse_text(id_field, raw_record.get(id_field), required=True)
        normalized_id = raw_id.casefold()
        if normalized_id in seen_ids:
            raise ValueError(f"Duplicate {id_field} values found in the {sheet_name} sheet.")
        seen_ids.add(normalized_id)
        records.append((row_number, _serialize_record(sheet_name, raw_record)))
    return records


def _validate_workbook_integrity(workbook: Any) -> None:
    """Reject cross-sheet references or attendance links that do not agree."""
    records_by_sheet = {
        sheet_name: _scan_records(workbook, sheet_name)
        for sheet_name in SHEET_HEADERS
    }
    staff_by_id = {
        record["Staff_ID"].casefold(): record
        for _, record in records_by_sheet[STAFF_SHEET]
    }
    shifts_by_id = {
        record["Shift_ID"].casefold(): record
        for _, record in records_by_sheet[SHIFTS_SHEET]
    }
    assignments_by_id = {
        record["Assignment_ID"].casefold(): record
        for _, record in records_by_sheet[ASSIGNMENTS_SHEET]
    }

    for _, assignment in records_by_sheet[ASSIGNMENTS_SHEET]:
        if assignment["Staff_ID"].casefold() not in staff_by_id:
            raise ValueError(
                f"Duty assignment {assignment['Assignment_ID']} references unknown "
                f"Staff_ID {assignment['Staff_ID']}."
            )
        if assignment["Shift_ID"].casefold() not in shifts_by_id:
            raise ValueError(
                f"Duty assignment {assignment['Assignment_ID']} references unknown "
                f"Shift_ID {assignment['Shift_ID']}."
            )

    attendance_assignments: set[str] = set()
    for _, attendance in records_by_sheet[ATTENDANCE_SHEET]:
        normalized_assignment_id = attendance["Assignment_ID"].casefold()
        if normalized_assignment_id in attendance_assignments:
            raise ValueError(
                "More than one attendance record references Assignment_ID "
                f"{attendance['Assignment_ID']}."
            )
        attendance_assignments.add(normalized_assignment_id)

        assignment = assignments_by_id.get(normalized_assignment_id)
        if assignment is None:
            raise ValueError(
                f"Attendance {attendance['Attendance_ID']} references unknown "
                f"Assignment_ID {attendance['Assignment_ID']}."
            )
        shift = shifts_by_id[assignment["Shift_ID"].casefold()]
        _validate_attendance_for_assignment(attendance, assignment, shift)


def _read_records(sheet_name: str) -> list[dict[str, Any]]:
    with _file_lock:
        workbook = _load_workbook(read_only=True, data_only=True)
        try:
            return [record for _, record in _scan_records(workbook, sheet_name)]
        finally:
            workbook.close()


def _normalize_id(value: str, field: str) -> str:
    parsed = _parse_text(field, value, required=True)
    return parsed.casefold()


def _get_record(sheet_name: str, field: str, identifier: str) -> dict[str, Any] | None:
    wanted = _normalize_id(identifier, field)
    for record in _read_records(sheet_name):
        if record[field].casefold() == wanted:
            return record
    return None


def read_staff() -> list[dict[str, Any]]:
    """Read all staff records."""
    return _read_records(STAFF_SHEET)


def list_staff() -> list[dict[str, Any]]:
    """Alias for read_staff()."""
    return read_staff()


def get_staff(staff_id: str) -> dict[str, Any] | None:
    """Return one staff member by case-insensitive Staff_ID."""
    return _get_record(STAFF_SHEET, "Staff_ID", staff_id)


def search_staff(query: str) -> list[dict[str, Any]]:
    """Search by Staff_ID, name, role, department, or contact number."""
    needle = str(query).strip().casefold()
    if not needle:
        return []
    fields = ("Staff_ID", "Full_Name", "Role", "Department", "Contact_Number")
    return [
        staff
        for staff in read_staff()
        if any(needle in str(staff.get(field) or "").casefold() for field in fields)
    ]


def _new_id(existing_ids: set[str], prefix: str, width: int) -> str:
    normalized = {value.casefold() for value in existing_ids}
    pattern = re.compile(rf"{re.escape(prefix)}-(\d+)", re.IGNORECASE)
    sequence = max(
        (int(match.group(1)) for value in existing_ids if (match := pattern.fullmatch(value))),
        default=0,
    ) + 1
    while True:
        candidate = f"{prefix}-{sequence:0{width}d}"
        if candidate.casefold() not in normalized:
            return candidate
        sequence += 1


def _existing_ids(records: list[tuple[int, dict[str, Any]]], field: str) -> set[str]:
    return {record[field] for _, record in records}


def _first_empty_row(worksheet: Any, headers: tuple[str, ...]) -> int:
    for row_number in range(2, worksheet.max_row + 1):
        if all(
            _is_blank(worksheet.cell(row=row_number, column=column).value)
            for column in range(1, len(headers) + 1)
        ):
            return row_number
    return worksheet.max_row + 1


def _prepare_appended_row(worksheet: Any, row_number: int, headers: tuple[str, ...]) -> None:
    if row_number > worksheet.max_row:
        style_source_row = 2 if worksheet.max_row >= 2 else 1
        for column in range(1, len(headers) + 1):
            source = worksheet.cell(row=style_source_row, column=column)
            destination = worksheet.cell(row=row_number, column=column)
            if source.has_style:
                destination._style = copy(source._style)
            if source.number_format:
                destination.number_format = source.number_format

        # Extend column-scoped dropdowns when records exceed the template's
        # preformatted rows, preserving the existing validation rules.
        for validation in worksheet.data_validations.dataValidation:
            updated_ranges = []
            changed = False
            for cell_range in validation.sqref.ranges:
                if (
                    cell_range.min_col == cell_range.max_col
                    and cell_range.min_row <= 2
                    and cell_range.max_row < row_number
                ):
                    updated_ranges.append(
                        CellRange(
                            min_col=cell_range.min_col,
                            min_row=cell_range.min_row,
                            max_col=cell_range.max_col,
                            max_row=row_number,
                        )
                    )
                    changed = True
                else:
                    updated_ranges.append(cell_range)
            if changed:
                validation.sqref = MultiCellRange(updated_ranges)

    # Existing table definitions are preserved by openpyxl, but their ranges
    # must also grow when a record is written beyond the current table bounds.
    for table in worksheet.tables.values():
        table_range = CellRange(table.ref)
        if (
            table_range.min_row != 1
            or table_range.min_col != 1
            or table_range.max_col != len(headers)
            or row_number <= table_range.max_row
        ):
            continue
        table_headers = tuple(
            worksheet.cell(row=1, column=column).value
            for column in range(1, len(headers) + 1)
        )
        if table_headers != headers:
            continue
        if getattr(table, "totalsRowCount", 0):
            raise ValueError(
                f"Cannot append to table {table.displayName!r} while it has a totals row."
            )
        table_range.max_row = row_number
        table.ref = str(table_range)
        if table.autoFilter is not None:
            table.autoFilter.ref = table.ref


def _write_record(
    worksheet: Any,
    row_number: int,
    headers: tuple[str, ...],
    record: dict[str, Any],
) -> None:
    _prepare_appended_row(worksheet, row_number, headers)
    for column, field in enumerate(headers, start=1):
        worksheet.cell(row=row_number, column=column, value=record.get(field))


def _save_workbook(workbook: Any) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"{EXCEL_FILE.stem}.",
            suffix=".xlsx",
            dir=EXCEL_FILE.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        workbook.save(temporary_path)
        os.replace(temporary_path, EXCEL_FILE)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def register_staff(staff_data: dict[str, Any]) -> dict[str, Any]:
    """Validate and append a staff member with a generated Staff_ID."""
    _check_payload(staff_data, _STAFF_EDITABLE, "staff")
    data = dict(staff_data)
    if _is_blank(data.get("Employment_Status")):
        data["Employment_Status"] = "Active"
    cleaned = _clean_staff_data(data)

    with _file_lock:
        workbook = _load_workbook()
        try:
            existing = _scan_records(workbook, STAFF_SHEET)
            staff_id = _new_id(_existing_ids(existing, "Staff_ID"), "STF", 6)
            record = {field: None for field in STAFF_HEADERS}
            record.update(cleaned)
            record["Staff_ID"] = staff_id
            worksheet = workbook[STAFF_SHEET]
            _write_record(
                worksheet,
                _first_empty_row(worksheet, STAFF_HEADERS),
                STAFF_HEADERS,
                record,
            )
            _save_workbook(workbook)
            return _serialize_record(STAFF_SHEET, record)
        finally:
            workbook.close()


def update_staff(staff_id: str, staff_data: dict[str, Any]) -> dict[str, Any] | None:
    """Update supplied staff fields while preserving Staff_ID."""
    _check_payload(staff_data, _STAFF_EDITABLE, "staff")
    wanted = _normalize_id(staff_id, "Staff_ID")
    with _file_lock:
        workbook = _load_workbook()
        try:
            records = _scan_records(workbook, STAFF_SHEET)
            matches = [
                (row_number, record)
                for row_number, record in records
                if record["Staff_ID"].casefold() == wanted
            ]
            if not matches:
                return None
            row_number, existing = matches[0]
            merged = {field: existing.get(field) for field in _STAFF_EDITABLE}
            merged.update(staff_data)
            cleaned = _clean_staff_data(merged)
            if (
                cleaned.get("Employment_Status") != existing.get("Employment_Status")
                and cleaned.get("Employment_Status") != "Active"
            ):
                future_assignments = _future_assignments_for(
                    workbook,
                    staff_id=existing["Staff_ID"],
                )
                if future_assignments:
                    assignment = future_assignments[0]
                    raise ValueError(
                        "Employment status cannot be changed while future or ongoing "
                        f"non-cancelled assignment {assignment['Assignment_ID']} exists."
                    )
            updated = {"Staff_ID": existing["Staff_ID"], **cleaned}
            _write_record(workbook[STAFF_SHEET], row_number, STAFF_HEADERS, updated)
            _save_workbook(workbook)
            return _serialize_record(STAFF_SHEET, updated)
        finally:
            workbook.close()


def read_shifts() -> list[dict[str, Any]]:
    """Read all shift definitions."""
    return _read_records(SHIFTS_SHEET)


def list_shifts() -> list[dict[str, Any]]:
    """Alias for read_shifts()."""
    return read_shifts()


def get_shift(shift_id: str) -> dict[str, Any] | None:
    """Return one shift by case-insensitive Shift_ID."""
    return _get_record(SHIFTS_SHEET, "Shift_ID", shift_id)


def create_shift(shift_data: dict[str, Any]) -> dict[str, Any]:
    """Create a shift with a generated Shift_ID."""
    _check_payload(shift_data, _SHIFT_EDITABLE, "shift")
    data = dict(shift_data)
    if _is_blank(data.get("Shift_Status")):
        data["Shift_Status"] = "Active"
    cleaned = _clean_shift_data(data)

    with _file_lock:
        workbook = _load_workbook()
        try:
            existing = _scan_records(workbook, SHIFTS_SHEET)
            shift_id = _new_id(_existing_ids(existing, "Shift_ID"), "SH", 3)
            record = {field: None for field in SHIFT_HEADERS}
            record.update(cleaned)
            record["Shift_ID"] = shift_id
            worksheet = workbook[SHIFTS_SHEET]
            _write_record(
                worksheet,
                _first_empty_row(worksheet, SHIFT_HEADERS),
                SHIFT_HEADERS,
                record,
            )
            _save_workbook(workbook)
            return _serialize_record(SHIFTS_SHEET, record)
        finally:
            workbook.close()


def update_shift(shift_id: str, shift_data: dict[str, Any]) -> dict[str, Any] | None:
    """Update a shift; its schedule is immutable after it has assignments."""
    _check_payload(shift_data, _SHIFT_EDITABLE, "shift")
    wanted = _normalize_id(shift_id, "Shift_ID")
    with _file_lock:
        workbook = _load_workbook()
        try:
            records = _scan_records(workbook, SHIFTS_SHEET)
            matches = [
                (row_number, record)
                for row_number, record in records
                if record["Shift_ID"].casefold() == wanted
            ]
            if not matches:
                return None
            row_number, existing = matches[0]
            merged = {field: existing.get(field) for field in _SHIFT_EDITABLE}
            merged.update(shift_data)
            cleaned = _clean_shift_data(merged)

            if (
                existing["Shift_Status"] == "Active"
                and cleaned["Shift_Status"] != "Active"
            ):
                future_assignments = _future_assignments_for(
                    workbook,
                    shift_id=existing["Shift_ID"],
                )
                if future_assignments:
                    assignment = future_assignments[0]
                    raise ValueError(
                        "Shift status cannot be changed while future or ongoing "
                        f"non-cancelled assignment {assignment['Assignment_ID']} exists."
                    )

            schedule_changed = any(
                cleaned[field] != _parse_time(field, existing.get(field), required=True)
                for field in ("Start_Time", "End_Time")
            ) or cleaned["Crosses_Midnight"] != existing["Crosses_Midnight"]
            if schedule_changed:
                referenced = any(
                    record["Shift_ID"].casefold() == existing["Shift_ID"].casefold()
                    for _, record in _scan_records(workbook, ASSIGNMENTS_SHEET)
                )
                if referenced:
                    raise ValueError(
                        "A shift's times and Crosses_Midnight cannot change after it "
                        "has duty assignments; create a new shift definition instead."
                    )

            updated = {"Shift_ID": existing["Shift_ID"], **cleaned}
            _write_record(workbook[SHIFTS_SHEET], row_number, SHIFT_HEADERS, updated)
            _save_workbook(workbook)
            return _serialize_record(SHIFTS_SHEET, updated)
        finally:
            workbook.close()


def _find_by_id(
    records: list[tuple[int, dict[str, Any]]],
    field: str,
    identifier: str,
) -> tuple[int, dict[str, Any]] | None:
    wanted = _normalize_id(identifier, field)
    for row_number, record in records:
        if record[field].casefold() == wanted:
            return row_number, record
    return None


def _assignment_interval(
    assignment: dict[str, Any],
    shift: dict[str, Any],
) -> tuple[datetime, datetime]:
    duty_date = _parse_date("Duty_Date", assignment["Duty_Date"], required=True)
    start_time = _parse_time("Start_Time", shift["Start_Time"], required=True)
    end_time = _parse_time("End_Time", shift["End_Time"], required=True)
    start = datetime.combine(duty_date, start_time)
    end_date = duty_date + timedelta(days=1) if shift["Crosses_Midnight"] == "Yes" else duty_date
    end = datetime.combine(end_date, end_time)
    return start, end


def _intervals_overlap(
    first: tuple[datetime, datetime],
    second: tuple[datetime, datetime],
) -> bool:
    # Half-open intervals allow one shift to begin exactly when another ends.
    return first[0] < second[1] and second[0] < first[1]


def _future_assignments_for(
    workbook: Any,
    *,
    staff_id: str | None = None,
    shift_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return matching non-cancelled assignments that have not ended yet."""
    wanted_staff = staff_id.casefold() if staff_id is not None else None
    wanted_shift = shift_id.casefold() if shift_id is not None else None
    shifts = {
        record["Shift_ID"].casefold(): record
        for _, record in _scan_records(workbook, SHIFTS_SHEET)
    }
    now = datetime.now()
    matches = []
    for _, assignment in _scan_records(workbook, ASSIGNMENTS_SHEET):
        if assignment["Assignment_Status"] == "Cancelled":
            continue
        if wanted_staff is not None and assignment["Staff_ID"].casefold() != wanted_staff:
            continue
        if wanted_shift is not None and assignment["Shift_ID"].casefold() != wanted_shift:
            continue
        shift = shifts[assignment["Shift_ID"].casefold()]
        _, end = _assignment_interval(assignment, shift)
        if end > now:
            matches.append(assignment)
    return matches


def read_duty_assignments() -> list[dict[str, Any]]:
    """Read all duty assignments in their stored order."""
    return _read_records(ASSIGNMENTS_SHEET)


def list_duty_assignments() -> list[dict[str, Any]]:
    """Alias for read_duty_assignments()."""
    return read_duty_assignments()


def get_duty_assignment(assignment_id: str) -> dict[str, Any] | None:
    """Return one duty assignment by case-insensitive Assignment_ID."""
    return _get_record(ASSIGNMENTS_SHEET, "Assignment_ID", assignment_id)


def create_duty_assignment(
    assignment_data: dict[str, Any],
) -> dict[str, Any]:
    """Create an append-only assignment after reference and schedule checks."""
    cleaned = _clean_assignment_data(assignment_data)
    with _file_lock:
        workbook = _load_workbook()
        try:
            staff_records = _scan_records(workbook, STAFF_SHEET)
            staff_match = _find_by_id(staff_records, "Staff_ID", cleaned["Staff_ID"])
            if staff_match is None:
                raise ValueError(f"Unknown Staff_ID: {cleaned['Staff_ID']}.")
            staff = staff_match[1]
            if staff.get("Employment_Status") != "Active":
                raise ValueError("Duty assignments can only be made to Active staff.")

            shift_records = _scan_records(workbook, SHIFTS_SHEET)
            shift_match = _find_by_id(shift_records, "Shift_ID", cleaned["Shift_ID"])
            if shift_match is None:
                raise ValueError(f"Unknown Shift_ID: {cleaned['Shift_ID']}.")
            shift = shift_match[1]
            if shift.get("Shift_Status") != "Active":
                raise ValueError("Duty assignments can only use Active shifts.")

            assignments = _scan_records(workbook, ASSIGNMENTS_SHEET)
            normalized_staff = cleaned["Staff_ID"].casefold()
            normalized_shift = cleaned["Shift_ID"].casefold()
            for _, existing in assignments:
                same_slot = (
                    existing["Staff_ID"].casefold() == normalized_staff
                    and existing["Shift_ID"].casefold() == normalized_shift
                    and existing["Duty_Date"] == cleaned["Duty_Date"].isoformat()
                )
                if same_slot:
                    raise ValueError(
                        "A duty assignment already exists for this staff member, "
                        "date, and shift."
                    )

            new_status = cleaned["Assignment_Status"]
            if new_status != "Cancelled":
                new_interval = _assignment_interval(cleaned, shift)
                shift_by_id = {
                    record["Shift_ID"].casefold(): record
                    for _, record in shift_records
                }
                for _, existing in assignments:
                    if (
                        existing["Staff_ID"].casefold() != normalized_staff
                        or existing["Assignment_Status"] == "Cancelled"
                    ):
                        continue
                    existing_shift = shift_by_id.get(existing["Shift_ID"].casefold())
                    if existing_shift is None:
                        raise ValueError(
                            f"Existing assignment {existing['Assignment_ID']} references "
                            f"unknown Shift_ID {existing['Shift_ID']}."
                        )
                    if _intervals_overlap(
                        new_interval,
                        _assignment_interval(existing, existing_shift),
                    ):
                        raise ValueError(
                            f"This shift overlaps duty assignment {existing['Assignment_ID']} "
                            "for the same staff member."
                        )

            assignment_id = _new_id(
                _existing_ids(assignments, "Assignment_ID"), "DA", 6
            )
            record = {field: None for field in ASSIGNMENT_HEADERS}
            record.update(cleaned)
            record["Assignment_ID"] = assignment_id
            worksheet = workbook[ASSIGNMENTS_SHEET]
            _write_record(
                worksheet,
                _first_empty_row(worksheet, ASSIGNMENT_HEADERS),
                ASSIGNMENT_HEADERS,
                record,
            )
            _save_workbook(workbook)
            return _serialize_record(ASSIGNMENTS_SHEET, record)
        finally:
            workbook.close()


def read_attendance() -> list[dict[str, Any]]:
    """Read all attendance records."""
    return _read_records(ATTENDANCE_SHEET)


def list_attendance() -> list[dict[str, Any]]:
    """Alias for read_attendance()."""
    return read_attendance()


def get_attendance(attendance_id: str) -> dict[str, Any] | None:
    """Return one attendance record by case-insensitive Attendance_ID."""
    return _get_record(ATTENDANCE_SHEET, "Attendance_ID", attendance_id)


def _validate_attendance_for_assignment(
    attendance: dict[str, Any],
    assignment: dict[str, Any],
    shift: dict[str, Any],
) -> None:
    if attendance["Staff_ID"].casefold() != assignment["Staff_ID"].casefold():
        raise ValueError("Attendance Staff_ID must match the referenced assignment.")
    attendance_date = _parse_date("Duty_Date", attendance["Duty_Date"], required=True)
    assignment_date = _parse_date("Duty_Date", assignment["Duty_Date"], required=True)
    if attendance_date != assignment_date:
        raise ValueError("Attendance Duty_Date must match the referenced assignment.")

    start, end = _assignment_interval(assignment, shift)
    check_in = _parse_datetime("Check_In_DateTime", attendance.get("Check_In_DateTime"))
    check_out = _parse_datetime("Check_Out_DateTime", attendance.get("Check_Out_DateTime"))
    if check_in is not None and not start <= check_in < end:
        raise ValueError(
            "Check_In_DateTime must fall within the assigned shift, including its "
            "next-day portion for overnight shifts."
        )
    if check_in is not None:
        late_cutoff = start + timedelta(minutes=LATE_GRACE_MINUTES)
        status = attendance["Attendance_Status"]
        if status == "Late" and check_in <= late_cutoff:
            raise ValueError(
                "Late attendance requires a check-in more than "
                f"{LATE_GRACE_MINUTES} minutes after shift start."
            )
        if status == "Present" and check_in > late_cutoff:
            raise ValueError(
                "Check-ins more than "
                f"{LATE_GRACE_MINUTES} minutes after shift start must be marked Late."
            )
    if check_out is not None and (check_in is None or not check_in < check_out <= end):
        raise ValueError(
            "Check_Out_DateTime must be after check-in and no later than the shift end."
        )


def record_attendance(attendance_data: dict[str, Any]) -> dict[str, Any]:
    """Append one attendance record for a valid duty assignment."""
    _check_payload(attendance_data, _ATTENDANCE_EDITABLE, "attendance")
    with _file_lock:
        workbook = _load_workbook()
        try:
            assignments = _scan_records(workbook, ASSIGNMENTS_SHEET)
            assignment_id = _parse_text(
                "Assignment_ID", attendance_data.get("Assignment_ID"), required=True
            )
            assignment_match = _find_by_id(
                assignments, "Assignment_ID", assignment_id
            )
            if assignment_match is None:
                raise ValueError(f"Unknown Assignment_ID: {assignment_id}.")
            assignment = assignment_match[1]
            if assignment["Assignment_Status"] == "Cancelled":
                raise ValueError("Attendance cannot be recorded against a cancelled assignment.")

            shifts = _scan_records(workbook, SHIFTS_SHEET)
            shift_match = _find_by_id(shifts, "Shift_ID", assignment["Shift_ID"])
            if shift_match is None:
                raise ValueError(
                    f"Assignment {assignment_id} references unknown Shift_ID "
                    f"{assignment['Shift_ID']}."
                )
            shift = shift_match[1]

            provided = dict(attendance_data)
            if "Staff_ID" in provided and _normalize_id(provided["Staff_ID"], "Staff_ID") != assignment["Staff_ID"].casefold():
                raise ValueError("Attendance Staff_ID must match the referenced assignment.")
            if "Duty_Date" in provided:
                submitted_date = _parse_date("Duty_Date", provided["Duty_Date"], required=True)
                if submitted_date.isoformat() != assignment["Duty_Date"]:
                    raise ValueError("Attendance Duty_Date must match the referenced assignment.")
            provided["Staff_ID"] = assignment["Staff_ID"]
            provided["Duty_Date"] = assignment["Duty_Date"]
            cleaned = _clean_attendance_data(provided)

            attendance_records = _scan_records(workbook, ATTENDANCE_SHEET)
            for _, existing in attendance_records:
                if existing["Assignment_ID"].casefold() == assignment_id.casefold():
                    raise ValueError(
                        "An attendance record already exists for this Assignment_ID; "
                        "use correct_attendance() with a reason to change it."
                    )

            _validate_attendance_for_assignment(cleaned, assignment, shift)
            attendance_id = _new_id(
                _existing_ids(attendance_records, "Attendance_ID"), "AT", 6
            )
            record = {field: None for field in ATTENDANCE_HEADERS}
            record.update(cleaned)
            record["Attendance_ID"] = attendance_id
            worksheet = workbook[ATTENDANCE_SHEET]
            _write_record(
                worksheet,
                _first_empty_row(worksheet, ATTENDANCE_HEADERS),
                ATTENDANCE_HEADERS,
                record,
            )
            _save_workbook(workbook)
            return _serialize_record(ATTENDANCE_SHEET, record)
        finally:
            workbook.close()


def correct_attendance(
    attendance_id: str,
    attendance_data: dict[str, Any],
    *,
    recorded_by: str,
    correction_reason: str,
) -> dict[str, Any] | None:
    """Correct an attendance row with an explicit actor and reason.

    The workbook has one row per assignment and no audit-log sheet, so this
    records the latest correction metadata on the existing row.
    """
    _check_payload(attendance_data, _ATTENDANCE_EDITABLE, "attendance")
    correction_actor = _parse_text("Recorded_By", recorded_by, required=True)
    reason = _parse_text("Correction_Reason", correction_reason, required=True)
    _normalize_id(attendance_id, "Attendance_ID")

    with _file_lock:
        workbook = _load_workbook()
        try:
            attendance_records = _scan_records(workbook, ATTENDANCE_SHEET)
            match = _find_by_id(attendance_records, "Attendance_ID", attendance_id)
            if match is None:
                return None
            row_number, existing = match

            if (
                "Attendance_ID" in attendance_data
                or (
                    "Assignment_ID" in attendance_data
                    and _normalize_id(attendance_data["Assignment_ID"], "Assignment_ID")
                    != existing["Assignment_ID"].casefold()
                )
            ):
                raise ValueError("An attendance correction cannot change its record or assignment ID.")

            assignments = _scan_records(workbook, ASSIGNMENTS_SHEET)
            assignment_match = _find_by_id(
                assignments, "Assignment_ID", existing["Assignment_ID"]
            )
            if assignment_match is None:
                raise ValueError(
                    f"Attendance {existing['Attendance_ID']} references an unknown assignment."
                )
            assignment = assignment_match[1]
            shifts = _scan_records(workbook, SHIFTS_SHEET)
            shift_match = _find_by_id(shifts, "Shift_ID", assignment["Shift_ID"])
            if shift_match is None:
                raise ValueError(
                    f"Assignment {assignment['Assignment_ID']} references an unknown shift."
                )

            merged = {field: existing.get(field) for field in _ATTENDANCE_EDITABLE}
            merged.update(attendance_data)
            merged["Recorded_By"] = correction_actor
            merged["Correction_Reason"] = reason
            if merged.get("Staff_ID") is None:
                merged["Staff_ID"] = assignment["Staff_ID"]
            if merged.get("Duty_Date") is None:
                merged["Duty_Date"] = assignment["Duty_Date"]
            cleaned = _clean_attendance_data(merged)
            _validate_attendance_for_assignment(cleaned, assignment, shift_match[1])

            updated = {"Attendance_ID": existing["Attendance_ID"], **cleaned}
            _write_record(workbook[ATTENDANCE_SHEET], row_number, ATTENDANCE_HEADERS, updated)
            _save_workbook(workbook)
            return _serialize_record(ATTENDANCE_SHEET, updated)
        finally:
            workbook.close()


__all__ = [
    "ASSIGNMENT_HEADERS",
    "ASSIGNMENT_STATUSES",
    "ASSIGNMENTS_SHEET",
    "ATTENDANCE_HEADERS",
    "ATTENDANCE_SHEET",
    "ATTENDANCE_STATUSES",
    "EMPLOYMENT_STATUSES",
    "EXCEL_FILE",
    "HEADERS",
    "INSTRUCTIONS_SHEET",
    "REQUIRED_SHEETS",
    "SHIFT_HEADERS",
    "SHIFT_STATUSES",
    "SHIFTS_SHEET",
    "STAFF_HEADERS",
    "STAFF_ROLES",
    "STAFF_SHEET",
    "create_duty_assignment",
    "create_shift",
    "correct_attendance",
    "get_attendance",
    "get_duty_assignment",
    "get_shift",
    "get_staff",
    "list_attendance",
    "list_duty_assignments",
    "list_shifts",
    "list_staff",
    "read_attendance",
    "read_duty_assignments",
    "read_shifts",
    "read_staff",
    "record_attendance",
    "register_staff",
    "search_staff",
    "update_shift",
    "update_staff",
]
