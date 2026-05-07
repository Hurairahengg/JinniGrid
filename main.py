"""
JINNI GRID - Mother Server Entry Point
Run: python main.py
"""

import os
import uvicorn

from app import create_app
from app.config import Config


# App instance at module level so uvicorn reloader can find it
app = create_app()


def main():
    server_config = Config.get_server_config()
    app_config = Config.get_app_config()

    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 5100)
    debug = server_config.get("debug", False)
    name = app_config.get("name", "JINNI GRID Mother Server")
    version = app_config.get("version", "0.2.0")

    print("")
    print("=" * 56)
    print(f"  {name} v{version}")
    print("=" * 56)
    print(f"  Dashboard:   http://{host}:{port}")
    print(f"  API docs:    http://{host}:{port}/docs")
    print(f"  Debug mode:  {debug}")
    print("=" * 56)
    print("")

    run_kwargs = {"host": host, "port": port, "reload": debug}

    if debug:
        # ── RELOAD FIX ───────────────────────────────────────
        # The old approach used reload_excludes with glob patterns
        # like "data/*" — but PurePath.match() does NOT recursively
        # match "data/strategies/foo.py", so every strategy upload
        # still triggered a full server reload.
        #
        # Fix: whitelist ONLY source directories via reload_dirs.
        # Writes to data/strategies/ (uploads), data/ (future DB),
        # or strategies/ (legacy) can never trigger the watcher.
        #
        # Trade-off: changes to main.py or config.yaml require a
        # manual restart. That's fine — config is cached anyway.
        project_root = os.path.dirname(os.path.abspath(__file__))
        run_kwargs["reload_dirs"] = [
            os.path.join(project_root, "app"),
            os.path.join(project_root, "ui"),
        ]

    uvicorn.run("main:app", **run_kwargs)


if __name__ == "__main__":
    main()