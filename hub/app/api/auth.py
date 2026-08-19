from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import auth
from ..audit import record_audit
from ..db import User
from ..deps import get_db
from ..schemas import LoginRequest, LoginResult, PasswordChangeRequest, UserOut

router = APIRouter(tags=["auth"])


@router.post("/api/login", response_model=LoginResult)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResult:
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="wrong username or password")
    auth.create_session(response, user.id)
    return LoginResult(ok=True, role=user.role)


@router.post("/api/logout", response_model=LoginResult)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE_NAME),
) -> LoginResult:
    auth.destroy_session(session_token, response)
    return LoginResult(ok=True)


@router.get("/api/session", response_model=LoginResult)
def check_session(user: User = Depends(auth.require_session)) -> LoginResult:
    """Cheap endpoint for the dashboard to check "am I still logged in" on
    load, and which role's nav to show -- without depending on any real
    data existing yet."""
    return LoginResult(ok=True, role=user.role)


@router.get("/api/me", response_model=UserOut)
def get_me(user: User = Depends(auth.require_session)) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role, scope=user.scope, created_at=user.created_at.isoformat())


@router.post("/api/me/password", response_model=LoginResult)
def change_own_password(
    body: PasswordChangeRequest,
    user: User = Depends(auth.require_session),
    db: Session = Depends(get_db),
) -> LoginResult:
    if not auth.verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="wrong current password")
    user.password_hash = auth.hash_password(body.new_password)
    db.commit()
    record_audit(db, user, "change_own_password", target=user.username)
    return LoginResult(ok=True, role=user.role)
