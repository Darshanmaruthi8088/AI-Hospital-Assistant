"""Excel-backed storage for the synthetic hospital patient-record demo."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


EXCEL_FILE = (
    Path(__file__).resolve().parent
    / "data"
    / "patient_records"
    / "hospital_patient_records_template.xlsx"
)
SHEET_NAME = "Patients"
HEADERS = (
    "Patient_ID",
    "Full_Name",
    "Date_of_Birth",
    "Age",
    "Gender",
    "Contact_Number",
    "Address",
    "Emergency_Contact_Name",
    "Emergency_Contact_Number",
    "Department",
    "Doctor_Assigned",
    "Registration_Date",
    "Visit_Type",
    "Record_Status",
    "Notes",
)
EDITABLE_FIELDS = frozenset(HEADERS) - {"Patient_ID"}
DATE_FIELDS = frozenset({"Date_of_Birth", "Registration_Date"})
TEXT_FIELDS = EDITABLE_FIELDS - DATE_FIELDS - {"Age"}
DROPDOWN_OPTIONS = {
    "Gender": {"Female", "Male", "Other", "Prefer not to say"},
    "Visit_Type": {"OPD", "IPD", "Emergency", "Follow-up"},
    "Record_Status": {"Active", "Discharged", "Inactive"},
}

# Protects reads and writes within this Python process. Saves are also written
# to a temporary file and atomically replaced so an interrupted save cannot
# leave a partially written workbook at the configured path.
_file_lock = threading.RLock()


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _validate_headers(worksheet: Any) -> None:
    actual = tuple(
        worksheet.cell(row=1, column=column).value
        for column in range(1, len(HEADERS) + 1)
    )
    extra_header = worksheet.cell(row=1, column=len(HEADERS) + 1).value
    if actual != HEADERS or not _is_blank(extra_header):
        raise ValueError(
            "The Patients sheet headers do not match the expected template. "
            "Keep the template column names and order unchanged."
        )


def _load_sheet(*, read_only: bool = False, data_only: bool = False):
    if not EXCEL_FILE.is_file():
        raise FileNotFoundError(f"Patient-record workbook not found: {EXCEL_FILE}")

    workbook = load_workbook(
        EXCEL_FILE,
        read_only=read_only,
        data_only=data_only,
    )
    try:
        if SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"Workbook is missing the {SHEET_NAME!r} sheet.")
        worksheet = workbook[SHEET_NAME]
        _validate_headers(worksheet)
        return workbook, worksheet
    except Exception:
        workbook.close()
        raise


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized = {field: _serialize_value(value) for field, value in record.items()}
    birth_value = record.get("Date_of_Birth")
    if not _is_blank(birth_value):
        birth_date = _parse_date("Date_of_Birth", birth_value)
        today = date.today()
        if birth_date > today:
            raise ValueError("Date_of_Birth cannot be in the future.")
        calculated_age = _calculate_age(birth_date, today)
        if not 0 <= calculated_age <= 150:
            raise ValueError(
                "Age calculated from Date_of_Birth must be between 0 and 150."
            )
        serialized["Age"] = calculated_age
    return serialized


def read_patients() -> list[dict[str, Any]]:
    """Read all populated patient rows, returning dates as ISO strings."""
    with _file_lock:
        workbook, worksheet = _load_sheet(read_only=True, data_only=True)
        try:
            patients = []
            for values in worksheet.iter_rows(
                min_row=2,
                max_col=len(HEADERS),
                values_only=True,
            ):
                if all(_is_blank(value) for value in values):
                    continue

                patient = dict(zip(HEADERS, values))
                if _is_blank(patient.get("Patient_ID")):
                    raise ValueError(
                        "A populated row in the Patients sheet is missing Patient_ID."
                    )
                patients.append(_serialize_record(patient))
            return patients
        finally:
            workbook.close()


def list_patients() -> list[dict[str, Any]]:
    """Alias suitable for the future GET /patients endpoint."""
    return read_patients()


def get_patient(patient_id: str) -> dict[str, Any] | None:
    """Return the patient with this ID, using a case-insensitive comparison."""
    wanted_id = str(patient_id).strip().casefold()
    if not wanted_id:
        return None
    for patient in read_patients():
        if str(patient["Patient_ID"]).strip().casefold() == wanted_id:
            return patient
    return None


def search_patients(query: str) -> list[dict[str, Any]]:
    """Search patients by ID, name, contact number, department, or doctor."""
    needle = str(query).strip().casefold()
    if not needle:
        return []
    searchable_fields = (
        "Patient_ID",
        "Full_Name",
        "Contact_Number",
        "Department",
        "Doctor_Assigned",
    )
    matching_patients = []
    for patient in read_patients():
        for field in searchable_fields:
            value = str(patient.get(field) or "").casefold()
            if needle in value:
                matching_patients.append(patient)
                break
    return matching_patients


def _parse_date(field: str, value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD format.") from error


def _calculate_age(birth_date: date, as_of: date) -> int:
    return as_of.year - birth_date.year - (
        (as_of.month, as_of.day) < (birth_date.month, birth_date.day)
    )


def _clean_patient_data(patient_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patient_data, dict):
        raise ValueError("Patient data must be a dictionary.")
    if any(not isinstance(field, str) for field in patient_data):
        raise ValueError("Patient field names must be strings.")

    unknown_fields = set(patient_data) - EDITABLE_FIELDS
    if unknown_fields:
        raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown_fields))}")

    cleaned: dict[str, Any] = {}
    for field, value in patient_data.items():
        if field in DATE_FIELDS:
            cleaned[field] = _parse_date(field, value)
        elif field == "Age":
            if _is_blank(value) or not _is_blank(
                patient_data.get("Date_of_Birth")
            ):
                # Date of Birth is authoritative when supplied. The age is
                # recalculated after all fields have been parsed.
                cleaned[field] = None
                continue
            if isinstance(value, bool):
                raise ValueError("Age must be a valid integer.")
            try:
                age = int(value)
            except (TypeError, ValueError) as error:
                raise ValueError("Age must be a valid integer.") from error
            if isinstance(value, float) and value != age:
                raise ValueError("Age must be a valid integer.")
            if isinstance(value, str) and not re.fullmatch(r"\d+", value.strip()):
                raise ValueError("Age must be a valid integer.")
            if not 0 <= age <= 150:
                raise ValueError("Age must be between 0 and 150.")
            cleaned[field] = age
        else:
            if value is None:
                cleaned[field] = None
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field} must be text.")
            text_value = value.strip()
            if len(text_value) > 32767:
                raise ValueError(f"{field} exceeds the Excel cell text limit.")
            cleaned[field] = text_value or None

    full_name = cleaned.get("Full_Name")
    if not isinstance(full_name, str) or not full_name:
        raise ValueError("Patient full name is required.")

    birth_date = cleaned.get("Date_of_Birth")
    if birth_date is not None:
        if birth_date > date.today():
            raise ValueError("Date_of_Birth cannot be in the future.")
        calculated_age = _calculate_age(birth_date, date.today())
        if not 0 <= calculated_age <= 150:
            raise ValueError("Age calculated from Date_of_Birth must be between 0 and 150.")
        cleaned["Age"] = calculated_age

    if cleaned.get("Registration_Date") is None:
        cleaned["Registration_Date"] = date.today()

    for field, allowed_values in DROPDOWN_OPTIONS.items():
        value = cleaned.get(field)
        if value is not None and value not in allowed_values:
            allowed = ", ".join(sorted(allowed_values))
            raise ValueError(f"{field} must be one of: {allowed}.")

    return cleaned


def _generate_patient_id(existing_ids: set[str]) -> str:
    normalized_ids = {patient_id.casefold() for patient_id in existing_ids}
    sequence_numbers = []
    for patient_id in existing_ids:
        match = re.fullmatch(r"PAT-(\d+)", patient_id.strip(), flags=re.IGNORECASE)
        if match:
            sequence_numbers.append(int(match.group(1)))

    sequence = max(sequence_numbers, default=0) + 1
    while True:
        patient_id = f"PAT-{sequence:06d}"
        if patient_id.casefold() not in normalized_ids:
            return patient_id
        sequence += 1


def _existing_ids_and_next_row(worksheet: Any) -> tuple[set[str], int]:
    existing_ids: set[str] = set()
    normalized_ids: set[str] = set()

    for row_index in range(2, worksheet.max_row + 1):
        values = [
            worksheet.cell(row=row_index, column=column).value
            for column in range(1, len(HEADERS) + 1)
        ]
        if all(_is_blank(value) for value in values):
            return existing_ids, row_index

        raw_id = values[0]
        if _is_blank(raw_id):
            raise ValueError(
                f"Populated row {row_index} in the Patients sheet is missing Patient_ID."
            )
        patient_id = str(raw_id).strip()
        normalized_id = patient_id.casefold()
        if normalized_id in normalized_ids:
            raise ValueError("The Patients sheet already contains duplicate patient IDs.")
        existing_ids.add(patient_id)
        normalized_ids.add(normalized_id)

    return existing_ids, worksheet.max_row + 1


def _save_workbook(workbook: Any) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"{EXCEL_FILE.stem}.",
            suffix=".xlsx",
            dir=EXCEL_FILE.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

        workbook.save(temp_path)
        os.replace(temp_path, EXCEL_FILE)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def register_patient(patient_data: dict[str, Any]) -> dict[str, Any]:
    """Validate and append a patient, generating its ID and registration date."""
    cleaned_data = _clean_patient_data(patient_data)

    with _file_lock:
        workbook, worksheet = _load_sheet()
        try:
            existing_ids, row_index = _existing_ids_and_next_row(worksheet)
            patient_id = _generate_patient_id(existing_ids)
            record = {field: None for field in HEADERS}
            record.update(cleaned_data)
            record["Patient_ID"] = patient_id

            for column, field in enumerate(HEADERS, start=1):
                worksheet.cell(row=row_index, column=column, value=record[field])

            _save_workbook(workbook)
            return _serialize_record(record)
        finally:
            workbook.close()


def update_patient(
    patient_id: str,
    patient_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Update supplied fields for an existing patient without changing its ID."""
    if not isinstance(patient_data, dict):
        raise ValueError("Patient data must be a dictionary.")
    if any(not isinstance(field, str) for field in patient_data):
        raise ValueError("Patient field names must be strings.")

    unknown_fields = set(patient_data) - EDITABLE_FIELDS
    if unknown_fields:
        raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown_fields))}")

    target_id = str(patient_id).strip().casefold()
    if not target_id:
        return None

    with _file_lock:
        workbook, worksheet = _load_sheet()
        try:
            target_row = None
            for row_index in range(2, worksheet.max_row + 1):
                current_id = worksheet.cell(row=row_index, column=1).value
                if (
                    not _is_blank(current_id)
                    and str(current_id).strip().casefold() == target_id
                ):
                    if target_row is not None:
                        raise ValueError(
                            "Duplicate patient IDs found in the workbook."
                        )
                    target_row = row_index

            if target_row is None:
                return None

            # Read the existing record.
            existing_record = {
                field: worksheet.cell(row=target_row, column=column).value
                for column, field in enumerate(HEADERS, start=1)
            }

            # Merge supplied changes with existing information.
            merged_data = {
                field: existing_record[field]
                for field in EDITABLE_FIELDS
            }
            merged_data.update(patient_data)

            # Date of Birth is authoritative, so validation recalculates Age
            # for every update, including updates to unrelated fields.
            cleaned_data = _clean_patient_data(merged_data)
            updated_record = {
                "Patient_ID": existing_record["Patient_ID"]
            }
            updated_record.update(cleaned_data)

            # Update the existing Excel row.
            for column, field in enumerate(HEADERS, start=1):
                cell = worksheet.cell(row=target_row, column=column)
                cell.value = updated_record[field]

            _save_workbook(workbook)
            return _serialize_record(updated_record)
        finally:
            workbook.close()


