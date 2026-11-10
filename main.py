from datetime import date, datetime, time
from urllib.error import URLError
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

import patient_store
import staff_store
from rag_engine import answer_patient_question, answer_question

app = FastAPI(
    title="AI Hospital Information Assistant",
    description="RAG-based hospital information assistant API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1)
    patient_id: str | None = Field(default=None, min_length=1)


class PatientCreateRequest(BaseModel):
    Full_Name: str = Field(..., min_length=1, max_length=32767)
    Date_of_Birth: date | None = None
    Age: int | None = Field(default=None, ge=0, le=150)
    Gender: Literal["Female", "Male", "Other", "Prefer not to say"] | None = None
    Contact_Number: str | None = Field(default=None, max_length=32767)
    Address: str | None = Field(default=None, max_length=32767)
    Emergency_Contact_Name: str | None = Field(default=None, max_length=32767)
    Emergency_Contact_Number: str | None = Field(default=None, max_length=32767)
    Department: str | None = Field(default=None, max_length=32767)
    Doctor_Assigned: str | None = Field(default=None, max_length=32767)
    Registration_Date: date | None = None
    Visit_Type: Literal["OPD", "IPD", "Emergency", "Follow-up"] | None = None
    Record_Status: Literal["Active", "Discharged", "Inactive"] | None = None
    Notes: str | None = Field(default=None, max_length=32767)

    class Config:
        extra = "forbid"


class APIRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StaffFields(APIRequestModel):
    Full_Name: str | None = Field(default=None, max_length=32767)
    Role: str | None = Field(default=None, max_length=32767)
    Department: str | None = Field(default=None, max_length=32767)
    Contact_Number: str | None = Field(default=None, max_length=32767)
    Email: str | None = Field(default=None, max_length=32767)
    Employment_Status: str | None = Field(default=None, max_length=32767)
    Joining_Date: date | None = None
    Notes: str | None = Field(default=None, max_length=32767)


class StaffCreateRequest(StaffFields):
    Full_Name: str = Field(..., min_length=1, max_length=32767)


class StaffUpdateRequest(StaffFields):
    pass


class ShiftFields(APIRequestModel):
    Shift_Name: str | None = Field(default=None, max_length=32767)
    Start_Time: time | None = None
    End_Time: time | None = None
    Crosses_Midnight: str | None = Field(default=None, max_length=32767)
    Description: str | None = Field(default=None, max_length=32767)
    Shift_Status: str | None = Field(default=None, max_length=32767)


class ShiftCreateRequest(ShiftFields):
    Shift_Name: str = Field(..., min_length=1, max_length=32767)
    Start_Time: time
    End_Time: time
    Crosses_Midnight: str = Field(..., min_length=1, max_length=32767)


class ShiftUpdateRequest(ShiftFields):
    pass


class DutyAssignmentFields(APIRequestModel):
    Staff_ID: str | None = Field(default=None, max_length=32767)
    Duty_Date: date | None = None
    Shift_ID: str | None = Field(default=None, max_length=32767)
    Assigned_By: str | None = Field(default=None, max_length=32767)
    Assignment_Status: str | None = Field(default=None, max_length=32767)
    Notes: str | None = Field(default=None, max_length=32767)


class DutyAssignmentCreateRequest(DutyAssignmentFields):
    Staff_ID: str = Field(..., min_length=1, max_length=32767)
    Duty_Date: date
    Shift_ID: str = Field(..., min_length=1, max_length=32767)


class AttendanceFields(APIRequestModel):
    Assignment_ID: str | None = Field(default=None, max_length=32767)
    Staff_ID: str | None = Field(default=None, max_length=32767)
    Duty_Date: date | None = None
    Check_In_DateTime: datetime | None = None
    Check_Out_DateTime: datetime | None = None
    Attendance_Status: str | None = Field(default=None, max_length=32767)
    Recorded_By: str | None = Field(default=None, max_length=32767)
    Correction_Reason: str | None = Field(default=None, max_length=32767)
    Notes: str | None = Field(default=None, max_length=32767)


class AttendanceCreateRequest(AttendanceFields):
    Assignment_ID: str = Field(..., min_length=1, max_length=32767)
    Attendance_Status: str = Field(..., min_length=1, max_length=32767)
    Recorded_By: str = Field(..., min_length=1, max_length=32767)


class AttendanceCorrectionRequest(AttendanceFields):
    Recorded_By: str = Field(..., min_length=1, max_length=32767)
    Correction_Reason: str = Field(..., min_length=1, max_length=32767)


@app.get("/")
def home():
    return {
        "message": "AI Hospital Information Assistant API is running!",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/patients")
def list_patients():
    try:
        return patient_store.list_patients()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Patient record storage is unavailable or invalid.",
        ) from error


@app.get("/patients/search")
def search_patient_records(q: str):
    if not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )
    try:
        return patient_store.search_patients(q)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Patient record storage is unavailable or invalid.",
        ) from error


@app.post("/patients", status_code=201)
def create_patient(request: PatientCreateRequest):
    try:
        patient_data = request.dict(exclude_unset=True)
        return patient_store.register_patient(patient_data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Patient record storage is unavailable.",
        ) from error


@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, request: PatientCreateRequest):
    try:
        patient_data = request.dict(exclude_unset=True)
        updated_patient = patient_store.update_patient(
            patient_id,
            patient_data,
        )
        if updated_patient is None:
            raise HTTPException(
                status_code=404,
                detail="Patient not found.",
            )
        return updated_patient
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Patient record storage is unavailable.",
        ) from error


