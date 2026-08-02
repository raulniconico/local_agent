"""Keeping long blocking calls off the GUI thread.

An API request or a local OCR run takes seconds to tens of seconds. Made
from the GUI thread it freezes the whole app -- no repaint, no window
controls -- so callers run one in a QThread and show a busy indicator
(widgets.WalkingCanLoader) meanwhile.

What's shared here is the thread's *lifetime*, not the work: a QThread torn
down while still running aborts the whole process ("QThread: Destroyed while
thread is still running"), and the dialog that started one is routinely
closed long before the call returns. So a running worker is owned by this
module rather than by its dialog, and quitting the app waits for it. Each
caller keeps its own QThread subclass, since mapping failures onto
user-facing messages is specific to what it was doing.
"""

from PySide6.QtCore import QCoreApplication, QThread

# Every worker started via start() and not yet finished.
_ACTIVE = set()

# Long enough to cover the request timeouts the API callers set (currently
# 90s), so a wait here ends by the call returning rather than by expiring.
_SHUTDOWN_WAIT_MS = 95_000

_shutdown_hook_installed = False


def _wait_for_active():
    for worker in list(_ACTIVE):
        worker.wait(_SHUTDOWN_WAIT_MS)


def _install_shutdown_hook():
    """Wired on first use rather than at import: this module is imported (via
    main_window) before app.py constructs the QApplication, so at import time
    there is no instance to connect to yet."""
    global _shutdown_hook_installed
    if _shutdown_hook_installed:
        return
    app = QCoreApplication.instance()
    if app is None:
        return
    app.aboutToQuit.connect(_wait_for_active)
    _shutdown_hook_installed = True


def start(worker: QThread) -> None:
    """Start `worker` and keep a reference to it until it finishes, so it
    survives its starter being garbage collected."""
    _install_shutdown_hook()
    _ACTIVE.add(worker)
    worker.finished.connect(lambda: _ACTIVE.discard(worker))
    worker.start()