"""
JINNI Grid Mother Server - Application Factory
app/__init__.py
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import Config
from app.routes.mainRoutes import router as main_routes_router


def create_app() -> FastAPI:
    app_config = Config.get_app_config()
    cors_origins = Config.get_cors_origins()

    app = FastAPI(
        title=app_config["name"],
        version=app_config["version"],
        description="JINNI Grid Mother Server - Integrated Dashboard + Fleet API",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(main_routes_router)

    ui_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "ui")
    )

    css_dir = os.path.join(ui_dir, "css")
    js_dir = os.path.join(ui_dir, "js")
    index_path = os.path.join(ui_dir, "index.html")

    if os.path.isdir(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.isdir(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(index_path)

    # ── Initialize persistence ───────────────────────────────
    from app.persistence import init_db
    init_db()

    # ── Restore strategies from disk ─────────────────────────
    from app.services.strategy_registry import load_strategies_from_disk
    load_strategies_from_disk()

    # ── Load workers from DB into memory cache ───────────────
    from app.services.mainServices import _load_workers_from_db
    _load_workers_from_db()

    return app