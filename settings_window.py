from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSlider, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

ROLE_LABELS = {
    "broadcaster": "Yayinci",
    "moderator": "Moderator",
    "vip": "VIP",
    "subscriber": "Abone",
    "sub_gifter": "Hediye Eden",
    "og": "OG",
    "founder": "Kurucu",
    "verified": "Onayli",
    "staff": "Kick Ekibi",
}

STYLE_SHEET = """
QWidget { background-color: #17181c; color: #e8e8ea; font-size: 13px; }
QTabWidget::pane { border: 1px solid #2a2b30; border-radius: 8px; top: -1px; }
QTabBar::tab {
    background: #1f2024; padding: 8px 16px; margin-right: 2px; color: #9a9ba3;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #23252b; color: #53FC18; font-weight: 600; }
QLineEdit, QSpinBox, QComboBox {
    background: #1f2024; border: 1px solid #33343a; border-radius: 6px;
    padding: 5px 8px; color: #e8e8ea;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #53FC18; }
QPushButton {
    background: #26282e; border: 1px solid #33343a; border-radius: 6px;
    padding: 8px 14px; color: #e8e8ea;
}
QPushButton:hover { border-color: #53FC18; }
QPushButton:disabled { color: #55565c; }
QPushButton#StartButton { background: #53FC18; color: #0b0c0e; font-weight: 700; border: none; }
QPushButton#StartButton:hover { background: #6bff35; }
QPushButton#StartButton:disabled { background: #2a3a1e; color: #4c5a44; }
QPushButton#StopButton { background: #3a1b1b; color: #ff6b6b; border: 1px solid #5a2b2b; }
QCheckBox { spacing: 8px; }
QSlider::groove:horizontal { height: 6px; background: #2a2b30; border-radius: 3px; }
QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; background: #53FC18; border-radius: 7px; }
QLabel#StatusLabel { color: #9a9ba3; padding: 4px 0; }
QLabel#HintLabel { color: #7d7e86; font-size: 11px; }
"""


class ColorSwatchButton(QPushButton):
    colorChanged = pyqtSignal(str)

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 26)
        self._color = color_hex or "#000000"
        self.clicked.connect(self._pick_color)
        self._refresh()

    def _refresh(self):
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color}; border: 1px solid #33343a; border-radius: 6px; }}"
            "QPushButton:hover { border: 1px solid #53FC18; }"
        )

    def color(self) -> str:
        return self._color

    def set_color(self, color_hex: str):
        self._color = color_hex
        self._refresh()

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Renk Sec")
        if c.isValid():
            self._color = c.name()
            self._refresh()
            self.colorChanged.emit(self._color)


