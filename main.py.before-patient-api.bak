from urllib.error import URLError

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


@app.get("/")
def home():
    return {
        "message": "AI Hospital Information Assistant API is running!",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


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
