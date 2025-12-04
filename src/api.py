from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None


@app.get("/health")
def health_check():
    """Return a simple OK status for readiness/liveness checks."""
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    return {
        "workspace_id": request.workspace_id,
        "question": request.question,
        "role": request.role,
        "answer": "This is a stub answer.",
        "sources": [],
    }