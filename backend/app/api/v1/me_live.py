from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import current_academy_id, require_student
from app.db.session import get_db
from app.models.identity import User
from app.schemas.live import JoinResponse, LiveSessionCard
from app.services import live_sessions as svc

router = APIRouter(prefix="/me/live-sessions", tags=["me:live-sessions"])


@router.get("", response_model=list[LiveSessionCard])
def list_my_sessions(status: str | None = None, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.list_my_sessions(db, academy_id, user, status)


@router.post("/{session_id}/join", response_model=JoinResponse)
def join_session(session_id: int, request: Request, user: User = Depends(require_student), academy_id: int = Depends(current_academy_id), db: Session = Depends(get_db)):
    return svc.join_session(db, academy_id, user, session_id, request)
