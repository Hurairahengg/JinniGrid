"""
JINNI Grid Mother Server - Application Factory
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse
from app.config import Config
from app.routes.health import router as health_router
from app.routes.grid import router as grid_router
from app.routes.portfolio import router as portfolio_router
from app.routes.system import router as system_router
from app.routes.strategies import router as strategies_router


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

    app.include_router(health_router)
    app.include_router(grid_router)
    app.include_router(portfolio_router)
    app.include_router(system_router)
    app.include_router(strategies_router)

    ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    css_dir = os.path.join(ui_dir, "css")
    js_dir = os.path.join(ui_dir, "js")

    if os.path.isdir(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.isdir(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    index_path = os.path.join(ui_dir, "index.html")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(index_path)

    return app