class SettingsWindow(QWidget):
    start_requested = pyqtSignal(dict)
    stop_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)
    move_mode_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()

    def __init__(self, initial_settings: dict):
        super().__init__()
        self.setWindowTitle("Kick Chat Overlay - Ayarlar")
        self.setFixedWidth(400)
        self.settings = dict(initial_settings)
        self._role_checkboxes = {}

        self.setStyleSheet(STYLE_SHEET)

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "Genel")
        tabs.addTab(self._build_appearance_tab(), "Gorunum")
        tabs.addTab(self._build_highlight_tab(), "One Cikanlar")
        tabs.addTab(self._build_filter_tab(), "Filtreler")
        layout.addWidget(tabs)

        self.status_label = QLabel("Hazir.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Baslat")
        self.start_btn.setObjectName("StartButton")
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Durdur")
        self.stop_btn.setObjectName("StopButton")
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        layout.addLayout(btn_row)

        credit_label = QLabel("Made with ❤️ by vicdum")
        credit_label.setObjectName("HintLabel")
        credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credit_label)

    # ---- sekme: genel -----------------------------------------------
    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.username_input = QLineEdit(self.settings.get("username", ""))
        self.username_input.setPlaceholderText("orn: xqc")
        form.addRow("Kick Kullanici Adi:", self.username_input)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setValue(self.settings["font_size"])
        self.font_size_spin.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Yazi Boyutu:", self.font_size_spin)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(self.settings["overlay_opacity"])
        self.opacity_slider.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Genel Opaklik:", self._slider_row(self.opacity_slider, "%"))

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(2, 120)
        self.duration_spin.setValue(self.settings["message_duration"])
        self.duration_spin.setSuffix(" sn")
        self.duration_spin.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Mesaj Kalma Suresi:", self.duration_spin)

        layout.addLayout(form)

        self.move_mode_checkbox = QCheckBox("Pencere Konumunu Ayarla")
        self.move_mode_checkbox.toggled.connect(self.move_mode_toggled.emit)
        layout.addWidget(self.move_mode_checkbox)

        hint = QLabel("Bu kutuyu isaretleyip overlay'i fareyle surukleyerek tasiyabilirsin. "
                      "Bitince isareti kaldir, tiklamalar tekrar oyuna gececek.")
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()
        return tab

    # ---- sekme: gorunum (renkler) ------------------------------------
    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.bg_swatch = ColorSwatchButton(self.settings.get("bg_color", "#000000"))
        self.bg_swatch.colorChanged.connect(self._emit_settings_changed)
        form.addRow("Arka Plan Rengi:", self.bg_swatch)

        self.bg_darkness_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_darkness_slider.setRange(0, 255)
        self.bg_darkness_slider.setValue(self.settings.get("bg_darkness", 140))
        self.bg_darkness_slider.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Arka Plan Koyulugu:", self._slider_row(self.bg_darkness_slider))

        self.text_color_swatch = ColorSwatchButton(self.settings.get("message_text_color", "#ffffff"))
        self.text_color_swatch.colorChanged.connect(self._emit_settings_changed)
        form.addRow("Mesaj Yazi Rengi:", self.text_color_swatch)

        self.username_mode_combo = QComboBox()
        self.username_mode_combo.addItem("Kick Rengini Kullan", "kick")
        self.username_mode_combo.addItem("Ozel Renk", "custom")
        idx = 1 if self.settings.get("username_color_mode") == "custom" else 0
        self.username_mode_combo.setCurrentIndex(idx)
        self.username_mode_combo.currentIndexChanged.connect(self._on_username_mode_changed)
        form.addRow("Kullanici Adi Rengi:", self.username_mode_combo)

        self.username_custom_swatch = ColorSwatchButton(self.settings.get("username_color_custom", "#63f5c2"))
        self.username_custom_swatch.setEnabled(idx == 1)
        self.username_custom_swatch.colorChanged.connect(self._emit_settings_changed)
        form.addRow("Ozel Kullanici Rengi:", self.username_custom_swatch)

        layout.addLayout(form)
        layout.addStretch()
        return tab

    # ---- sekme: one cikanlar (highlight) -----------------------------
    def _build_highlight_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.highlight_enabled_checkbox = QCheckBox("Vurgulamayi Etkinlestir")
        self.highlight_enabled_checkbox.setChecked(self.settings.get("highlight_enabled", True))
        self.highlight_enabled_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.highlight_enabled_checkbox)

        form = QFormLayout()

        self.highlight_users_input = QLineEdit(
            ", ".join(self.settings.get("highlight_users") or [])
        )
        self.highlight_users_input.setPlaceholderText("kullanici1, kullanici2")
        self.highlight_users_input.editingFinished.connect(self._emit_settings_changed)
        form.addRow("Kullanicilar:", self.highlight_users_input)

        self.highlight_color_swatch = ColorSwatchButton(self.settings.get("highlight_color", "#ff9900"))
        self.highlight_color_swatch.colorChanged.connect(self._emit_settings_changed)
        form.addRow("Vurgu Rengi:", self.highlight_color_swatch)

        self.highlight_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_alpha_slider.setRange(0, 255)
        self.highlight_alpha_slider.setValue(self.settings.get("highlight_alpha", 200))
        self.highlight_alpha_slider.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Vurgu Yogunlugu:", self._slider_row(self.highlight_alpha_slider))

        layout.addLayout(form)

        roles_label = QLabel("Rollere Gore Vurgula:")
        layout.addWidget(roles_label)

        roles_grid = QGridLayout()
        active_roles = set(self.settings.get("highlight_roles") or [])
        for i, (key, label) in enumerate(ROLE_LABELS.items()):
            cb = QCheckBox(label)
            cb.setChecked(key in active_roles)
            cb.toggled.connect(self._emit_settings_changed)
            self._role_checkboxes[key] = cb
            roles_grid.addWidget(cb, i // 3, i % 3)
        layout.addLayout(roles_grid)

        layout.addStretch()
        return tab

    # ---- sekme: filtreler ------------------------------------------------
    def _build_filter_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.blocked_keywords_input = QLineEdit(
            ", ".join(self.settings.get("blocked_keywords") or [])
        )
        self.blocked_keywords_input.setPlaceholderText("kelime1, kelime2")
        self.blocked_keywords_input.editingFinished.connect(self._emit_settings_changed)
        form.addRow("Yasakli Kelimeler:", self.blocked_keywords_input)

        self.blocked_users_input = QLineEdit(
            ", ".join(self.settings.get("blocked_users") or [])
        )
        self.blocked_users_input.setPlaceholderText("kullanici1, kullanici2")
        self.blocked_users_input.editingFinished.connect(self._emit_settings_changed)
        form.addRow("Engellenen Kullanicilar:", self.blocked_users_input)

        layout.addLayout(form)

        self.hide_bot_messages_checkbox = QCheckBox("Bot Mesajlarini Gizle")
        self.hide_bot_messages_checkbox.setChecked(self.settings.get("hide_bot_messages", False))
        self.hide_bot_messages_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.hide_bot_messages_checkbox)

        bot_form = QFormLayout()
        self.bot_users_input = QLineEdit(
            ", ".join(self.settings.get("bot_users") or [])
        )
        self.bot_users_input.setPlaceholderText("botrix, kicklet, streamelements")
        self.bot_users_input.editingFinished.connect(self._emit_settings_changed)
        bot_form.addRow("Bot Kullanicilari:", self.bot_users_input)
        layout.addLayout(bot_form)

        bot_hint = QLabel("Kick bot hesaplarini bir 'rozet' olarak isaretlemiyor, "
                           "o yuzden bot adlarini burada elle listele.")
        bot_hint.setObjectName("HintLabel")
        bot_hint.setWordWrap(True)
        layout.addWidget(bot_hint)

        self.hide_bot_commands_checkbox = QCheckBox("Bot Komutlarini Gizle")
        self.hide_bot_commands_checkbox.setChecked(self.settings.get("hide_bot_commands", False))
        self.hide_bot_commands_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.hide_bot_commands_checkbox)

        prefix_form = QFormLayout()
        self.bot_prefix_input = QLineEdit(self.settings.get("bot_command_prefix", "!"))
        self.bot_prefix_input.setFixedWidth(60)
        self.bot_prefix_input.editingFinished.connect(self._emit_settings_changed)
        prefix_form.addRow("Komut On Eki:", self.bot_prefix_input)
        layout.addLayout(prefix_form)

        self.hide_notifications_checkbox = QCheckBox("Abone / Bagis Bildirimlerini Gizle")
        self.hide_notifications_checkbox.setChecked(self.settings.get("hide_notifications", False))
        self.hide_notifications_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.hide_notifications_checkbox)

        layout.addStretch()
        return tab

    # ---- yardimcilar ---------------------------------------------------
    def _slider_row(self, slider: QSlider, suffix: str = "") -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider)
        value_label = QLabel(f"{slider.value()}{suffix}")
        value_label.setFixedWidth(42)
        slider.valueChanged.connect(lambda v: value_label.setText(f"{v}{suffix}"))
        row_layout.addWidget(value_label)
        return row

    def _on_username_mode_changed(self, _index):
        is_custom = self.username_mode_combo.currentData() == "custom"
        self.username_custom_swatch.setEnabled(is_custom)
        self._emit_settings_changed()

    def _on_start_clicked(self):
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Eksik Bilgi", "Lutfen Kick kullanici adini girin.")
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.start_requested.emit(self.current_settings())

    def current_settings(self) -> dict:
        self.settings["username"] = self.username_input.text().strip()
        self.settings["font_size"] = self.font_size_spin.value()
        self.settings["overlay_opacity"] = self.opacity_slider.value()
        self.settings["message_duration"] = self.duration_spin.value()

        self.settings["bg_color"] = self.bg_swatch.color()
        self.settings["bg_darkness"] = self.bg_darkness_slider.value()
        self.settings["message_text_color"] = self.text_color_swatch.color()
        self.settings["username_color_mode"] = self.username_mode_combo.currentData()
        self.settings["username_color_custom"] = self.username_custom_swatch.color()

        self.settings["highlight_enabled"] = self.highlight_enabled_checkbox.isChecked()
        users_raw = self.highlight_users_input.text()
        self.settings["highlight_users"] = [
            u.strip().lower() for u in users_raw.split(",") if u.strip()
        ]
        self.settings["highlight_roles"] = [
            key for key, cb in self._role_checkboxes.items() if cb.isChecked()
        ]
        self.settings["highlight_color"] = self.highlight_color_swatch.color()
        self.settings["highlight_alpha"] = self.highlight_alpha_slider.value()

        keywords_raw = self.blocked_keywords_input.text()
        self.settings["blocked_keywords"] = [
            k.strip().lower() for k in keywords_raw.split(",") if k.strip()
        ]
        blocked_raw = self.blocked_users_input.text()
        self.settings["blocked_users"] = [
            u.strip().lower() for u in blocked_raw.split(",") if u.strip()
        ]
        self.settings["hide_bot_messages"] = self.hide_bot_messages_checkbox.isChecked()
        bot_users_raw = self.bot_users_input.text()
        self.settings["bot_users"] = [
            u.strip().lower() for u in bot_users_raw.split(",") if u.strip()
        ]
        self.settings["hide_bot_commands"] = self.hide_bot_commands_checkbox.isChecked()
        self.settings["bot_command_prefix"] = self.bot_prefix_input.text().strip() or "!"
        self.settings["hide_notifications"] = self.hide_notifications_checkbox.isChecked()

        return self.settings

    def _emit_settings_changed(self, *_):
        self.settings_changed.emit(self.current_settings())

    def set_status(self, text: str):
        self.status_label.setText(text)

    def on_stopped(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.move_mode_checkbox.setChecked(False)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)

    def closeEvent(self, event):
        event.accept()
        self.quit_requested.emit()
