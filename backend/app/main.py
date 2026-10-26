"""Minimal FastAPI entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from uuid import UUID, uuid4
from app.services.chat_jobs import chat_jobs, ChatJobError
from pydantic import BaseModel, Field
from app.rag.generate import ChatError, get_rag_service
from app.rag.pinecone_store import PineconeOperationError
from app.graph.workflow import get_agent_service

app = FastAPI(title="Creator Studio Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "application": "Creator Studio Copilot"}


# Lazy provider initialization keeps /health independent of external credentials.


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    strategy: Literal['A','B','C'] = 'B'
    top_k: int = Field(default=5, ge=1, le=10)


@app.post('/ask')
def ask(request: AskRequest):
    try:
        return get_rag_service().answer(request.question,request.strategy,request.top_k)
    except ValueError:
        raise HTTPException(status_code=400,detail='Invalid request or missing service configuration') from None
    except (ChatError,PineconeOperationError):
        raise HTTPException(status_code=503,detail='Knowledge service is temporarily unavailable') from None


class ChatRequest(BaseModel):
    request_id: UUID | None = None
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    equipment: list[str] | None = Field(default=None, max_length=12)


@app.post('/chat')
def chat(request: ChatRequest):
    try:
        if request.request_id:
            return chat_job(request).future.result()
        return get_agent_service().chat(request.message, request.session_id, request.equipment)
    except ChatJobError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from None
    except KeyError:
        raise HTTPException(status_code=404, detail='Session not found') from None
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid request or missing service configuration') from None
    except (ChatError, PineconeOperationError):
        raise HTTPException(status_code=503, detail='Assistant is temporarily unavailable') from None


def chat_job(request):
    signature = (request.message, request.session_id, tuple(request.equipment or []))
    return chat_jobs.get_or_start(str(request.request_id or uuid4()), signature,
        lambda: get_agent_service().chat(request.message, request.session_id, request.equipment))


@app.post('/chat/stream')
def chat_stream(request: ChatRequest):
    try:
        job = chat_job(request)
    except ChatJobError as error:
        raise HTTPException(status_code=error.status, detail=str(error)) from None
    return StreamingResponse(job.events_since_start(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.get('/sessions/{session_id}')
def session(session_id: str):
    try:
        return get_agent_service().session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Session not found') from None
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid session or missing service configuration') from None
    except (ChatError, PineconeOperationError):
        raise HTTPException(status_code=503, detail='Assistant is temporarily unavailable') from None
