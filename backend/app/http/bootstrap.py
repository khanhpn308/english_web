"""One-time bootstrap exchange; the trusted browser page is owned by T066."""

from backend.app.http.errors import error_response
from backend.app.http.session import COOKIE_NAME, SESSION_TTL_SECONDS, SessionStore
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field


class BootstrapExchange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    token: str = Field(min_length=1, max_length=128)


router = APIRouter(tags=["bootstrap"])


@router.post("/bootstrap/exchange", status_code=204)
def exchange_bootstrap(request: Request, body: BootstrapExchange) -> Response:
    sessions: SessionStore = request.app.state.sessions
    cookie = sessions.exchange(body.token)
    if cookie is None:
        return error_response(401, "SESSION_INVALID")
    response = Response(status_code=204)
    # Cookie flags follow Starlette's response API; plain loopback HTTP cannot use Secure.
    # Source: https://www.starlette.io/responses/#set-cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=cookie,
        max_age=SESSION_TTL_SECONDS,
        path="/",
        httponly=True,
        samesite="strict",
    )
    return response
