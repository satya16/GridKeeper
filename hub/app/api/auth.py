import hmac

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from .. import auth
from ..schemas import LoginRequest, LoginResult

router = APIRouter(tags=["auth"])


@router.post("/api/login", response_model=LoginResult)
def login(body: LoginRequest, response: Response) -> LoginResult:
    """Username isn't collected -- there's only ever been one admin
    password (see auth.require_session's docstring/comment for why this
    replaced HTTP Basic, whose native prompt some real mobile browsers
    don't show at all)."""
    if not hmac.compare_digest(body.password, auth.get_admin_password()):
        raise HTTPException(status_code=401, detail="wrong password")
    auth.create_session(response)
    return LoginResult(ok=True)


@router.post("/api/logout", response_model=LoginResult)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE_NAME),
) -> LoginResult:
    auth.destroy_session(session_token, response)
    return LoginResult(ok=True)


@router.get("/api/session", response_model=LoginResult)
def check_session(_session: str = Depends(auth.require_session)) -> LoginResult:
    """Cheap endpoint for the dashboard to check "am I still logged in"
    on load, without depending on any real data existing yet."""
    return LoginResult(ok=True)
