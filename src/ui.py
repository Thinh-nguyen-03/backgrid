"""UI routes serving the built frontend"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()

dist_dir = Path(__file__).parent.parent / "frontend" / "dist"


@router.get("/")
async def serve_spa():
    """Serve the SPA index.html from the built frontend."""
    index_path = dist_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    # Fallback to legacy template
    templates_dir = Path(__file__).parent / "templates"
    return FileResponse(str(templates_dir / "index.html"))


def mount_static_files(app):
    """Mount static assets on the FastAPI app instance.
    Must be called on the app directly since StaticFiles doesn't work on APIRouter.
    """
    from fastapi.staticfiles import StaticFiles
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
