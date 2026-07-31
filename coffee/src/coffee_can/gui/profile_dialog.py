"""Dialog for editing the local user's profile (name, email, avatar photo)."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import profile
from .widgets import circular_pixmap

_AVATAR_SIZE = 96
_AVATAR_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class ProfileSettingsDialog(QDialog):
    """Edits the single app-wide profile.py record. A newly picked or removed
    photo is only staged in memory -- it's copied in / deleted from disk in
    _save() -- so clicking Cancel never touches the existing avatar file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profile Settings")
        self.resize(380, 340)

        data = profile.load_profile()
        self._current_image_path = data.get("image_path")
        self._pending_image_source = None  # Path, if the user just picked a new photo
        self._pending_remove = False  # True if the user clicked Remove Photo

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_avatar_preview()

        change_photo_btn = QPushButton("Change Photo...")
        change_photo_btn.clicked.connect(self._choose_image)
        remove_photo_btn = QPushButton("Remove Photo")
        remove_photo_btn.clicked.connect(self._remove_image)
        avatar_buttons = QHBoxLayout()
        avatar_buttons.addWidget(change_photo_btn)
        avatar_buttons.addWidget(remove_photo_btn)

        avatar_col = QVBoxLayout()
        avatar_col.addWidget(self.avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)
        avatar_col.addLayout(avatar_buttons)

        self.name_edit = QLineEdit(data.get("name") or "")
        self.email_edit = QLineEdit(data.get("email") or "")
        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Email", self.email_edit)

        save_btn = QPushButton("Save")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(avatar_col)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(buttons)

    def _staged_image_path(self):
        if self._pending_remove:
            return None
        if self._pending_image_source is not None:
            return str(self._pending_image_source)
        return self._current_image_path

    def _update_avatar_preview(self):
        path = self._staged_image_path()
        pixmap = circular_pixmap(path, _AVATAR_SIZE) if path and Path(path).exists() else QPixmap()
        if pixmap.isNull():
            self.avatar_label.setPixmap(QPixmap())
            self.avatar_label.setText("No Photo")
            self.avatar_label.setStyleSheet(
                f"background-color: #D7F5DE; border-radius: {_AVATAR_SIZE // 2}px; color: #34C759;"
            )
        else:
            self.avatar_label.setPixmap(pixmap)
            self.avatar_label.setText("")
            self.avatar_label.setStyleSheet("")

    def _choose_image(self):
        suffixes = " ".join(f"*{s}" for s in sorted(_AVATAR_SUFFIXES))
        path, _ = QFileDialog.getOpenFileName(self, "Select a profile photo", "", f"Images ({suffixes})")
        if not path:
            return
        self._pending_image_source = Path(path)
        self._pending_remove = False
        self._update_avatar_preview()

    def _remove_image(self):
        self._pending_image_source = None
        self._pending_remove = True
        self._update_avatar_preview()

    def _save(self):
        name = self.name_edit.text().strip()
        email = self.email_edit.text().strip()

        if self._pending_image_source is not None:
            image_path = profile.set_avatar(self._pending_image_source)
        elif self._pending_remove:
            profile.clear_avatar()
            image_path = None
        else:
            image_path = self._current_image_path

        profile.save_profile(name, email, image_path)
        self.accept()
