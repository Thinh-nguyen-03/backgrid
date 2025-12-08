"""UI routes using Jinja2 templates"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()

# Set up templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/")
async def home(request: Request):
    """
    Render the home page UI.

    Args:
        request: FastAPI request object (required for templates)

    Returns:
        TemplateResponse with the index.html template
    """
    return templates.TemplateResponse("index.html", {"request": request})