@app.post("/patients/import")
async def import_patient_records(file: UploadFile = File(...)):
    try:
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail="Please upload a valid .xlsx Excel file.",
            )

        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File size must not exceed 10 MB.",
            )

        return patient_store.import_patients(file_content)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Patient record storage is unavailable.",
        ) from error
    finally:
        await file.close()


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    try:
        patient = patient_store.get_patient(patient_id)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Patient record storage is unavailable or invalid.",
        ) from error

    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


@app.get("/staff")
def list_staff_records():
    try:
        return staff_store.list_staff()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Staff record storage is unavailable or invalid.",
        ) from error


@app.get("/staff/search")
def search_staff_records(q: str):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    try:
        return staff_store.search_staff(q)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Staff record storage is unavailable or invalid.",
        ) from error


@app.get("/staff/{staff_id}")
def get_staff_record(staff_id: str):
    try:
        staff = staff_store.get_staff(staff_id)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Staff record storage is unavailable or invalid.",
        ) from error
    if staff is None:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    return staff


@app.post("/staff", status_code=201)
def create_staff_record(request: StaffCreateRequest):
    try:
        return staff_store.register_staff(request.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Staff record storage is unavailable.",
        ) from error


@app.put("/staff/{staff_id}")
def update_staff_record(staff_id: str, request: StaffUpdateRequest):
    try:
        updated_staff = staff_store.update_staff(
            staff_id,
            request.model_dump(exclude_unset=True),
        )
        if updated_staff is None:
            raise HTTPException(status_code=404, detail="Staff member not found.")
        return updated_staff
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Staff record storage is unavailable.",
        ) from error


@app.get("/shifts")
def list_shift_records():
    try:
        return staff_store.list_shifts()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Shift storage is unavailable or invalid.",
        ) from error


@app.get("/shifts/{shift_id}")
def get_shift_record(shift_id: str):
    try:
        shift = staff_store.get_shift(shift_id)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Shift storage is unavailable or invalid.",
        ) from error
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found.")
    return shift


@app.post("/shifts", status_code=201)
def create_shift_record(request: ShiftCreateRequest):
    try:
        return staff_store.create_shift(request.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Shift storage is unavailable.",
        ) from error


@app.put("/shifts/{shift_id}")
def update_shift_record(shift_id: str, request: ShiftUpdateRequest):
    try:
        updated_shift = staff_store.update_shift(
            shift_id,
            request.model_dump(exclude_unset=True),
        )
        if updated_shift is None:
            raise HTTPException(status_code=404, detail="Shift not found.")
        return updated_shift
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Shift storage is unavailable.",
        ) from error


@app.get("/duty-assignments")
def list_duty_assignment_records():
    try:
        return staff_store.list_duty_assignments()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Duty assignment storage is unavailable or invalid.",
        ) from error


@app.get("/duty-assignments/{assignment_id}")
def get_duty_assignment_record(assignment_id: str):
    try:
        assignment = staff_store.get_duty_assignment(assignment_id)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Duty assignment storage is unavailable or invalid.",
        ) from error
    if assignment is None:
        raise HTTPException(status_code=404, detail="Duty assignment not found.")
    return assignment


@app.post("/duty-assignments", status_code=201)
def create_duty_assignment_record(request: DutyAssignmentCreateRequest):
    try:
        return staff_store.create_duty_assignment(
            request.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Duty assignment storage is unavailable.",
        ) from error


@app.get("/attendance")
def list_attendance_records():
    try:
        return staff_store.list_attendance()
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Attendance storage is unavailable or invalid.",
        ) from error


@app.get("/attendance/{attendance_id}")
def get_attendance_record(attendance_id: str):
    try:
        attendance = staff_store.get_attendance(attendance_id)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Attendance storage is unavailable or invalid.",
        ) from error
    if attendance is None:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
    return attendance


@app.post("/attendance", status_code=201)
def create_attendance_record(request: AttendanceCreateRequest):
    try:
        return staff_store.record_attendance(request.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Attendance storage is unavailable.",
        ) from error


@app.put("/attendance/{attendance_id}")
def update_attendance_record(
    attendance_id: str,
    request: AttendanceCorrectionRequest,
):
    correction = request.model_dump(exclude_unset=True)
    recorded_by = correction.pop("Recorded_By")
    correction_reason = correction.pop("Correction_Reason")
    try:
        updated_attendance = staff_store.correct_attendance(
            attendance_id,
            correction,
            recorded_by=recorded_by,
            correction_reason=correction_reason,
        )
        if updated_attendance is None:
            raise HTTPException(status_code=404, detail="Attendance record not found.")
        return updated_attendance
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Attendance storage is unavailable.",
        ) from error


@app.post("/ask")
def ask(request: QuestionRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")

    if request.patient_id is not None:
        patient_id = request.patient_id.strip()
        if not patient_id:
            raise HTTPException(status_code=422, detail="Patient ID must not be blank.")
        try:
            patient = patient_store.get_patient(patient_id)
        except (OSError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail="Patient record storage is unavailable or invalid.",
            ) from error
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found.")
        try:
            result = answer_patient_question(question, patient)
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail="The patient assistant could not process the question.",
            ) from error
    else:
        try:
            result = answer_question(question)
        except URLError as error:
            raise HTTPException(
                status_code=503,
                detail="Could not connect to the local Ollama service.",
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail="The assistant could not process the question.",
            ) from error

    return {
        "question": question,
        "answer": result["answer"],
        "sources": result["sources"],
        "warnings": result.get("warnings", []),
        "validation_status": result.get("validation_status", "not_applicable"),
    }
