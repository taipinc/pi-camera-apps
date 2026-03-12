#!/usr/bin/env python3
"""FastAPI web server for camera control UI."""

import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from shared_state import SharedState

VALID_APP_NAMES = {"dual-cam-raw", "dual-cam-pixmix", "slit-scan-1"}

# Capture directories relative to working dir, mapped to app labels
CAPTURE_DIRS = {
    "raw_captures": "raw",
    "pixmix_captures": "pixmix",
    "slit_scan_test": "slit-scan",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".dng"}

app = FastAPI()

# Module-level reference; set by start_server() before uvicorn.run().
_shared_state: SharedState | None = None
_base_dir: Path | None = None


# ── HTML UI ──────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


# ── API endpoints ────────────────────────────────────────────────────────

@app.get("/status")
def status():
    frame = _shared_state.get_latest_frame()
    return JSONResponse({
        "active_app_name": _shared_state.get_active_app_name(),
        "frame_available": frame is not None,
    })


@app.post("/capture")
def capture():
    _shared_state.set_pending_capture(True)
    return JSONResponse({"ok": True})


@app.post("/switch/{app_name}")
def switch(app_name: str):
    if app_name not in VALID_APP_NAMES:
        return JSONResponse({"ok": False, "error": f"Invalid app name. Valid: {sorted(VALID_APP_NAMES)}"}, status_code=400)
    _shared_state.set_pending_switch(app_name)
    return JSONResponse({"ok": True})


@app.get("/stream")
def stream():
    def generate():
        while True:
            frame = _shared_state.get_latest_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(0.05)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ── Photo gallery ────────────────────────────────────────────────────────

@app.get("/photos")
def list_photos():
    """Return newest-first list of captured images across all capture dirs."""
    photos = []
    for dir_name, app_label in CAPTURE_DIRS.items():
        dir_path = _base_dir / dir_name
        if not dir_path.is_dir():
            continue
        for f in dir_path.iterdir():
            if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file():
                photos.append({
                    "filename": f.name,
                    "path": f"{dir_name}/{f.name}",
                    "modified_timestamp": f.stat().st_mtime,
                    "app": app_label,
                })
    photos.sort(key=lambda p: p["modified_timestamp"], reverse=True)
    return JSONResponse(photos[:10])


@app.get("/photo/{filepath:path}")
def serve_photo(filepath: str):
    """Serve an image file. Only allows paths within known capture directories."""
    # Normalise and resolve to catch traversal attempts
    requested = (_base_dir / filepath).resolve()

    # Must be inside one of the allowed capture dirs
    allowed = False
    for dir_name in CAPTURE_DIRS:
        allowed_root = (_base_dir / dir_name).resolve()
        if str(requested).startswith(str(allowed_root) + os.sep) or requested == allowed_root:
            allowed = True
            break

    if not allowed or not requested.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)

    return FileResponse(requested)


# ── Static assets (CSS/JS if added later) ───────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ── Server entry point ──────────────────────────────────────────────────

def start_server(shared_state: SharedState, host: str = "0.0.0.0", port: int = 8080):
    """Run the FastAPI app with uvicorn. Call this in a daemon thread."""
    global _shared_state, _base_dir
    _shared_state = shared_state
    _base_dir = Path.cwd()

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