def import_patients(file_content: bytes) -> dict[str, Any]:
    """Import valid patient records from an uploaded Excel workbook."""
    if not file_content:
        raise ValueError("The uploaded Excel file is empty.")

    try:
        source_workbook = load_workbook(
            BytesIO(file_content),
            read_only=True,
            data_only=True,
        )
    except Exception as error:
        raise ValueError("Unable to read the uploaded Excel file.") from error

    imported_records: list[tuple[int, dict[str, Any]]] = []
    skipped = 0
    errors: list[dict[str, Any]] = []

    try:
        if SHEET_NAME not in source_workbook.sheetnames:
            raise ValueError("Uploaded workbook must contain a Patients sheet.")

        source_sheet = source_workbook[SHEET_NAME]
        source_headers = tuple(
            source_sheet.cell(row=1, column=column).value
            for column in range(1, len(HEADERS) + 1)
        )
        extra_header = source_sheet.cell(row=1, column=len(HEADERS) + 1).value
        if source_headers != HEADERS or not _is_blank(extra_header):
            raise ValueError(
                "Uploaded Excel headers do not match the hospital patient template."
            )

        for row_number, values in enumerate(
            source_sheet.iter_rows(
                min_row=2,
                max_col=len(HEADERS),
                values_only=True,
            ),
            start=2,
        ):
            if all(_is_blank(value) for value in values):
                continue

            raw_patient_id = values[0]
            if not isinstance(raw_patient_id, str) or not raw_patient_id.strip():
                skipped += 1
                errors.append(
                    {
                        "row": row_number,
                        "error": "Patient_ID must be non-empty text.",
                    }
                )
                continue

            patient_id = raw_patient_id.strip()
            source_record = dict(zip(HEADERS, values))
            patient_data = {
                field: source_record[field]
                for field in EDITABLE_FIELDS
            }

            try:
                cleaned_data = _clean_patient_data(patient_data)
            except ValueError as error:
                skipped += 1
                errors.append(
                    {
                        "row": row_number,
                        "patient_id": patient_id,
                        "error": str(error),
                    }
                )
                continue

            imported_records.append(
                (
                    row_number,
                    {
                        "Patient_ID": patient_id,
                        **cleaned_data,
                    },
                )
            )
    finally:
        source_workbook.close()

    imported = 0
    with _file_lock:
        workbook, worksheet = _load_sheet()
        try:
            existing_ids: set[str] = set()
            for row_number in range(2, worksheet.max_row + 1):
                values = [
                    worksheet.cell(row=row_number, column=column).value
                    for column in range(1, len(HEADERS) + 1)
                ]
                if all(_is_blank(value) for value in values):
                    continue

                raw_patient_id = values[0]
                if _is_blank(raw_patient_id):
                    raise ValueError(
                        f"Populated row {row_number} in the Patients sheet "
                        "is missing Patient_ID."
                    )

                patient_id = str(raw_patient_id).strip()
                normalized_id = patient_id.casefold()
                if normalized_id in existing_ids:
                    raise ValueError(
                        "The Patients sheet already contains duplicate patient IDs."
                    )
                existing_ids.add(normalized_id)

            next_row = worksheet.max_row + 1
            for row_number, record in imported_records:
                patient_id = record["Patient_ID"]
                normalized_id = patient_id.casefold()
                if normalized_id in existing_ids:
                    skipped += 1
                    errors.append(
                        {
                            "row": row_number,
                            "patient_id": patient_id,
                            "error": "Duplicate Patient_ID; row skipped.",
                        }
                    )
                    continue

                for column, field in enumerate(HEADERS, start=1):
                    worksheet.cell(
                        row=next_row,
                        column=column,
                        value=record[field],
                    )
                existing_ids.add(normalized_id)
                imported += 1
                next_row += 1

            if imported:
                _save_workbook(workbook)
        finally:
            workbook.close()

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }


