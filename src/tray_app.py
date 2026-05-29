import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSlider, QCheckBox,
    QFileDialog, QSystemTrayIcon, QComboBox, QListWidget,
    QListWidgetItem, QAbstractItemView, QMenu,
    QSpinBox, QStyle, QScrollArea, QMessageBox,
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPalette,
    QKeySequence, QDragEnterEvent, QDropEvent, QFont,
    QShortcut,
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl
from .wallpaper_engine import WallpaperEngine, FrameWallpaperEngine, PLAYBACK_MODES
from . import load_config, save_config
from . import icons
from .detector import detect_environment
from .utils import get_video_info, format_duration, format_resolution, send_notification, generate_thumbnail


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._drag_pos = None
        self.setObjectName("TitleBar")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)

        self.led = QLabel()
        self.led.setPixmap(icons.icon_led_inactive(8).pixmap(8, 8))
        self.led.setFixedSize(10, 10)
        layout.addWidget(self.led)

        title = QLabel("Wallpaper Dinamicos")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        layout.addStretch()

        self.info_label = QLabel("")
        self.info_label.setObjectName("infoLabel")
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.info_label)

        btn_min = QPushButton()
        btn_min.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMinButton))
        btn_min.setFixedSize(24, 24)
        btn_min.setFlat(True)
        btn_min.clicked.connect(lambda: self.window().showMinimized())
        layout.addWidget(btn_min)

        btn_close = QPushButton()
        btn_close.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        btn_close.setFixedSize(24, 24)
        btn_close.setFlat(True)
        btn_close.clicked.connect(self.window().close)
        layout.addWidget(btn_close)

        self.setLayout(layout)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def set_active(self, active):
        self.led.setPixmap(
            icons.icon_led_active(8).pixmap(8, 8) if active
            else icons.icon_led_inactive(8).pixmap(8, 8)
        )

    def set_info(self, text):
        self.info_label.setText(text)


class ThumbnailWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 145)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            ThumbnailWidget {
                background: transparent;
                border: 1px dashed #888;
                border-radius: 8px;
                font-size: 12px;
                color: #888;
            }
        """)
        self.setText("Sin preview")

    def set_video(self, path):
        if not path or not os.path.isfile(path):
            self.setText("Sin preview")
            self.setStyleSheet("""
                ThumbnailWidget {
                    background: transparent;
                    border: 1px dashed #888;
                    border-radius: 8px;
                    font-size: 12px;
                    color: #888;
                }
            """)
            return
        thumb_path = generate_thumbnail(path)
        if thumb_path:
            pixmap = QPixmap(thumb_path)
            if not pixmap.isNull():
                self.setPixmap(pixmap)
                self.setStyleSheet("""
                    ThumbnailWidget {
                        background: transparent;
                        border: 1px solid #555;
                        border-radius: 8px;
                    }
                """)
                try:
                    Path(thumb_path).unlink(missing_ok=True)
                except Exception:
                    pass
                return
        try:
            Path(thumb_path).unlink(missing_ok=True)
        except Exception:
            pass
        self.setText(os.path.basename(path)[:30])


class WallpaperGUI(QWidget):
    def __init__(self, env):
        super().__init__()
        self.env = env
        self.config = load_config()
        self._wp_engine = WallpaperEngine(desktop=env["desktop"])
        self._frame_engine = FrameWallpaperEngine()
        self._use_frame_engine = self.config.get("show_icons", False) if env["desktop"] == "deepin" else False
        if self._use_frame_engine:
            self._wp_engine.hide()
        self._is_paused = False
        self._current_video = None
        self._auto_advance_timer = QTimer()
        self._auto_advance_timer.timeout.connect(self._auto_advance)
        self._mode_debounce = QTimer()
        self._mode_debounce.setSingleShot(True)
        self._mode_debounce.timeout.connect(self._apply_mode_debounce)
        self._mode_debounce_val = None
        self._current_info = {}
        self.setAcceptDrops(True)

        self.setWindowTitle("Wallpaper Dinamicos")
        self.setWindowIcon(icons.icon_app(48))
        self.setObjectName("MainWindow")
        self.setMinimumSize(300, 520)
        self.setMaximumSize(400, 720)
        self.resize(320, 580)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAutoFillBackground(True)

        self._fix_palette()
        self._apply_stylesheet()
        self._restore_geometry()
        self._build_ui()
        self._setup_shortcuts()
        self._setup_tray()
        self._update_controls_for_mode()
        self._start_timer()
        self._sync_auto_advance()

        if self.config.get("last_video") and os.path.isfile(self.config["last_video"]):
            QTimer.singleShot(500, self._auto_start_last)

    @property
    def engine(self):
        return self._frame_engine if self._use_frame_engine else self._wp_engine

    def _switch_engine_mode(self, use_frame):
        current_video = self._current_video

        self._wp_engine.stop()
        self._wp_engine._destroy_window()
        self._frame_engine.cleanup(skip_restore=True)

        self._use_frame_engine = use_frame
        self._update_controls_for_mode()

        if not use_frame:
            self._wp_engine._setup_window()

        if current_video and os.path.isfile(current_video):
            if use_frame:
                self.engine.start(current_video, fps=self.config.get("frame_fps", 30),
                                  on_complete=self._update_controls_for_mode)
            else:
                self.engine.start(current_video)

    def _update_controls_for_mode(self):
        is_frame = self._use_frame_engine
        self.btn_play.setEnabled(not is_frame and self.engine.is_running)
        self.volume_slider.setEnabled(not is_frame)
        self.btn_mute.setEnabled(not is_frame)
        self.mode_combo.setEnabled(not is_frame)
        self.brightness_slider.setEnabled(not is_frame)
        self.contrast_slider.setEnabled(not is_frame)
        self.blur_slider.setEnabled(not is_frame)
        if hasattr(self, "fps_spin"):
            self.fps_spin.setEnabled(is_frame)

    def _apply_stylesheet(self):
        dark = self.env["dark_mode"]
        bg = self.env["bg_color"]
        fg = self.env["fg_color"]
        accent = self.env["accent_color"]
        alt = "#1f2326" if dark else "#f5f5f5"
        surface = "#2a2e35" if dark else "#ffffff"
        border = "#3d424a" if dark else "#d0d0d0"
        muted = "#8a8f96" if dark else "#999999"
        hover_bg = "#3d424a" if dark else "#e8e8e8"
        pressed_bg = "#4a5060" if dark else "#d0d0d0"

        qss = f"""
        QWidget {{
            background-color: {bg};
            color: {fg};
        }}
        QWidget#MainWindow {{
            border-radius: 10px;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QPushButton {{
            background-color: {surface};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 5px 12px;
            min-height: 24px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
            border-color: {accent};
        }}
        QPushButton:pressed {{
            background-color: {pressed_bg};
        }}
        QPushButton:disabled {{
            background-color: {bg};
            color: {muted};
            border-color: {border};
        }}
        QPushButton:flat {{
            border: none;
            background: transparent;
        }}
        QPushButton:flat:hover {{
            background-color: {hover_bg};
        }}
        QLabel {{
            background: transparent;
            color: {fg};
        }}
        QLabel#infoLabel {{
            color: {muted};
            font-size: 10px;
        }}
        #TitleBar {{
            background-color: {surface};
            border-bottom: 1px solid {border};
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        #TitleBar QPushButton {{
            background: transparent;
            border: none;
            border-radius: 4px;
            min-height: 20px;
            min-width: 20px;
            padding: 2px;
        }}
        #TitleBar QPushButton:hover {{
            background-color: {hover_bg};
        }}
        QComboBox {{
            background-color: {surface};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 4px 8px;
            min-height: 22px;
            font-size: 12px;
        }}
        QComboBox:hover {{
            border-color: {accent};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox::down-arrow {{
            width: 8px;
            height: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {surface};
            color: {fg};
            border: 1px solid {border};
            border-radius: 4px;
            selection-background-color: {accent};
        }}
        QCheckBox {{
            spacing: 6px;
            font-size: 12px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {border};
            border-radius: 3px;
            background: {surface};
        }}
        QCheckBox::indicator:hover {{
            border-color: {accent};
        }}
        QCheckBox::indicator:checked {{
            background-color: {accent};
            border-color: {accent};
        }}
        QSpinBox {{
            background-color: {surface};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 3px 6px;
            min-height: 22px;
            font-size: 12px;
        }}
        QSpinBox:hover {{
            border-color: {accent};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            border: none;
            background: transparent;
            width: 16px;
        }}
        QListWidget {{
            background-color: {surface};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 2px;
            font-size: 11px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 4px 6px;
            border-radius: 4px;
        }}
        QListWidget::item:hover {{
            background-color: {hover_bg};
        }}
        QListWidget::item:selected {{
            background-color: {accent};
            color: white;
        }}
        QSlider::groove:horizontal {{
            background: {border};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {accent};
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {accent};
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        QSlider::sub-page:horizontal {{
            background: {accent};
            border-radius: 2px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {border};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {muted};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QMenu {{
            background-color: {surface};
            color: {fg};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {accent};
            color: white;
        }}
        """
        self.setStyleSheet(qss)

    def _fix_palette(self):
        pal = QApplication.palette()
        if self.env["dark_mode"]:
            pal.setColor(QPalette.ColorRole.Window, QColor(self.env["bg_color"]))
            pal.setColor(QPalette.ColorRole.Base, QColor("#1f2326"))
            pal.setColor(QPalette.ColorRole.Text, QColor(self.env["fg_color"]))
            pal.setColor(QPalette.ColorRole.WindowText, QColor(self.env["fg_color"]))
            pal.setColor(QPalette.ColorRole.Button, QColor(self.env["bg_color"]))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor(self.env["fg_color"]))
            pal.setColor(QPalette.ColorRole.Highlight, QColor(self.env["accent_color"]))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
        else:
            pal.setColor(QPalette.ColorRole.Window, QColor(self.env["bg_color"]))
            pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.Text, QColor(self.env["fg_color"]))
            pal.setColor(QPalette.ColorRole.WindowText, QColor(self.env["fg_color"]))
            pal.setColor(QPalette.ColorRole.Button, QColor(self.env["bg_color"]))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor(self.env["fg_color"]))
            pal.setColor(QPalette.ColorRole.Highlight, QColor(self.env["accent_color"]))
            pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
        QApplication.setPalette(pal)
        self.setPalette(pal)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(12, 8, 12, 12)
        cl.setSpacing(6)

        self.thumbnail = ThumbnailWidget()
        cl.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignCenter)

        self.video_label = QLabel("Arrastra un video o selecciona uno")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setWordWrap(True)
        cl.addWidget(self.video_label)

        self.video_info_label = QLabel("")
        self.video_info_label.setObjectName("infoLabel")
        self.video_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.video_info_label)

        self.playlist_label = QLabel("")
        self.playlist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.playlist_label)

        cl.addWidget(self._sep())

        btn_row1 = QHBoxLayout()
        btn_select = QPushButton("Seleccionar")
        btn_select.setIcon(icons.icon_folder(16))
        btn_select.clicked.connect(self._select_video)
        btn_row1.addWidget(btn_select)

        btn_sample = QPushButton("Ejemplo")
        btn_sample.setIcon(icons.icon_play(16))
        btn_sample.clicked.connect(self._load_sample)
        btn_row1.addWidget(btn_sample)

        btn_add = QPushButton("+ Playlist")
        btn_add.setIcon(icons.icon_play(16))
        btn_add.clicked.connect(self._add_to_playlist)
        btn_row1.addWidget(btn_add)
        cl.addLayout(btn_row1)

        self.playlist_widget = QListWidget()
        self.playlist_widget.setMaximumHeight(90)
        self.playlist_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.playlist_widget.itemDoubleClicked.connect(self._play_from_playlist)
        self.playlist_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self._playlist_context_menu)
        cl.addWidget(self.playlist_widget)

        ctrl_row = QHBoxLayout()
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.btn_prev.setFixedSize(30, 30)
        self.btn_prev.clicked.connect(self._prev_video)
        ctrl_row.addWidget(self.btn_prev)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play.setFixedSize(34, 34)
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self._toggle_pause)
        ctrl_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.btn_stop.setFixedSize(30, 30)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        ctrl_row.addWidget(self.btn_stop)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.btn_next.setFixedSize(30, 30)
        self.btn_next.clicked.connect(self._next_video)
        ctrl_row.addWidget(self.btn_next)
        cl.addLayout(ctrl_row)

        vol_row = QHBoxLayout()
        self.btn_mute = QPushButton()
        self.btn_mute.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        self.btn_mute.setFixedSize(30, 30)
        self.btn_mute.setFlat(True)
        self.btn_mute.clicked.connect(self._toggle_mute)
        vol_row.addWidget(self.btn_mute)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.config.get("volume", 50))
        self.volume_slider.valueChanged.connect(self._on_volume)
        vol_row.addWidget(self.volume_slider)

        self.vol_label = QLabel(f"{self.config.get('volume', 50)}%")
        self.vol_label.setFixedWidth(32)
        vol_row.addWidget(self.vol_label)
        cl.addLayout(vol_row)

        cl.addWidget(self._sep())

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Modo:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Fill", "Fit", "Stretch", "Center"])
        mode_map = {"fill": 0, "fit": 1, "stretch": 2, "center": 3}
        self.mode_combo.setCurrentIndex(mode_map.get(self.config.get("playback_mode", "fill"), 0))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo)
        cl.addLayout(mode_row)

        aa_row = QHBoxLayout()
        self.auto_advance_cb = QCheckBox("Auto-cambio")
        self.auto_advance_cb.setChecked(self.config.get("auto_advance", False))
        self.auto_advance_cb.toggled.connect(self._on_auto_advance_toggled)
        aa_row.addWidget(self.auto_advance_cb)

        self.aa_seconds = QSpinBox()
        self.aa_seconds.setRange(5, 3600)
        self.aa_seconds.setValue(self.config.get("auto_advance_seconds", 30))
        self.aa_seconds.setSuffix("s")
        self.aa_seconds.setFixedWidth(65)
        self.aa_seconds.valueChanged.connect(self._on_aa_seconds_changed)
        aa_row.addWidget(self.aa_seconds)
        aa_row.addStretch()
        cl.addLayout(aa_row)

        if self.env["desktop"] == "deepin":
            self.icons_cb = QCheckBox("Mostrar iconos (experimental)")
            self.icons_cb.blockSignals(True)
            self.icons_cb.setChecked(self._use_frame_engine)
            self.icons_cb.blockSignals(False)
            self.icons_cb.toggled.connect(self._on_icons_toggled)
            cl.addWidget(self.icons_cb)

            fps_row = QHBoxLayout()
            fps_row.addWidget(QLabel("FPS iconos:"))
            self.fps_spin = QSpinBox()
            self.fps_spin.setRange(10, 180)
            self.fps_spin.setValue(self.config.get("frame_fps", 30))
            self.fps_spin.setSuffix(" fps")
            self.fps_spin.setFixedWidth(75)
            self.fps_spin.valueChanged.connect(self._on_fps_changed)
            fps_row.addWidget(self.fps_spin)
            fps_row.addStretch()
            cl.addLayout(fps_row)

        cl.addWidget(self._sep())

        self.brightness_slider = self._make_slider("Brillo", cl, 0, 200,
                                                    self.config.get("brightness", 100),
                                                    self._on_brightness)
        self.contrast_slider = self._make_slider("Contraste", cl, 0, 200,
                                                  self.config.get("contrast", 100),
                                                  self._on_contrast)
        self.blur_slider = self._make_slider("Blur", cl, 0, 20,
                                              self.config.get("blur", 0),
                                              self._on_blur)

        btn_reset = QPushButton("Restablecer Filtros")
        btn_reset.clicked.connect(self._reset_filters)
        cl.addWidget(btn_reset)

        cl.addWidget(self._sep())

        self.autostart_cb = QCheckBox("Iniciar con sesion")
        self.autostart_cb.setChecked(self.config.get("autostart", False))
        self.autostart_cb.toggled.connect(self._toggle_autostart)
        cl.addWidget(self.autostart_cb)

        cl.addStretch()

        btn_quit = QPushButton("Salir")
        btn_quit.clicked.connect(self._quit)
        cl.addWidget(btn_quit)

        content.setLayout(cl)
        scroll.setWidget(content)

    def _sep(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("QFrame { background: palette(mid); border: none; max-height: 1px; }")
        return sep

    def _make_slider(self, label_text, parent_layout, min_val, max_val, default, callback):
        row = QHBoxLayout()
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setFixedWidth(55)
        row.addWidget(label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.valueChanged.connect(callback)
        row.addWidget(slider)
        val_label = QLabel(f"{default}")
        val_label.setFixedWidth(28)
        val_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(val_label)
        slider._val_label = val_label
        parent_layout.addLayout(row)
        return slider

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._select_video)
        QShortcut(QKeySequence("Space"), self, self._toggle_pause)
        QShortcut(QKeySequence("Ctrl+Q"), self, self._quit)
        QShortcut(QKeySequence("Ctrl+Right"), self, self._next_video)
        QShortcut(QKeySequence("Ctrl+Left"), self, self._prev_video)
        QShortcut(QKeySequence("Ctrl+M"), self, self._toggle_mute)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
                self._add_video_to_playlist(path)

    def _add_video_to_playlist(self, path):
        if path not in self.config["playlist"]:
            self.config["playlist"].append(path)
            save_config(self.config)
            self._refresh_playlist()
            if len(self.config["playlist"]) == 1:
                self._play_index(0)

    def _add_to_playlist(self):
        files, _ = QFileDialog.getOpenFileUrls(
            self, "Agregar Videos",
            QUrl.fromLocalFile(str(Path.home() / "Videos")),
            "Videos (*.mp4 *.webm *.mkv *.avi *.mov);;Todos (*)",
        )
        for f in files:
            path = f.toLocalFile()
            if path and path not in self.config["playlist"]:
                self.config["playlist"].append(path)
        save_config(self.config)
        self._refresh_playlist()
        if self.config["playlist"] and not self.engine.is_running:
            self._play_index(0)

    def _refresh_playlist(self):
        self.playlist_widget.clear()
        for i, path in enumerate(self.config["playlist"]):
            name = os.path.basename(path)
            item = QListWidgetItem(f"{i+1}. {name}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.playlist_widget.addItem(item)
        total = len(self.config["playlist"])
        idx = self.config.get("playlist_index", 0)
        self.playlist_label.setText(f"Playlist: {idx+1}/{total}" if total else "")

    def _play_from_playlist(self, item):
        self._play_index(item.data(Qt.ItemDataRole.UserRole))

    def _play_index(self, idx):
        playlist = self.config["playlist"]
        if 0 <= idx < len(playlist):
            path = playlist[idx]
            self.config["playlist_index"] = idx
            self.config["last_video"] = path
            save_config(self.config)
            success = self.engine.start(path, fps=self.config.get("frame_fps", 30))
            if success:
                self._current_video = path
                self._is_paused = False
                self.btn_play.setEnabled(not self._use_frame_engine)
                self.btn_stop.setEnabled(True)
                self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self._update_video_display(path)
                self._refresh_playlist()
                self._sync_auto_advance()

    def _next_video(self):
        pl = self.config["playlist"]
        if not pl:
            return
        self._play_index((self.config.get("playlist_index", 0) + 1) % len(pl))

    def _prev_video(self):
        pl = self.config["playlist"]
        if not pl:
            return
        self._play_index((self.config.get("playlist_index", 0) - 1) % len(pl))

    def _playlist_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Reproducir").triggered.connect(lambda: self._play_index(idx))
        menu.addAction("Eliminar").triggered.connect(lambda: self._remove_from_playlist(idx))
        menu.addAction("Limpiar playlist").triggered.connect(self._clear_playlist)
        menu.exec(self.playlist_widget.mapToGlobal(pos))

    def _remove_from_playlist(self, idx):
        pl = self.config["playlist"]
        if 0 <= idx < len(pl):
            pl.pop(idx)
            if self.config.get("playlist_index", 0) >= len(pl):
                self.config["playlist_index"] = max(0, len(pl) - 1)
            save_config(self.config)
            self._refresh_playlist()

    def _clear_playlist(self):
        self.config["playlist"] = []
        self.config["playlist_index"] = 0
        save_config(self.config)
        self._refresh_playlist()

    def _on_icons_toggled(self, checked):
        self.config["show_icons"] = checked
        save_config(self.config)
        self._switch_engine_mode(checked)

    def _on_fps_changed(self, val):
        self.config["frame_fps"] = val
        save_config(self.config)
        if self._use_frame_engine and self._frame_engine.is_running:
            self._frame_engine.set_fps(val)

    def _on_auto_advance_toggled(self, checked):
        self.config["auto_advance"] = checked
        save_config(self.config)
        self._sync_auto_advance()

    def _on_aa_seconds_changed(self, val):
        self.config["auto_advance_seconds"] = val
        save_config(self.config)
        self._sync_auto_advance()

    def _sync_auto_advance(self):
        if self.config.get("auto_advance", False) and len(self.config["playlist"]) > 1:
            self._auto_advance_timer.start(self.config.get("auto_advance_seconds", 30) * 1000)
        else:
            self._auto_advance_timer.stop()

    def _auto_advance(self):
        if self.engine.is_running and not self._is_paused:
            self._next_video()

    def _on_mode_changed(self, index):
        modes = ["fill", "fit", "stretch", "center"]
        self.config["playback_mode"] = modes[index]
        save_config(self.config)
        if not self._use_frame_engine:
            self._mode_debounce_val = modes[index]
            self._mode_debounce.start(500)

    def _setup_tray(self):
        self.tray = None
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.tray = QSystemTrayIcon(icons.icon_app(64), self)
                self.tray.setToolTip("Wallpaper Dinamicos")
                self.tray.activated.connect(self._on_tray_activated)
                self.tray.show()
        except Exception:
            self.tray = None

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def _auto_start_last(self):
        video = self.config.get("last_video", "")
        if video and os.path.isfile(video):
            self.engine.start(video, fps=self.config.get("frame_fps", 30))
            self._current_video = video
            self.btn_play.setEnabled(not self._use_frame_engine)
            self.btn_stop.setEnabled(True)
            self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self._update_video_display(video)

    def _select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Video",
            str(Path.home() / "Videos"),
            "Videos (*.mp4 *.webm *.mkv *.avi *.mov);;Todos (*)",
        )
        if file_path:
            self.config["last_video"] = file_path
            if file_path not in self.config["playlist"]:
                self.config["playlist"].append(file_path)
                self.config["playlist_index"] = len(self.config["playlist"]) - 1
            else:
                self.config["playlist_index"] = self.config["playlist"].index(file_path)
            save_config(self.config)
            self._refresh_playlist()
            success = self.engine.start(file_path, fps=self.config.get("frame_fps", 30))
            if success:
                self._current_video = file_path
                self._is_paused = False
                self.btn_play.setEnabled(not self._use_frame_engine)
                self.btn_stop.setEnabled(True)
                self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self._update_video_display(file_path)
                self._sync_auto_advance()

    def _load_sample(self):
        samples_dir = Path(__file__).parent.parent / "samples"
        if not samples_dir.exists():
            samples_dir = Path.home() / ".local" / "share" / "wallpaper-dinamicos" / "samples"
        if not samples_dir.exists():
            QMessageBox.information(self, "Sin ejemplos",
                "No se encontraron videos de ejemplo.\n"
                "Descarga desde: https://github.com/yhas1984/Wallpapers_Dynamics/tree/main/samples")
            return
        samples = list(samples_dir.glob("*.mp4"))
        if not samples:
            QMessageBox.information(self, "Sin ejemplos", "No hay videos .mp4 en la carpeta samples/")
            return
        from PyQt6.QtWidgets import QInputDialog
        names = [s.stem.replace("_", " ").title() for s in samples]
        name, ok = QInputDialog.getItem(self, "Video de ejemplo", "Selecciona un video:", names, 0, False)
        if ok and name:
            idx = names.index(name)
            path = str(samples[idx])
            self.config["last_video"] = path
            if path not in self.config["playlist"]:
                self.config["playlist"].append(path)
                self.config["playlist_index"] = len(self.config["playlist"]) - 1
            save_config(self.config)
            self._refresh_playlist()
            success = self.engine.start(path, fps=self.config.get("frame_fps", 30))
            if success:
                self._current_video = path
                self._is_paused = False
                self.btn_play.setEnabled(not self._use_frame_engine)
                self.btn_stop.setEnabled(True)
                self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                self._update_video_display(path)
                self._sync_auto_advance()

    def _update_video_display(self, path):
        name = os.path.basename(path)
        self.video_label.setText(name)
        self.thumbnail.set_video(path)

        info = get_video_info(path)
        self._current_info = info
        parts = []
        if info["width"] and info["height"]:
            parts.append(format_resolution(info["width"], info["height"]))
        if info["duration"]:
            parts.append(format_duration(info["duration"]))
        if info["fps"]:
            parts.append(f"{info['fps']} fps")
        if parts:
            self.video_info_label.setText(" | ".join(parts))
        else:
            self.video_info_label.setText("")

        if hasattr(self, "fps_spin") and info.get("fps"):
            native = round(info["fps"])
            self.fps_spin.setToolTip(f"FPS nativo del video: {native}")

    def _toggle_pause(self):
        if not self.engine.is_running:
            return
        self.engine.pause()
        self._is_paused = not self._is_paused
        icon = QStyle.StandardPixmap.SP_MediaPlay if self._is_paused else QStyle.StandardPixmap.SP_MediaPause
        self.btn_play.setIcon(self.style().standardIcon(icon))

    def _stop(self):
        self.engine.stop()
        self._current_video = None
        self._is_paused = False
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.video_label.setText("Arrastra un video o selecciona uno")
        self.video_info_label.setText("")
        self.thumbnail.clear()
        self.thumbnail.setText("Sin preview")
        self.title_bar.set_active(False)
        self.title_bar.set_info("")

    def _toggle_mute(self):
        muted = self.config.get("muted", True)
        self.config["muted"] = not muted
        save_config(self.config)
        self.engine.set_mute(self.config["muted"])

    def _on_volume(self, val):
        self.config["volume"] = val
        save_config(self.config)
        self.engine.set_volume(val)
        self.vol_label.setText(f"{val}%")
        if val > 0 and self.config.get("muted", True):
            self.config["muted"] = False
            save_config(self.config)
            self.engine.set_mute(False)

    def _apply_mode_debounce(self):
        if self._mode_debounce_val and self._current_video:
            self.engine.update_filters({"playback_mode": self._mode_debounce_val})

    def _on_brightness(self, val):
        self.config["brightness"] = val
        self.brightness_slider._val_label.setText(str(val))
        self.engine.set_brightness(val)

    def _on_contrast(self, val):
        self.config["contrast"] = val
        self.contrast_slider._val_label.setText(str(val))
        self.engine.set_contrast(val)

    def _on_blur(self, val):
        self.config["blur"] = val
        self.blur_slider._val_label.setText(str(val))
        self.engine.set_blur(val)

    def _reset_filters(self):
        self.config.update({"brightness": 100, "contrast": 100, "blur": 0})
        save_config(self.config)
        self.brightness_slider.setValue(100)
        self.contrast_slider.setValue(100)
        self.blur_slider.setValue(0)
        self.engine.set_brightness(100)
        self.engine.set_contrast(100)
        self.engine.set_blur(0)

    def _toggle_autostart(self, checked):
        self.config["autostart"] = checked
        save_config(self.config)
        autostart_dir = Path.home() / ".config" / "autostart"
        df = autostart_dir / "wallpaper-dinamicos.desktop"
        if checked:
            autostart_dir.mkdir(parents=True, exist_ok=True)
            if getattr(sys, 'frozen', False):
                exec_path = sys.executable
            else:
                exec_path = Path(__file__).parent.parent / "run.py"
            df.write_text(
                "[Desktop Entry]\nType=Application\nName=Wallpaper Dinamicos\n"
                f"Exec={exec_path}\nHidden=false\nNoDisplay=false\n"
                "X-GNOME-Autostart-enabled=true\nStartupNotify=false\nTerminal=false\n"
            )
        elif df.exists():
            df.unlink()

    def _quit(self):
        self._auto_advance_timer.stop()
        self._mode_debounce.stop()
        self._wp_engine.cleanup()
        self._frame_engine.cleanup()
        self.app_ref.quit()

    def _restore_geometry(self):
        geo = self.config.get("window_geometry")
        if geo:
            try:
                self.resize(geo.get("w", 320), geo.get("h", 580))
                x, y = geo.get("x"), geo.get("y")
                if x is not None and y is not None:
                    self.move(x, y)
            except Exception:
                pass

    def _save_geometry(self):
        g = self.geometry()
        self.config["window_geometry"] = {
            "x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()
        }
        save_config(self.config)

    def closeEvent(self, event):
        self._save_geometry()
        event.ignore()
        self.hide()
        if self.tray:
            send_notification(
                "Wallpaper Dinamicos",
                "Doble clic en la bandeja para abrir.",
            )

    def _start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)

    def _update_status(self):
        if self.engine.is_running and self.engine.current_video:
            name = os.path.basename(self.engine.current_video)[:40]
            if self._is_paused:
                self.video_label.setText(f"[PAUSA] {name}")
            else:
                self.video_label.setText(name)
            self.title_bar.set_active(True)
            if self._current_info.get("duration"):
                self.title_bar.set_info(format_duration(self._current_info["duration"]))
        else:
            self.title_bar.set_active(False)
            self.title_bar.set_info("")


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("WallpaperDinamicos")
    app.setOrganizationName("WallpaperDinamicos")

    env = detect_environment()
    print(f"Escritorio: {env['desktop']}, Display: {env['display_server']}, "
          f"Modo oscuro: {env['dark_mode']}")

    gui = WallpaperGUI(env)
    gui.app_ref = app

    cfg = load_config()
    if cfg.get("start_minimized", True):
        gui.hide()
        if gui.tray:
            send_notification(
                "Wallpaper Dinamicos",
                "Iniciado minimizado. Doble clic en la bandeja para abrir.",
            )
    else:
        gui.show()

    sys.exit(app.exec())
