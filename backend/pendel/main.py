from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


def create_app() -> FastAPI:
    app = FastAPI(title="Pendel", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.include_router(api)
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
