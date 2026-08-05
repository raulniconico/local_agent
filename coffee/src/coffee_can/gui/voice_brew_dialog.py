"""Dialog for the sessions section's voice-recording button: record a short
clip of the user describing a brew out loud, send it to Qwen-Omni for audio
understanding, review the parsed session + stages, then Create Session --
same downstream shape as ai_brew_dialog.py's text flow, just sourced from
a microphone instead of a dripper pick + text suggestion. See qwen_brew.py
for the actual API call and the JSON shape it returns.

Imports QtMultimedia at module level -- if that's unavailable in a given
PySide6 build, importing this module raises ImportError, and the caller
(bean_dialog.py) catches that to disable the voice-session button gracefully,
same as camera_dialog.py's "Take Photo" path.
"""

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
)
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import qwen_brew
from ..formatting import format_seconds
from . import background
from .widgets import WalkingCanLoader


class _TranscribeWorker(QThread):
    """Runs one qwen_brew.transcribe_brew_session() call off the GUI thread --
    a blocking HTTPS round-trip that regularly takes tens of seconds. See
    background.py for why the thread isn't owned by the dialog."""

    succeeded = Signal(dict)  # not `finished`: QThread already defines that
    failed = Signal(str, str)  # (message box title, message)

    def __init__(self, audio_bytes: bytes, audio_format: str, bean_info: dict):
        super().__init__()
        self._audio_bytes = audio_bytes
        self._audio_format = audio_format
        self._bean_info = bean_info

    def run(self):
        try:
            result = qwen_brew.transcribe_brew_session(
                self._audio_bytes, self._audio_format, self._bean_info
            )
        except qwen_brew.QwenUnavailableError as exc:
            self.failed.emit("Voice session unavailable", str(exc))
        except Exception as exc:  # noqa: BLE001 -- network/SDK errors vary
            self.failed.emit("Request failed", f"Couldn't parse the recording: {exc}")
        else:
            self.succeeded.emit(result)


