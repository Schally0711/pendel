import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, restore, setup
from .api import router as api_router
from .config import get_settings
from .db import any_users, migrate

api = APIRouter(prefix="/api")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Files that must be revalidated on every load so new deployments are picked up
NO_CACHE = {"index.html", "service-worker.js", "manifest.webmanifest", "theme.js"}

mimetypes.add_type("application/manifest+json", ".webmanifest")
CSRF_HEADER = "x-requested-with"
# Credential exchange without a cookie session: nothing a forged cross-site request could abuse
CSRF_EXEMPT = {"/api/auth/token"}
MAX_BODY_BYTES = 1024 * 1024  # all API payloads are small JSON documents …
UPLOAD_PATHS = {"/api/admin/restore", "/api/setup/restore"}  # … except database uploads (own limit)


@api.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    migrate()
    if not any_users():
        setup.announce()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pendel",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.include_router(api)
    app.include_router(api_router)

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        """Cookie-authenticated writes need a custom header, which cross-site forms cannot send.

        Requests with an API token (Authorization header) are not affected.
        """
        if (
            request.method in UNSAFE_METHODS
            and request.url.path.startswith("/api/")
            and "authorization" not in request.headers
            and request.url.path not in CSRF_EXEMPT
            and request.headers.get(CSRF_HEADER) != "pendel"
        ):
            return JSONResponse({"detail": "csrf_header_missing"}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def body_limit(request: Request, call_next):
        """Reject oversized request bodies early (declared Content-Length)."""
        length = request.headers.get("content-length")
        limit = restore.MAX_UPLOAD_BYTES if request.url.path in UPLOAD_PATHS else MAX_BODY_BYTES
        if length and (not length.isdigit() or int(length) > limit):
            return JSONResponse({"detail": "request_too_large"}, status_code=413)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    _mount_spa(app, get_settings().static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA; unknown non-API paths fall back to index.html for client-side routing."""
    index = static_dir / "index.html"
    if not index.is_file():
        return
    app.mount("/_app", StaticFiles(directory=static_dir / "_app"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str) -> FileResponse:
        file = (static_dir / path).resolve()
        if not (path and file.is_file() and file.is_relative_to(static_dir.resolve())):
            file = index
        headers = {"Cache-Control": "no-cache"} if file.name in NO_CACHE else None
        return FileResponse(file, headers=headers)


app = create_app()
