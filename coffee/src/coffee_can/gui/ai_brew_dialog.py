"""Dialog for the bean page's "Ask AI" button: pick a dripper and optionally
a dose, ask Qwen for a brewing recipe suggestion for this bean, review it,
then Create Session -- which hands the parsed recipe (dripper, summary, dose, grind
size, pour stages) back to the caller (BeanDialog._ask_ai_brew) to persist
as a real session with real brew_stages rows, then opens the normal
BrewDialog for further editing. See qwen_brew_suggest.py for the actual API call
and the JSON shape it returns."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import qwen_brew_suggest
from ..formatting import format_seconds
from . import background
from .widgets import DripperCombo, WalkingCanLoader


class _SuggestionWorker(QThread):
    """Runs one qwen_brew_suggest.suggest_brew() call off the GUI thread -- a
    blocking HTTPS round-trip that regularly takes tens of seconds. See
    background.py for why the thread isn't owned by the dialog."""

    succeeded = Signal(dict)  # not `finished`: QThread already defines that
    failed = Signal(str, str)  # (message box title, message)

    def __init__(self, bean_info: dict, dripper: str, dose_g: float | None):
        super().__init__()
        self._bean_info = bean_info
        self._dripper = dripper
        self._dose_g = dose_g

    def run(self):
        try:
            result = qwen_brew_suggest.suggest_brew(
                self._bean_info, self._dripper, self._dose_g
            )
        except qwen_brew_suggest.QwenBrewUnavailableError as exc:
            self.failed.emit("AI suggestion unavailable", str(exc))
        except Exception as exc:  # noqa: BLE001 -- network/SDK errors vary
            self.failed.emit("Request failed", f"Couldn't get a suggestion: {exc}")
        else:
            self.succeeded.emit(result)


class AiBrewSuggestionDialog(QDialog):
    def __init__(self, bean_row, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ask AI -- {bean_row['name'] or 'this bean'}")
        self.resize(480, 460)
        self._bean_row = bean_row
        self._result = None  # qwen_brew_suggest.suggest_brew()'s parsed dict, once fetched
        self._worker = None

        self.dripper = None
        self.suggestion = None
        self.dose_g = None
        self.grind_size = None
        self.stages = []

        self.dripper_combo = DripperCombo()

        # Same range/step/suffix as BrewDialog's dose field, so the number
        # means the same thing in both places. 0 is the special case: it
        # reads "auto" and leaves the dose to Qwen, which is what this
        # dialog did before the field existed -- so the default keeps the
        # old behaviour rather than pushing a made-up 15 g on anyone.
        self.dose_spin = QDoubleSpinBox()
        self.dose_spin.setRange(0, 100)
        self.dose_spin.setSuffix(" g")
        self.dose_spin.setSingleStep(0.5)
        self.dose_spin.setValue(0)
        self.dose_spin.setSpecialValueText("auto")
        self.dose_spin.setToolTip("Leave on 'auto' to let the AI choose the dose")

        self.ask_btn = QPushButton("Get Suggestion")
        self.ask_btn.setProperty("variant", "primary")
        self.ask_btn.clicked.connect(self._ask)

        self.loader = WalkingCanLoader()
        self.loader.hide()

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self.suggestion_edit = QPlainTextEdit()
        self.suggestion_edit.setPlaceholderText("The AI's brewing suggestion will appear here...")
        self.suggestion_edit.setReadOnly(True)

        self.create_btn = QPushButton("Create Session")
        self.create_btn.setProperty("variant", "primary")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._create_session)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        # A grid rather than two QHBoxLayouts: the two labels have to share a
        # column to line up, and the ask button spans both rows because it
        # acts on both fields, not just the dripper it would otherwise sit
        # beside. The spin box is left-aligned at its natural width -- a dose
        # stretched to the combo's width reads as a field expecting a long
        # value, which two digits are not.
        top_grid = QGridLayout()
        top_grid.addWidget(QLabel("Dripper"), 0, 0)
        top_grid.addWidget(self.dripper_combo, 0, 1)
        top_grid.addWidget(QLabel("Dose"), 1, 0)
        top_grid.addWidget(self.dose_spin, 1, 1, Qt.AlignmentFlag.AlignLeft)
        top_grid.addWidget(self.ask_btn, 0, 2, 2, 1)
        top_grid.setColumnStretch(1, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.create_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(top_grid)
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

    @staticmethod
    def _render(result: dict) -> str:
        lines = [result["summary"] or "(no explanation returned)", ""]
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

    def _ask(self):
        dripper = self.dripper_combo.text().strip()
        if not dripper:
            QMessageBox.information(self, "Pick a dripper", "Choose a dripper first.")
            return

        self.ask_btn.setEnabled(False)
        self.create_btn.setEnabled(False)
        self._result = None
        self.suggestion_edit.setPlainText("")
        self.status_label.setText("Torrefying...")
        self.loader.show()

        worker = _SuggestionWorker(self._bean_info(), dripper, self.dose_spin.value() or None)
        self._worker = worker
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        background.start(worker)

    def _finish_request(self):
        self._worker = None
        self.loader.hide()
        self.status_label.setText("")
        self.ask_btn.setEnabled(True)

    def _on_succeeded(self, result: dict):
        self._finish_request()
        self._result = result
        self.suggestion_edit.setPlainText(self._render(result))
        self.create_btn.setEnabled(True)

    def _on_failed(self, title: str, message: str):
        self._finish_request()
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event):
        # The request keeps running to completion in the background (there's
        # no way to cancel an in-flight SDK call), but its signals must stop
        # reaching a dialog that's on its way out.
        if self._worker is not None:
            self._worker.succeeded.disconnect(self._on_succeeded)
            self._worker.failed.disconnect(self._on_failed)
            self._worker = None
        super().closeEvent(event)

    def _create_session(self):
        if self._result is None:
            return
        self.dripper = self.dripper_combo.text().strip()
        self.suggestion = self._result["summary"]
        self.dose_g = self._result["dose_g"]
        self.grind_size = self._result["grind_size"]
        self.stages = self._result["stages"]
        self.accept()