class VoiceBrewDialog(QDialog):
    def __init__(self, bean_row, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Voice Session -- {bean_row['name'] or 'this bean'}")
        self.resize(480, 480)
        self._bean_row = bean_row
        self._result = None  # qwen_brew.transcribe_brew_session()'s parsed dict, once fetched
        self._worker = None
        self._temp_path = None
        self._stopping = False  # True between us calling stop() and the recorder confirming it

        self.dripper = None
        self.suggestion = None
        self.dose_g = None
        self.grind_size = None
        self.stages = []

        self._audio_input = QAudioInput()
        self._capture_session = QMediaCaptureSession()
        self._capture_session.setAudioInput(self._audio_input)
        self._recorder = QMediaRecorder()
        self._capture_session.setRecorder(self._recorder)
        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
        media_format.setAudioCodec(QMediaFormat.AudioCodec.Wave)
        self._recorder.setMediaFormat(media_format)
        self._recorder.recorderStateChanged.connect(self._on_recorder_state_changed)
        self._recorder.errorOccurred.connect(self._on_recorder_error)

        has_mic = bool(QMediaDevices.audioInputs())

        self.mic_btn = QPushButton("🎤 Start Recording")
        self.mic_btn.setProperty("variant", "primary")
        self.mic_btn.setEnabled(has_mic)
        self.mic_btn.clicked.connect(self._toggle_recording)

        self.loader = WalkingCanLoader()
        self.loader.hide()

        self.status_label = QLabel(
            "No microphone found on this system."
            if not has_mic
            else "Press the microphone and describe the brew out loud -- "
            "dripper, dose, grind size, and each pour."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self.suggestion_edit = QPlainTextEdit()
        self.suggestion_edit.setPlaceholderText("What Qwen understood from the recording will appear here...")
        self.suggestion_edit.setReadOnly(True)

        self.create_btn = QPushButton("Create Session")
        self.create_btn.setProperty("variant", "primary")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._create_session)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        mic_row = QHBoxLayout()
        mic_row.addStretch()
        mic_row.addWidget(self.mic_btn)
        mic_row.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.create_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(mic_row)
        layout.addWidget(self.loader)
        layout.addWidget(self.status_label)
        layout.addWidget(self.suggestion_edit, 1)
        layout.addLayout(buttons)

    def _bean_info(self) -> dict:
        return {
            "Name": self._bean_row["name"],
            "Origin": self._bean_row["origin"],
            "Variety": self._bean_row["variety"],
            "Altitude": self._bean_row["altitude"],
            "Roaster": self._bean_row["roaster"],
            "Producer": self._bean_row["producer"],
            "Process": self._bean_row["process"],
            "Roast date": self._bean_row["roast_date"],
        }

    # --- recording -------------------------------------------------------

    def _toggle_recording(self):
        if self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self._stopping = True
            self._recorder.stop()
        else:
            self._start_recording()

    def _start_recording(self):
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="coffee-can-voice-")
        os.close(fd)
        self._temp_path = path
        self._recorder.setOutputLocation(QUrl.fromLocalFile(path))
        self._result = None
        self.suggestion_edit.setPlainText("")
        self.create_btn.setEnabled(False)
        self._recorder.record()

    def _on_recorder_state_changed(self, state):
        # setProperty("variant", ...) alone doesn't repaint an already-shown
        # widget -- the app's stylesheet keys off that property, and Qt only
        # re-evaluates stylesheet rules on unpolish()/polish(), not on every
        # property change.
        if state == QMediaRecorder.RecorderState.RecordingState:
            self.mic_btn.setText("⏹ Stop Recording")
            self.mic_btn.setProperty("variant", "destructive")
            self.mic_btn.style().unpolish(self.mic_btn)
            self.mic_btn.style().polish(self.mic_btn)
            self.status_label.setText("Recording -- press Stop Recording when you're done.")
        elif state == QMediaRecorder.RecorderState.StoppedState:
            self.mic_btn.setText("🎤 Start Recording")
            self.mic_btn.setProperty("variant", "primary")
            self.mic_btn.style().unpolish(self.mic_btn)
            self.mic_btn.style().polish(self.mic_btn)
            if self._stopping:
                self._stopping = False
                self._transcribe()

    def _on_recorder_error(self, _error, message):
        self._stopping = False
        QMessageBox.warning(self, "Recording failed", message)

    # --- transcription -----------------------------------------------------

    def _transcribe(self):
        path = Path(self._temp_path) if self._temp_path else None
        self._temp_path = None
        if path is None or not path.exists() or path.stat().st_size == 0:
            if path is not None:
                path.unlink(missing_ok=True)
            self.status_label.setText("No audio was captured -- try again.")
            return

        audio_bytes = path.read_bytes()
        path.unlink(missing_ok=True)

        self.mic_btn.setEnabled(False)
        self.status_label.setText("Torrefying...")
        self.loader.show()

        worker = _TranscribeWorker(audio_bytes, "wav", self._bean_info())
        self._worker = worker
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        background.start(worker)

    def _finish_request(self):
        self._worker = None
        self.loader.hide()
        self.status_label.setText("")
        self.mic_btn.setEnabled(bool(QMediaDevices.audioInputs()))

    @staticmethod
    def _render(result: dict) -> str:
        lines = []
        if result["dripper"]:
            lines.append(f"Dripper: {result['dripper']}")
        lines.append(result["summary"] or "(no additional notes)")
        lines.append("")
        dose = f"{result['dose_g']:g} g" if result["dose_g"] is not None else "(not specified)"
        lines.append(f"Dose: {dose}")
        lines.append(f"Grind: {result['grind_size'] or '(not specified)'}")
        if result["stages"]:
            lines.append("Stages:")
            for i, stage in enumerate(result["stages"], 1):
                temp = f"{stage['temperature_c']:g}°C" if stage["temperature_c"] is not None else "?"
                water = f"{stage['water_g']:g}g" if stage["water_g"] is not None else "?"
                duration = format_seconds(stage["time_seconds"])
                circling = stage["circling"] or "none"
                lines.append(f"  {i}. {temp}, {water} water, {duration}, {circling}")
        else:
            lines.append("Stages: (none returned)")
        return "\n".join(lines)

    def _on_succeeded(self, result: dict):
        self._finish_request()
        self._result = result
        self.suggestion_edit.setPlainText(self._render(result))
        self.create_btn.setEnabled(True)

    def _on_failed(self, title: str, message: str):
        self._finish_request()
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event):
        if self._recorder.recorderState() != QMediaRecorder.RecorderState.StoppedState:
            self._stopping = False  # closing, not restarting the mic button
            self._recorder.stop()
        # The request keeps running to completion in the background (there's
        # no way to cancel an in-flight SDK call), but its signals must stop
        # reaching a dialog that's on its way out.
        if self._worker is not None:
            self._worker.succeeded.disconnect(self._on_succeeded)
            self._worker.failed.disconnect(self._on_failed)
            self._worker = None
        if self._temp_path:
            Path(self._temp_path).unlink(missing_ok=True)
            self._temp_path = None
        super().closeEvent(event)

    def _create_session(self):
        if self._result is None:
            return
        self.dripper = self._result["dripper"] or None
        self.suggestion = self._result["summary"]
        self.dose_g = self._result["dose_g"]
        self.grind_size = self._result["grind_size"]
        self.stages = self._result["stages"]
        self.accept()