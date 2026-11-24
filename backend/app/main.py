import json
import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .api import (
    analytics,
    auth,
    campaigns,
    contacts,
    gmail,
    mail,
    resumes,
    sent_replies,
    tracking,
)

app = FastAPI(title="OutreachDesk", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONT],
    allow_credentials=True,
    allow_headers=["Content-Type", "X-CSRF-Token"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
)
log = logging.getLogger("outreachdesk")


@app.middleware("http")
async def protect(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
        "origin"
    ) not in {None, config.FRONT}:
        return JSONResponse({"detail": "Untrusted request origin"}, 403)
    response = await call_next(request)
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if response.status_code >= 400:
        route = request.scope.get("route")
        log.info(
            json.dumps(
                {
                    "method": request.method,
                    "route": getattr(route, "path", "unknown"),
                    "status": response.status_code,
                }
            )
        )
    return response


@app.exception_handler(RequestValidationError)
async def validation(request, exc):
    return JSONResponse(
        {
            "detail": "; ".join(
                f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in exc.errors()
            )
        },
        422,
    )


@app.exception_handler(httpx.HTTPError)
async def network(request, exc):
    return JSONResponse(
        {"detail": "Google could not be reached. Check your connection."}, 502
    )


for module in (
    auth,
    contacts,
    resumes,
    campaigns,
    gmail,
    mail,
    analytics,
    tracking,
    sent_replies,
):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
