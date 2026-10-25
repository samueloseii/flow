from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.bootstrap import bootstrap
from app.db.migrate import run_migrations
from app.db.session import engine
from app.models import (  # noqa: F401  — ensure all models are registered
    Community,
    Expense,
    Household,
    Invoice,
    MaintenanceRecord,
    Meter,
    MeterReading,
    Partner,
    Payment,
    User,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


def attach_partners_to_organization():
    """Partners created before the organization level existed get a default organization."""
    from app.db.session import SessionLocal
    from app.models.organization import Organization
    from app.models.partner import Partner

    db = SessionLocal()
    try:
        orphans = db.query(Partner).filter(Partner.organization_id.is_(None)).all()
        if not orphans:
            return
        org = db.query(Organization).order_by(Organization.created_at).first()
        if not org:
            org = Organization(name="Main organization")
            db.add(org)
            db.flush()
        for partner in orphans:
            partner.organization_id = org.id
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    bootstrap()
    attach_partners_to_organization()


@app.get("/health")
@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {"status": "healthy", "version": settings.VERSION}


# Serve frontend static files in production
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static")

    # Serve individual static files (manifest, SW, icons) at their exact paths
    for static_file in STATIC_DIR.iterdir():
        if static_file.is_file() and static_file.name != "index.html":
            _name = static_file.name

            def _make_handler(fpath: Path):
                async def _handler():
                    return FileResponse(str(fpath))
                return _handler

            app.get(f"/{_name}", include_in_schema=False)(_make_handler(static_file))

    # SPA fallback — catch any remaining GET that didn't match an API route
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        if request.method == "GET" and not request.url.path.startswith("/api"):
            return FileResponse(str(STATIC_DIR / "index.html"))
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)
