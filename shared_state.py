#!/usr/bin/env python3
"""Thread-safe shared state between camera apps and the web server."""

import threading


class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest_frame_jpeg: bytes | None = None
        self._active_app_name: str | None = None
        self._pending_capture: bool = False
        self._pending_switch: str | None = None

    # --- frame ---

    def get_latest_frame(self) -> bytes | None:
        with self._lock:
            return self._latest_frame_jpeg

    def set_latest_frame(self, jpeg_bytes: bytes | None) -> None:
        with self._lock:
            self._latest_frame_jpeg = jpeg_bytes

    # --- active app ---

    def get_active_app_name(self) -> str | None:
        with self._lock:
            return self._active_app_name

    def set_active_app_name(self, name: str | None) -> None:
        with self._lock:
            self._active_app_name = name

    # --- pending capture ---

    def get_pending_capture(self) -> bool:
        with self._lock:
            return self._pending_capture

    def set_pending_capture(self, value: bool) -> None:
        with self._lock:
            self._pending_capture = value

    # --- pending switch ---

    def get_pending_switch(self) -> str | None:
        with self._lock:
            return self._pending_switch

    def set_pending_switch(self, name: str | None) -> None:
        with self._lock:
            self._pending_switch = name
