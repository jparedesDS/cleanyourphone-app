"""Run one blocking service call on a background thread.

Pages keep all Qt widgets and session mutation on the UI thread; a worker only
calls the service and returns its result or exception through queued signals.
This keeps the window repainting while ``adb mdns services``, ``adb pair``,
``adb connect``, ``adb devices`` or a Platform-Tools download are in flight.

A plain Python thread plus a QObject signal bridge is used instead of QThread so
finished workers never race with QThread destruction at window or test teardown.
Emitting a Qt signal from a non-Qt thread is safe: the receiver lives on the UI
thread, so Qt delivers it through a queued connection.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal


class BackgroundCall(QObject):
    """Execute one call at a time on a daemon thread and report the outcome."""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._active = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def start(self, call: Callable[[], Any]) -> bool:
        """Run *call* once; return ``False`` when a call is already active."""
        with self._lock:
            if self._active:
                return False
            self._active = True
        thread = threading.Thread(
            target=self._run,
            args=(call,),
            name="cleanyourphone-worker",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return True

    def _run(self, call: Callable[[], Any]) -> None:
        try:
            result = call()
        except Exception as exc:  # noqa: BLE001 - the page decides how to show it
            self.failed.emit(exc)
        else:
            self.succeeded.emit(result)
        finally:
            with self._lock:
                self._active = False
            self.finished.emit()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Wait briefly for an active call when the window is closing."""
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)


__all__ = ["BackgroundCall"]
