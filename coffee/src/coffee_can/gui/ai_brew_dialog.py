"""Dialog for the bean page's "Ask AI" button: pick a dripper, ask DeepSeek
for a brewing recipe suggestion for this bean, review it, then Create
Session -- which hands the parsed recipe (dripper, summary, dose, grind
size, pour stages) back to the caller (BeanDialog._ask_ai_brew) to persist
as a real session with real brew_stages rows, then opens the normal
BrewDialog for further editing. See deepseek_brew.py for the actual API call
and the JSON shape it returns."""

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import deepseek_brew
from ..formatting import format_seconds
from .widgets import DripperCombo


class AiBrewSuggestionDialog(QDialog):
    def __init__(self, bean_row, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ask AI -- {bean_row['name'] or 'this bean'}")
        self.resize(480, 460)
        self._bean_row = bean_row
        self._result = None  # deepseek_brew.suggest_brew()'s parsed dict, once fetched

        self.dripper = None
        self.suggestion = None
        self.dose_g = None
        self.grind_size = None
        self.stages = []

        self.dripper_combo = DripperCombo()

        self.ask_btn = QPushButton("Get Suggestion")
        self.ask_btn.setProperty("variant", "primary")
        self.ask_btn.clicked.connect(self._ask)

        self.status_label = QLabel("")
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

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Dripper"))
        top_row.addWidget(self.dripper_combo, 1)
        top_row.addWidget(self.ask_btn)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.create_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(top_row)
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
        self.status_label.setText("Asking DeepSeek...")
        QApplication.processEvents()  # paint the status text before the blocking request

        try:
            result = deepseek_brew.suggest_brew(self._bean_info(), dripper)
        except deepseek_brew.DeepSeekUnavailableError as exc:
            self.status_label.setText("")
            self.ask_btn.setEnabled(True)
            QMessageBox.warning(self, "AI suggestion unavailable", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 -- network/SDK errors vary
            self.status_label.setText("")
            self.ask_btn.setEnabled(True)
            QMessageBox.warning(self, "Request failed", f"Couldn't get a suggestion: {exc}")
            return

        self.status_label.setText("")
        self.ask_btn.setEnabled(True)
        self._result = result
        self.suggestion_edit.setPlainText(self._render(result))
        self.create_btn.setEnabled(True)

    def _create_session(self):
        if self._result is None:
            return
        self.dripper = self.dripper_combo.text().strip()
        self.suggestion = self._result["summary"]
        self.dose_g = self._result["dose_g"]
        self.grind_size = self._result["grind_size"]
        self.stages = self._result["stages"]
        self.accept()
