from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router as api_router
from .config import get_settings
from .db import migrate

api = APIRouter(prefix="/api")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-requested-with"


@api.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    migrate()
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
            and request.headers.get(CSRF_HEADER) != "pendel"
        ):
            return JSONResponse({"detail": "csrf_header_missing"}, status_code=403)
        return await call_next(request)

    _mount_spa(app, get_settings().static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA; unknown non-API paths fall back to index.html for client-side routing."""
    index = static_dir / "index.html"
    if not index.is_file():
        return
    app.mount("/_app", StaticFiles(directory=static_dir / "_app"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        file = (static_dir / path).resolve()
        if path and file.is_file() and file.is_relative_to(static_dir.resolve()):
            return FileResponse(file)
        return FileResponse(index)


app = create_app()
