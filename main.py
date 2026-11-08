from datetime import date
from typing import Literal
from urllib.error import URLError

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import patient_store
from rag_engine import answer_question

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


@app.post("/ask")
def ask(request: QuestionRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be blank.")

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