def migrate_patient_ages() -> dict[str, Any]:
    """Correct stored ages from DOB after creating a timestamped workbook backup.

    This migration is opt-in and is not called during normal reads or API
    requests. It makes no workbook changes when there are no ages to correct.
    """
    with _file_lock:
        workbook, worksheet = _load_sheet()
        try:
            today = date.today()
            patient_id_column = HEADERS.index("Patient_ID") + 1
            birth_date_column = HEADERS.index("Date_of_Birth") + 1
            age_column = HEADERS.index("Age") + 1
            corrections: list[tuple[int, int]] = []
            unchanged = 0
            without_birth_date = 0

            for row_number in range(2, worksheet.max_row + 1):
                values = [
                    worksheet.cell(row=row_number, column=column).value
                    for column in range(1, len(HEADERS) + 1)
                ]
                if all(_is_blank(value) for value in values):
                    continue

                if _is_blank(values[patient_id_column - 1]):
                    raise ValueError(
                        f"Populated row {row_number} is missing Patient_ID."
                    )

                raw_birth_date = values[birth_date_column - 1]
                if _is_blank(raw_birth_date):
                    without_birth_date += 1
                    continue

                try:
                    birth_date = _parse_date("Date_of_Birth", raw_birth_date)
                except ValueError as error:
                    raise ValueError(
                        f"Invalid Date_of_Birth in row {row_number}: {error}"
                    ) from error

                if birth_date is None:
                    without_birth_date += 1
                    continue
                if birth_date > today:
                    raise ValueError(
                        f"Date_of_Birth in row {row_number} cannot be in the future."
                    )

                calculated_age = _calculate_age(birth_date, today)
                if not 0 <= calculated_age <= 150:
                    raise ValueError(
                        f"Calculated age in row {row_number} must be between 0 and 150."
                    )

                current_age = values[age_column - 1]
                if type(current_age) is int and current_age == calculated_age:
                    unchanged += 1
                else:
                    corrections.append((row_number, calculated_age))

            backup_path: Path | None = None
            if corrections:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                backup_path = EXCEL_FILE.with_name(
                    f"{EXCEL_FILE.stem}.age-backup-{timestamp}{EXCEL_FILE.suffix}"
                )
                suffix = 1
                while backup_path.exists():
                    backup_path = EXCEL_FILE.with_name(
                        f"{EXCEL_FILE.stem}.age-backup-{timestamp}-{suffix}"
                        f"{EXCEL_FILE.suffix}"
                    )
                    suffix += 1

                # Keep an untouched copy before changing any workbook cells.
                shutil.copy2(EXCEL_FILE, backup_path)
                for row_number, calculated_age in corrections:
                    worksheet.cell(row=row_number, column=age_column).value = (
                        calculated_age
                    )
                _save_workbook(workbook)

            return {
                "updated": len(corrections),
                "unchanged": unchanged,
                "without_birth_date": without_birth_date,
                "backup": str(backup_path) if backup_path is not None else None,
            }
        finally:
            workbook.close()


__all__ = [
    "EDITABLE_FIELDS",
    "EXCEL_FILE",
    "HEADERS",
    "get_patient",
    "import_patients",
    "list_patients",
    "migrate_patient_ages",
    "read_patients",
    "register_patient",
    "update_patient",
    "search_patients",
]
