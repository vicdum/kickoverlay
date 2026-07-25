from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog, QFormLayout,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

import notify_sound
from logger import LOG_PATH, get_logger, open_log_folder
from turkish import tr_fold

log = get_logger("settings")

FONT_WEIGHT_LABELS = [
    ("Çok İnce", 100),
    ("İnce", 300),
    ("Normal", 400),
    ("Orta", 500),
    ("Yarı Kalın", 600),
    ("Kalın", 700),
    ("Çok Kalın", 800),
    ("Siyah", 900),
]

ROLE_LABELS = {
    "broadcaster": "Yayıncı",
    "moderator": "Moderatör",
    "vip": "VIP",
    "subscriber": "Abone",
    "sub_gifter": "Hediye Eden",
    "og": "OG",
    "founder": "Kurucu",
    "verified": "Onaylı",
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
QLabel#SectionLabel {
    color: #53FC18; font-weight: 600; padding-top: 10px;
    border-top: 1px solid #2a2b30; margin-top: 6px;
}
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: #1b1c21; width: 10px; margin: 0; border-radius: 5px;
}
QScrollBar::handle:vertical { background: #3a3c44; min-height: 24px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #53FC18; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

# Sekme icerigi ekrandan uzun olabildigi icin her sekme kaydirilabilir bir
# alana konur; bu deger kaydirmaya gerek olmadan gorunen en az yuksekliktir.
TAB_MIN_HEIGHT = 470


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
        c = QColorDialog.getColor(QColor(self._color), self, "Renk Seç")
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
        # 400 px'de uzun Turkce etiketler combo/spinbox alanlarini
        # okunamayacak kadar sikistiriyordu.
        self.setFixedWidth(460)
        self.settings = dict(initial_settings)
        self._role_checkboxes = {}

        self.setStyleSheet(STYLE_SHEET)

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.setMinimumHeight(TAB_MIN_HEIGHT)
        tabs.addTab(self._scrollable(self._build_general_tab()), "Genel")
        tabs.addTab(self._scrollable(self._build_appearance_tab()), "Görünüm")
        tabs.addTab(self._scrollable(self._build_highlight_tab()), "Öne Çıkanlar")
        tabs.addTab(self._scrollable(self._build_mention_tab()), "Etiket")
        tabs.addTab(self._scrollable(self._build_filter_tab()), "Filtreler")
        layout.addWidget(tabs)

        # Soluklastirma tum sekmeler kurulduktan sonra: bu cagrilar
        # _emit_settings_changed tetiklemez, sadece enabled durumunu duzeltir.
        self._sync_mention_widgets()

        self.status_label = QLabel("Hazır.")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Başlat")
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

        self._fit_to_screen()

    # ---- yerlesim yardimcilari -----------------------------------------
    def _scrollable(self, inner: QWidget) -> QWidget:
        """Sekmeyi kaydirilabilir alana sarar.

        Ayar sayisi arttikca sekmeler kucuk ekranlarda (1366x768 gibi)
        tasiyordu; alt taraftaki Baslat/Durdur dugmeleri ekran disinda
        kaliyordu.
        """
        area = QScrollArea()
        area.setWidget(inner)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return area

    def _fit_to_screen(self):
        """Pencereyi ekrana sigacak yuksekliğe ayarlar."""
        try:
            screen = QApplication.primaryScreen()
            available = screen.availableGeometry().height() if screen else 900
            wanted = self.sizeHint().height()
            self.resize(self.width(), min(wanted, max(400, int(available * 0.92))))
        except Exception as exc:
            log.debug("pencere boyutu ayarlanamadi: %s", exc)

    # ---- sekme: genel -----------------------------------------------
    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()
        self.username_input = QLineEdit(self.settings.get("username", ""))
        self.username_input.setPlaceholderText("örn: MuratAbiGF")
        form.addRow("Kick Kullanıcı Adı:", self.username_input)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(self.settings["overlay_opacity"])
        self.opacity_slider.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Genel Opaklık:", self._slider_row(self.opacity_slider, "%"))

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(2, 120)
        self.duration_spin.setValue(self.settings["message_duration"])
        self.duration_spin.setSuffix(" sn")
        self.duration_spin.valueChanged.connect(self._emit_settings_changed)
        form.addRow("Mesaj Kalma Süresi:", self.duration_spin)

        layout.addLayout(form)

        self.move_mode_checkbox = QCheckBox("Pencere Konumunu Ayarla")
        self.move_mode_checkbox.toggled.connect(self.move_mode_toggled.emit)
        layout.addWidget(self.move_mode_checkbox)

        hint = QLabel("Bu kutuyu işaretleyip overlay'i fareyle sürükleyerek taşıyabilirsin. "
                      "Bitince işareti kaldır, tıklamalar tekrar oyuna geçecek.")
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()
        layout.addWidget(self._build_log_section())
        return tab

    # ---- tanilama / log bolumu -----------------------------------------
    def _build_log_section(self) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 8, 0, 0)

        self.debug_logs_checkbox = QCheckBox("Ayrıntılı log (sorun bildirirken aç)")
        self.debug_logs_checkbox.setChecked(self.settings.get("debug_logs", False))
        self.debug_logs_checkbox.toggled.connect(self._emit_settings_changed)
        box_layout.addWidget(self.debug_logs_checkbox)

        log_btn = QPushButton("Log Klasörünü Aç")
        log_btn.clicked.connect(self._open_logs)
        box_layout.addWidget(log_btn)

        log_hint = QLabel(f"Uygulama beklenmedik şekilde kapanırsa log dosyasındaki "
                          f"son satırlar sebebi gösterir:\n{LOG_PATH}")
        log_hint.setObjectName("HintLabel")
        log_hint.setWordWrap(True)
        box_layout.addWidget(log_hint)
        return box

    def _open_logs(self):
        if not open_log_folder():
            QMessageBox.information(self, "Log Klasörü",
                                    f"Klasör açılamadı. Yolu elle kopyalayabilirsin:\n{LOG_PATH}")

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
        form.addRow("Arka Plan Koyuluğu:", self._slider_row(self.bg_darkness_slider))

        self.text_color_swatch = ColorSwatchButton(self.settings.get("message_text_color", "#ffffff"))
        self.text_color_swatch.colorChanged.connect(self._emit_settings_changed)
        form.addRow("Mesaj Yazı Rengi:", self.text_color_swatch)

        self.username_mode_combo = QComboBox()
        self.username_mode_combo.addItem("Kick Rengini Kullan", "kick")
        self.username_mode_combo.addItem("Özel Renk", "custom")
        idx = 1 if self.settings.get("username_color_mode") == "custom" else 0
        self.username_mode_combo.setCurrentIndex(idx)
        self.username_mode_combo.currentIndexChanged.connect(self._on_username_mode_changed)
        form.addRow("Kullanıcı Adı Rengi:", self.username_mode_combo)

        self.username_custom_swatch = ColorSwatchButton(self.settings.get("username_color_custom", "#63f5c2"))
        self.username_custom_swatch.setEnabled(idx == 1)
        self.username_custom_swatch.colorChanged.connect(self._emit_settings_changed)
        form.addRow("Özel Kullanıcı Rengi:", self.username_custom_swatch)

        layout.addLayout(form)
        layout.addWidget(self._build_font_section())
        layout.addStretch()
        return tab

    # ---- yazi tipi bolumu ----------------------------------------------
    def _build_font_section(self) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Yazı Tipi")
        title.setObjectName("SectionLabel")
        box_layout.addWidget(title)

        form = QFormLayout()

        self.font_family_combo = QComboBox()
        self.font_family_combo.addItem("Sistem Varsayılanı", "")
        for family in QFontDatabase.families():
            self.font_family_combo.addItem(family, family)
        saved_family = self.settings.get("font_family") or ""
        family_idx = self.font_family_combo.findData(saved_family)
        if family_idx < 0:
            # kaydedilen yazi tipi bu bilgisayarda kurulu degil
            log.warning("yazi tipi bulunamadi (%r) - varsayilana donuluyor", saved_family)
            family_idx = 0
        self.font_family_combo.setCurrentIndex(family_idx)
        self.font_family_combo.setMinimumWidth(200)
        form.addRow("Yazı Tipi:", self.font_family_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 48)
        self.font_size_spin.setValue(self.settings.get("font_size", 16))
        self.font_size_spin.setSuffix(" px")
        form.addRow("Yazı Boyutu:", self.font_size_spin)

        self.font_weight_combo = QComboBox()
        for label, weight in FONT_WEIGHT_LABELS:
            self.font_weight_combo.addItem(f"{label} ({weight})", weight)
        weight_idx = self.font_weight_combo.findData(self.settings.get("font_weight", 400))
        self.font_weight_combo.setCurrentIndex(max(0, weight_idx))
        self.font_weight_combo.setMinimumWidth(200)
        form.addRow("Kalınlık:", self.font_weight_combo)

        self.font_italic_checkbox = QCheckBox("Eğik (italik)")
        self.font_italic_checkbox.setChecked(bool(self.settings.get("font_italic")))
        form.addRow("", self.font_italic_checkbox)

        box_layout.addLayout(form)

        self.font_preview = QLabel("Örnek: ahmet: selam kanka 42 GÜLE GÜLE")
        self.font_preview.setWordWrap(True)
        box_layout.addWidget(self.font_preview)

        font_hint = QLabel("Her yazı tipi her kalınlığı desteklemez; seçilen kalınlık "
                           "yoksa Windows en yakınını kullanır.")
        font_hint.setObjectName("HintLabel")
        font_hint.setWordWrap(True)
        box_layout.addWidget(font_hint)

        # sinyaller degerler yerlestikten SONRA baglanir
        self.font_family_combo.currentIndexChanged.connect(self._on_font_changed)
        self.font_size_spin.valueChanged.connect(self._on_font_changed)
        self.font_weight_combo.currentIndexChanged.connect(self._on_font_changed)
        self.font_italic_checkbox.toggled.connect(self._on_font_changed)
        self._refresh_font_preview()
        return box

    def _refresh_font_preview(self):
        family = self.font_family_combo.currentData() or ""
        css = f'font-family: "{family}";' if family else ""
        css += f"font-size: {self.font_size_spin.value()}px;"
        css += f"font-weight: {self.font_weight_combo.currentData()};"
        if self.font_italic_checkbox.isChecked():
            css += "font-style: italic;"
        self.font_preview.setStyleSheet(
            "QLabel {" + css + "color:#e8e8ea; background:#0f1013;"
            "border:1px solid #2a2b30; border-radius:6px; padding:8px;}"
        )

    def _on_font_changed(self, *_):
        self._refresh_font_preview()
        self._emit_settings_changed()

    # ---- sekme: one cikanlar (highlight) -----------------------------
    def _build_highlight_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.highlight_enabled_checkbox = QCheckBox("Vurgulamayı Etkinleştir")
        self.highlight_enabled_checkbox.setChecked(self.settings.get("highlight_enabled", True))
        self.highlight_enabled_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.highlight_enabled_checkbox)

        form = QFormLayout()

        self.highlight_users_input = QLineEdit(
            ", ".join(self.settings.get("highlight_users") or [])
        )
        self.highlight_users_input.setPlaceholderText("kullanıcı1, kullanıcı2")
        self.highlight_users_input.editingFinished.connect(self._emit_settings_changed)
        form.addRow("Kullanıcılar:", self.highlight_users_input)
        layout.addLayout(form)

        roles_label = QLabel("Rollere Göre Vurgula:")
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

        style_label = QLabel("Vurgu Stili")
        style_label.setObjectName("SectionLabel")
        layout.addWidget(style_label)

        # ---- arka plan boyama (kapatilirsa arka plan normal kalir) ----
        self.highlight_bg_checkbox = QCheckBox("Arka planı vurgu rengiyle boya")
        self.highlight_bg_checkbox.setChecked(self.settings.get("highlight_bg_enabled", True))
        layout.addWidget(self.highlight_bg_checkbox)

        bg_form = QFormLayout()
        self.highlight_color_swatch = ColorSwatchButton(self.settings.get("highlight_color", "#ff9900"))
        self.highlight_color_swatch.colorChanged.connect(self._emit_settings_changed)
        bg_form.addRow("Vurgu Rengi:", self.highlight_color_swatch)

        self.highlight_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.highlight_alpha_slider.setRange(0, 255)
        self.highlight_alpha_slider.setValue(self.settings.get("highlight_alpha", 200))
        self.highlight_alpha_slider.valueChanged.connect(self._emit_settings_changed)
        self.highlight_alpha_row = self._slider_row(self.highlight_alpha_slider)
        bg_form.addRow("Vurgu Yoğunluğu:", self.highlight_alpha_row)
        layout.addLayout(bg_form)

        # ---- cerceve ----
        border_form = QFormLayout()

        self.border_mode_combo = QComboBox()
        self.border_mode_combo.addItem("Yok", "none")
        self.border_mode_combo.addItem("Seçilen Renk", "custom")
        self.border_mode_combo.addItem("Kullanıcı Adı Rengi", "username")
        self.border_mode_combo.addItem("Rol Rengi", "role")
        mode = self.settings.get("highlight_border_mode", "custom")
        idx = max(0, self.border_mode_combo.findData(mode))
        self.border_mode_combo.setCurrentIndex(idx)
        self.border_mode_combo.setMinimumWidth(180)
        border_form.addRow("Çerçeve:", self.border_mode_combo)

        self.border_color_swatch = ColorSwatchButton(
            self.settings.get("highlight_border_color", "#ff9900")
        )
        self.border_color_swatch.colorChanged.connect(self._emit_settings_changed)
        border_form.addRow("Çerçeve Rengi:", self.border_color_swatch)

        self.border_width_spin = QSpinBox()
        self.border_width_spin.setRange(0, 12)
        self.border_width_spin.setValue(self.settings.get("highlight_border_width", 3))
        self.border_width_spin.setSuffix(" px")
        self.border_width_spin.valueChanged.connect(self._emit_settings_changed)
        border_form.addRow("Kalınlık:", self.border_width_spin)

        self.border_sides_combo = QComboBox()
        self.border_sides_combo.addItem("Sol Kenar", "left")
        self.border_sides_combo.addItem("Tam Çerçeve", "full")
        sides_idx = max(0, self.border_sides_combo.findData(
            self.settings.get("highlight_border_sides", "left")))
        self.border_sides_combo.setCurrentIndex(sides_idx)
        self.border_sides_combo.setMinimumWidth(180)
        self.border_sides_combo.currentIndexChanged.connect(self._emit_settings_changed)
        border_form.addRow("Konum:", self.border_sides_combo)

        layout.addLayout(border_form)

        border_hint = QLabel("Rol rengi, mesajdaki rozetin rengiyle aynı olur. "
                             "Rozeti olmayan (isme göre vurgulanan) kullanıcıda "
                             "seçilen renge düşer.")
        border_hint.setObjectName("HintLabel")
        border_hint.setWordWrap(True)
        layout.addWidget(border_hint)

        # sinyaller widget'lar kurulduktan SONRA baglanir: aksi halde
        # setChecked/setCurrentIndex insa sirasinda _emit_settings_changed
        # tetikleyip henuz olusmamis sekmelerin widget'larina erisir.
        self.highlight_bg_checkbox.toggled.connect(self._on_highlight_style_changed)
        self.border_mode_combo.currentIndexChanged.connect(self._on_highlight_style_changed)
        self._sync_highlight_style_widgets()

        layout.addStretch()
        return tab

    def _sync_highlight_style_widgets(self):
        """Kullanilmayan alanlari soluklastir."""
        bg_on = self.highlight_bg_checkbox.isChecked()
        self.highlight_color_swatch.setEnabled(bg_on)
        self.highlight_alpha_row.setEnabled(bg_on)

        mode = self.border_mode_combo.currentData()
        self.border_color_swatch.setEnabled(mode == "custom")
        has_border = mode != "none"
        self.border_width_spin.setEnabled(has_border)
        self.border_sides_combo.setEnabled(has_border)

    def _on_highlight_style_changed(self, *_):
        self._sync_highlight_style_widgets()
        self._emit_settings_changed()

    # ---- sekme: etiket (mention) ----------------------------------------
    def _build_mention_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.mention_enabled_checkbox = QCheckBox("Etiket Vurgulamayı Etkinleştir")
        self.mention_enabled_checkbox.setChecked(self.settings.get("mention_enabled", True))
        layout.addWidget(self.mention_enabled_checkbox)

        name_form = QFormLayout()
        self.mention_names_input = QLineEdit(
            ", ".join(self.settings.get("mention_names") or [])
        )
        self.mention_names_input.setPlaceholderText("kendi_adın, takma_adın")
        self.mention_names_input.editingFinished.connect(self._emit_settings_changed)
        name_form.addRow("İsimler:", self.mention_names_input)
        layout.addLayout(name_form)

        names_hint = QLabel("Virgülle ayır, '@' koymana gerek yok. Bu isimler mesaj "
                            "METNİNDE geçtiğinde vurgulanır - '@ad' ve düz 'ad' "
                            "yazımı ikisi de yakalanır, büyük/küçük harf önemsiz.")
        names_hint.setObjectName("HintLabel")
        names_hint.setWordWrap(True)
        layout.addWidget(names_hint)

        # ---- etiketin kendisi ----
        tag_label = QLabel("Etiket Görünümü")
        tag_label.setObjectName("SectionLabel")
        layout.addWidget(tag_label)

        tag_form = QFormLayout()
        self.mention_color_swatch = ColorSwatchButton(self.settings.get("mention_color", "#ffd400"))
        self.mention_color_swatch.colorChanged.connect(self._emit_settings_changed)
        tag_form.addRow("Etiket Rengi:", self.mention_color_swatch)
        layout.addLayout(tag_form)

        self.mention_bold_checkbox = QCheckBox("Etiketi kalın yaz")
        self.mention_bold_checkbox.setChecked(self.settings.get("mention_bold", True))
        layout.addWidget(self.mention_bold_checkbox)

        # ---- mesajin tamami ----
        msg_label = QLabel("Mesaj Vurgusu")
        msg_label.setObjectName("SectionLabel")
        layout.addWidget(msg_label)

        self.mention_bg_checkbox = QCheckBox("Mesajın arka planını boya")
        self.mention_bg_checkbox.setChecked(self.settings.get("mention_bg_enabled", False))
        layout.addWidget(self.mention_bg_checkbox)

        bg_form = QFormLayout()
        self.mention_bg_swatch = ColorSwatchButton(self.settings.get("mention_bg_color", "#5a3d00"))
        self.mention_bg_swatch.colorChanged.connect(self._emit_settings_changed)
        bg_form.addRow("Arka Plan Rengi:", self.mention_bg_swatch)

        self.mention_bg_alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.mention_bg_alpha_slider.setRange(0, 255)
        self.mention_bg_alpha_slider.setValue(self.settings.get("mention_bg_alpha", 210))
        self.mention_bg_alpha_slider.valueChanged.connect(self._emit_settings_changed)
        self.mention_bg_alpha_row = self._slider_row(self.mention_bg_alpha_slider)
        bg_form.addRow("Yoğunluk:", self.mention_bg_alpha_row)
        layout.addLayout(bg_form)

        self.mention_border_checkbox = QCheckBox("Mesaja çerçeve çiz")
        self.mention_border_checkbox.setChecked(self.settings.get("mention_border_enabled", False))
        layout.addWidget(self.mention_border_checkbox)

        border_form = QFormLayout()
        self.mention_border_swatch = ColorSwatchButton(
            self.settings.get("mention_border_color", "#ffd400"))
        self.mention_border_swatch.colorChanged.connect(self._emit_settings_changed)
        border_form.addRow("Çerçeve Rengi:", self.mention_border_swatch)

        self.mention_border_width_spin = QSpinBox()
        self.mention_border_width_spin.setRange(0, 12)
        self.mention_border_width_spin.setValue(self.settings.get("mention_border_width", 3))
        self.mention_border_width_spin.setSuffix(" px")
        self.mention_border_width_spin.valueChanged.connect(self._emit_settings_changed)
        border_form.addRow("Kalınlık:", self.mention_border_width_spin)

        self.mention_border_sides_combo = QComboBox()
        self.mention_border_sides_combo.addItem("Sol Kenar", "left")
        self.mention_border_sides_combo.addItem("Tam Çerçeve", "full")
        sides_idx = max(0, self.mention_border_sides_combo.findData(
            self.settings.get("mention_border_sides", "left")))
        self.mention_border_sides_combo.setCurrentIndex(sides_idx)
        self.mention_border_sides_combo.setMinimumWidth(180)
        self.mention_border_sides_combo.currentIndexChanged.connect(self._emit_settings_changed)
        border_form.addRow("Konum:", self.mention_border_sides_combo)
        layout.addLayout(border_form)

        precedence_hint = QLabel("Etiket arka planı ve çerçevesi, 'Öne Çıkanlar' "
                                 "sekmesindeki vurguyu ezer: adın geçtiği mesaj "
                                 "yazanın rolünden daha önemli.")
        precedence_hint.setObjectName("HintLabel")
        precedence_hint.setWordWrap(True)
        layout.addWidget(precedence_hint)

        # ---- ses ----
        sound_label = QLabel("Ses")
        sound_label.setObjectName("SectionLabel")
        layout.addWidget(sound_label)

        self.mention_sound_checkbox = QCheckBox("Etiketlendiğimde ses çal")
        self.mention_sound_checkbox.setChecked(self.settings.get("mention_sound_enabled", False))
        layout.addWidget(self.mention_sound_checkbox)

        sound_row = QHBoxLayout()
        self.mention_sound_input = QLineEdit(self.settings.get("mention_sound_path", ""))
        self.mention_sound_input.setPlaceholderText("boş = Windows sistem sesi")
        self.mention_sound_input.editingFinished.connect(self._emit_settings_changed)
        sound_row.addWidget(self.mention_sound_input)
        browse_btn = QPushButton("Seç")
        browse_btn.setFixedWidth(58)
        browse_btn.clicked.connect(self._pick_sound_file)
        sound_row.addWidget(browse_btn)
        self.mention_sound_test_btn = QPushButton("Dene")
        self.mention_sound_test_btn.setFixedWidth(58)
        self.mention_sound_test_btn.clicked.connect(self._test_sound)
        sound_row.addWidget(self.mention_sound_test_btn)
        layout.addLayout(sound_row)

        cooldown_form = QFormLayout()
        self.mention_cooldown_spin = QSpinBox()
        self.mention_cooldown_spin.setRange(0, 60)
        self.mention_cooldown_spin.setValue(self.settings.get("mention_sound_cooldown", 3))
        self.mention_cooldown_spin.setSuffix(" sn")
        self.mention_cooldown_spin.valueChanged.connect(self._emit_settings_changed)
        cooldown_form.addRow("Sesler Arası En Az:", self.mention_cooldown_spin)
        layout.addLayout(cooldown_form)

        sound_hint = QLabel("Sadece .wav dosyası çalınır (Windows'un kendi ses API'si "
                            "kullanılıyor, ses seviyesi uygulamadan ayarlanamaz). "
                            "Dosya seçilmezse sistem bildirim sesi çalar.")
        sound_hint.setObjectName("HintLabel")
        sound_hint.setWordWrap(True)
        layout.addWidget(sound_hint)

        # sinyaller widget'lar kurulduktan SONRA baglanir (bkz. vurgu sekmesi)
        self.mention_enabled_checkbox.toggled.connect(self._on_mention_style_changed)
        self.mention_bold_checkbox.toggled.connect(self._on_mention_style_changed)
        self.mention_bg_checkbox.toggled.connect(self._on_mention_style_changed)
        self.mention_border_checkbox.toggled.connect(self._on_mention_style_changed)
        self.mention_sound_checkbox.toggled.connect(self._on_mention_style_changed)

        layout.addStretch()
        return tab

    def _sync_mention_widgets(self):
        """Kullanilmayan alanlari soluklastir."""
        on = self.mention_enabled_checkbox.isChecked()
        self.mention_names_input.setEnabled(on)
        self.mention_color_swatch.setEnabled(on)
        self.mention_bold_checkbox.setEnabled(on)
        self.mention_bg_checkbox.setEnabled(on)
        self.mention_border_checkbox.setEnabled(on)
        self.mention_sound_checkbox.setEnabled(on)

        bg_on = on and self.mention_bg_checkbox.isChecked()
        self.mention_bg_swatch.setEnabled(bg_on)
        self.mention_bg_alpha_row.setEnabled(bg_on)

        border_on = on and self.mention_border_checkbox.isChecked()
        self.mention_border_swatch.setEnabled(border_on)
        self.mention_border_width_spin.setEnabled(border_on)
        self.mention_border_sides_combo.setEnabled(border_on)

        sound_on = on and self.mention_sound_checkbox.isChecked()
        self.mention_sound_input.setEnabled(sound_on)
        self.mention_cooldown_spin.setEnabled(sound_on)

    def _on_mention_style_changed(self, *_):
        self._sync_mention_widgets()
        self._emit_settings_changed()

    def _pick_sound_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Bildirim Sesi Seç", self.mention_sound_input.text(),
            "WAV ses dosyaları (*.wav)")
        if path:
            self.mention_sound_input.setText(path)
            self._emit_settings_changed()

    def _test_sound(self):
        # bekleme suresi atlanir, yoksa arka arkaya denemede sessiz kalir
        if not notify_sound.play(self.mention_sound_input.text(), 0, force=True):
            QMessageBox.information(self, "Ses", "Ses çalınamadı. Log dosyasına bak.")

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
        form.addRow("Yasaklı Kelimeler:", self.blocked_keywords_input)

        self.blocked_users_input = QLineEdit(
            ", ".join(self.settings.get("blocked_users") or [])
        )
        self.blocked_users_input.setPlaceholderText("kullanıcı1, kullanıcı2")
        self.blocked_users_input.editingFinished.connect(self._emit_settings_changed)
        form.addRow("Engellenen Kullanıcılar:", self.blocked_users_input)

        layout.addLayout(form)

        self.hide_bot_messages_checkbox = QCheckBox("Bot Mesajlarını Gizle")
        self.hide_bot_messages_checkbox.setChecked(self.settings.get("hide_bot_messages", False))
        self.hide_bot_messages_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.hide_bot_messages_checkbox)

        bot_form = QFormLayout()
        self.bot_users_input = QLineEdit(
            ", ".join(self.settings.get("bot_users") or [])
        )
        self.bot_users_input.setPlaceholderText("botrix, kicklet, streamelements")
        self.bot_users_input.editingFinished.connect(self._emit_settings_changed)
        bot_form.addRow("Bot Kullanıcıları:", self.bot_users_input)
        layout.addLayout(bot_form)

        bot_hint = QLabel("Kick bot hesaplarını bir 'rozet' olarak işaretlemiyor, "
                           "o yüzden bot adlarını burada elle listele.")
        bot_hint.setObjectName("HintLabel")
        bot_hint.setWordWrap(True)
        layout.addWidget(bot_hint)

        self.hide_bot_commands_checkbox = QCheckBox("Bot Komutlarını Gizle")
        self.hide_bot_commands_checkbox.setChecked(self.settings.get("hide_bot_commands", False))
        self.hide_bot_commands_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.hide_bot_commands_checkbox)

        prefix_form = QFormLayout()
        self.bot_prefix_input = QLineEdit(self.settings.get("bot_command_prefix", "!"))
        self.bot_prefix_input.setFixedWidth(60)
        self.bot_prefix_input.editingFinished.connect(self._emit_settings_changed)
        prefix_form.addRow("Komut Ön Eki:", self.bot_prefix_input)
        layout.addLayout(prefix_form)

        self.hide_notifications_checkbox = QCheckBox("Abone / Bağış Bildirimlerini Gizle")
        self.hide_notifications_checkbox.setChecked(self.settings.get("hide_notifications", False))
        self.hide_notifications_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.hide_notifications_checkbox)

        self.remove_deleted_messages_checkbox = QCheckBox("Silinen Mesajları Overlay'den de Kaldır")
        self.remove_deleted_messages_checkbox.setChecked(self.settings.get("remove_deleted_messages", False))
        self.remove_deleted_messages_checkbox.toggled.connect(self._emit_settings_changed)
        layout.addWidget(self.remove_deleted_messages_checkbox)

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
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen Kick kullanıcı adını girin.")
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.start_requested.emit(self.current_settings())

    def current_settings(self) -> dict:
        self.settings["username"] = self.username_input.text().strip()
        self.settings["font_size"] = self.font_size_spin.value()
        self.settings["font_family"] = self.font_family_combo.currentData() or ""
        self.settings["font_weight"] = self.font_weight_combo.currentData()
        self.settings["font_italic"] = self.font_italic_checkbox.isChecked()
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
            tr_fold(u.strip()) for u in users_raw.split(",") if u.strip()
        ]
        self.settings["highlight_roles"] = [
            key for key, cb in self._role_checkboxes.items() if cb.isChecked()
        ]
        self.settings["highlight_color"] = self.highlight_color_swatch.color()
        self.settings["highlight_alpha"] = self.highlight_alpha_slider.value()
        self.settings["highlight_bg_enabled"] = self.highlight_bg_checkbox.isChecked()
        self.settings["highlight_border_mode"] = self.border_mode_combo.currentData()
        self.settings["highlight_border_color"] = self.border_color_swatch.color()
        self.settings["highlight_border_width"] = self.border_width_spin.value()
        self.settings["highlight_border_sides"] = self.border_sides_combo.currentData()

        self.settings["mention_enabled"] = self.mention_enabled_checkbox.isChecked()
        mention_raw = self.mention_names_input.text()
        self.settings["mention_names"] = [
            tr_fold(n.strip().lstrip("@")) for n in mention_raw.split(",") if n.strip().lstrip("@")
        ]
        self.settings["mention_color"] = self.mention_color_swatch.color()
        self.settings["mention_bold"] = self.mention_bold_checkbox.isChecked()
        self.settings["mention_bg_enabled"] = self.mention_bg_checkbox.isChecked()
        self.settings["mention_bg_color"] = self.mention_bg_swatch.color()
        self.settings["mention_bg_alpha"] = self.mention_bg_alpha_slider.value()
        self.settings["mention_border_enabled"] = self.mention_border_checkbox.isChecked()
        self.settings["mention_border_color"] = self.mention_border_swatch.color()
        self.settings["mention_border_width"] = self.mention_border_width_spin.value()
        self.settings["mention_border_sides"] = self.mention_border_sides_combo.currentData()
        self.settings["mention_sound_enabled"] = self.mention_sound_checkbox.isChecked()
        self.settings["mention_sound_path"] = self.mention_sound_input.text().strip()
        self.settings["mention_sound_cooldown"] = self.mention_cooldown_spin.value()

        keywords_raw = self.blocked_keywords_input.text()
        self.settings["blocked_keywords"] = [
            tr_fold(k.strip()) for k in keywords_raw.split(",") if k.strip()
        ]
        blocked_raw = self.blocked_users_input.text()
        self.settings["blocked_users"] = [
            tr_fold(u.strip()) for u in blocked_raw.split(",") if u.strip()
        ]
        self.settings["hide_bot_messages"] = self.hide_bot_messages_checkbox.isChecked()
        bot_users_raw = self.bot_users_input.text()
        self.settings["bot_users"] = [
            tr_fold(u.strip()) for u in bot_users_raw.split(",") if u.strip()
        ]
        self.settings["hide_bot_commands"] = self.hide_bot_commands_checkbox.isChecked()
        self.settings["bot_command_prefix"] = self.bot_prefix_input.text().strip() or "!"
        self.settings["hide_notifications"] = self.hide_notifications_checkbox.isChecked()
        self.settings["remove_deleted_messages"] = self.remove_deleted_messages_checkbox.isChecked()

        self.settings["debug_logs"] = self.debug_logs_checkbox.isChecked()

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
            log.info("ayarlar penceresi kucultuldu - tepsiye gizleniyor")
            QTimer.singleShot(0, self.hide)

    def closeEvent(self, event):
        # Ayarlar penceresinin X'i uygulamanin tamamini kapatir. Kullanici
        # "kendi kendine kapandi" derse, logda bu satirin olup olmadigi
        # kazara Alt+F4 ile gercek cokmeyi ayirt eder.
        log.info("ayarlar penceresi kapatildi (X) - uygulama kapaniyor")
        event.accept()
        self.quit_requested.emit()
