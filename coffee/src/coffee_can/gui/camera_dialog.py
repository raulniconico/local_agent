"""Live camera capture, used to photograph a coffee bag label for OCR
scanning. Imports QtMultimedia at module level -- if that's unavailable in
a given PySide6 build, importing this module raises ImportError, and
callers (bean_dialog.py) catch that to disable "Take Photo" gracefully
without affecting the rest of the app."""

import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class CameraCaptureDialog(QDialog):
    """Live preview with a Capture button. On success, self.captured_path
    points at a JPEG written to a temp file -- the caller (bean_dialog.py's
    OCR scan flow) reads it and is responsible for cleaning it up."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Take a Photo")
        self.resize(640, 520)
        self.captured_path = None

        self._camera = None
        self._capture_session = QMediaCaptureSession()

        self.video_widget = QVideoWidget()
        self._capture_session.setVideoOutput(self.video_widget)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self.capture_btn = QPushButton("Capture")
        self.capture_btn.setProperty("variant", "primary")
        self.capture_btn.clicked.connect(self._capture)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.capture_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self.video_widget, 1)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)

        self._start_camera()

    def _start_camera(self):
        devices = QMediaDevices.videoInputs()
        if not devices:
            self.status_label.setText("No camera found on this system.")
            self.capture_btn.setEnabled(False)
            return
        self._camera = QCamera(devices[0])
        self._capture_session.setCamera(self._camera)
        self._camera.errorOccurred.connect(self._on_camera_error)
        self._camera.start()

    def _on_camera_error(self, _error, message):
        self.status_label.setText(f"Camera error: {message}")
        self.capture_btn.setEnabled(False)

    def _capture(self):
        if self._camera is None:
            return
        # Grabbed straight off the live video frame via QVideoWidget's own
        # window, rather than QImageCapture, so this works with whatever
        # camera backend is present without needing a dedicated still-image
        # pipeline configured.
        pixmap = self.video_widget.grab()
        if pixmap.isNull():
            self.status_label.setText("Capture failed -- try again.")
            return
        fd, path = tempfile.mkstemp(suffix=".jpg", prefix="coffee-can-scan-")
        os.close(fd)
        pixmap.save(path, "JPG")
        self.captured_path = path
        if self._camera is not None:
            self._camera.stop()
        self.accept()

    def closeEvent(self, event):
        if self._camera is not None:
            self._camera.stop()
        super().closeEvent(event)
