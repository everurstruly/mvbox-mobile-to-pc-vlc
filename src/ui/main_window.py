import os
import subprocess
import time
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui
import win32com.client  # type: ignore
import pythoncom

from ..core.config_manager import load_config, save_config
from ..core.transfer_planner import build_transfer_plan
from ..devices.mtp_client import get_devices
from ..sync.sync_controller import ScanWorker, SyncWorker

# ── Obsidian Air: Apple-Inspired Micro-Design ──────────────────────────────────
OBSIDIAN_QSS = """
QMainWindow {
    background-color: #050505;
}
QWidget {
    font-family: 'Inter', 'Segoe UI Variable', 'Segoe UI', sans-serif;
    color: #FFFFFF;
}
#main_canvas {
    background: qradialgradient(cx:0.5, cy:0.2, radius:0.8, fx:0.5, fy:0.2,
        stop:0 rgba(50, 50, 90, 0.15), stop:1 rgba(5, 5, 5, 1));
}
#surfaceCard {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px;
}
#surfaceLow {
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
}

/* Typography */
#title { font-size: 26px; font-weight: 800; letter-spacing: -0.8px; }
#subtitle { font-size: 14px; color: rgba(255, 255, 255, 0.4); line-height: 1.5; }
#phase_lbl { font-size: 10px; font-weight: 900; letter-spacing: 2px; color: #007AFF; }
#stats_text { font-size: 12px; color: rgba(255, 255, 255, 0.3); font-weight: 600; }

/* Stepper */
#step_dot { color: rgba(255, 255, 255, 0.1); font-size: 14px; padding: 0 4px; }
#step_text { font-size: 11px; font-weight: 800; color: rgba(255, 255, 255, 0.2); letter-spacing: 1px; }
#step_text[active="true"] { color: #007AFF; }

/* Buttons */
QPushButton { border-radius: 12px; font-weight: 700; font-size: 13px; padding: 12px 24px; }
QPushButton#primary { 
    background-color: #007AFF; color: white; border: none; 
}
QPushButton#primary:hover { background-color: #0084FF; }
QPushButton#primary:disabled { background-color: #1a1a1a; color: #444; }

QPushButton#secondary { 
    background-color: rgba(255, 255, 255, 0.06); 
    border: 1px solid rgba(255, 255, 255, 0.1); 
}
QPushButton#secondary:hover { background-color: rgba(255, 255, 255, 0.1); }

/* Card Style */
#MediaCard { background-color: rgba(255, 255, 255, 0.03); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.05); }
#MediaCard[selected="true"] { background-color: rgba(0, 122, 255, 0.08); border: 2px solid #007AFF; }

/* Progress Bar */
QProgressBar { background: rgba(255,255,255,0.05); border-radius: 3px; height: 3px; border: none; }
QProgressBar::chunk { background: #007AFF; border-radius: 3px; }

QComboBox { 
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 18px;
    font-size: 14px;
    color: white;
}
QComboBox:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
}
QComboBox::drop-down { border: none; width: 30px; }
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid rgba(255, 255, 255, 0.3);
    margin-right: 12px;
}
QComboBox QAbstractItemView {
    background-color: #121212;
    border: 1px solid #222;
    border-radius: 10px;
    selection-background-color: #007AFF;
    outline: 0px;
}

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent; width: 6px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
}
"""

class MediaCard(QtWidgets.QFrame):
    def __init__(self, item_data):
        super().__init__()
        self.setObjectName("MediaCard")
        self.setFixedSize(240, 200)
        self.item_data = item_data
        self._selected = True
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Image Canvas
        self.thumb_container = QtWidgets.QFrame()
        self.thumb_container.setFixedHeight(120)
        self.thumb_container.setStyleSheet("background: #0D0D0D; border-top-left-radius: 16px; border-top-right-radius: 16px;")
        t_layout = QtWidgets.QVBoxLayout(self.thumb_container)
        
        # Icon/Thumbnail
        self.thumbnail_lbl = QtWidgets.QLabel("🎬" if item_data['media'].type == "movie" else "📺")
        self.thumbnail_lbl.setStyleSheet("font-size: 40px;")
        self.thumbnail_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        t_layout.addWidget(self.thumbnail_lbl)
        
        # 2. Metadata Pane
        self.info_pane = QtWidgets.QWidget()
        i_layout = QtWidgets.QVBoxLayout(self.info_pane)
        i_layout.setContentsMargins(16, 12, 16, 16)
        
        self.title_lbl = QtWidgets.QLabel(item_data['media'].title)
        self.title_lbl.setStyleSheet("font-weight: 800; font-size: 14px; color: #EEE;")
        self.title_lbl.setWordWrap(True)
        
        meta = item_data['media'].type.upper()
        if item_data['media'].type == "episode":
            meta = f"SERIES • S{item_data['media'].season:02d}E{item_data['media'].episode:02d}"
        
        self.meta_lbl = QtWidgets.QLabel(meta)
        self.meta_lbl.setStyleSheet("color: #007AFF; font-weight: 900; font-size: 9px; letter-spacing: 1.5px;")
        
        i_layout.addWidget(self.meta_lbl)
        i_layout.addWidget(self.title_lbl)
        i_layout.addStretch()
        
        layout.addWidget(self.thumb_container)
        layout.addWidget(self.info_pane)
        self.update_style()

    def mousePressEvent(self, event):
        self._selected = not self._selected
        self.update_style()
        # Notify main window
        parent = self.window()
        if hasattr(parent, 'refresh_summary'):
            parent.refresh_summary()

    def set_thumbnail(self, pixmap):
        self.thumbnail_lbl.setPixmap(pixmap.scaled(self.thumb_container.size(), 
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            QtCore.Qt.TransformationMode.SmoothTransformation))
        self.thumbnail_lbl.setText("")

    def is_selected(self): return self._selected
    
    def update_style(self):
        self.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MovieBox Sync")
        self.setFixedSize(840, 580)
        self.config = load_config()
        self.setStyleSheet(OBSIDIAN_QSS)
        
        self.scan_worker = None
        self.sync_worker = None
        self.cards = []
        self.target_paths = []
        self.setup_ui()
        
    def setup_ui(self):
        container = QtWidgets.QWidget()
        container.setObjectName("main_canvas")
        self.setCentralWidget(container)
        self.root_layout = QtWidgets.QVBoxLayout(container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        
        self.navbar = QtWidgets.QFrame()
        self.navbar.setFixedHeight(64)
        nav_layout = QtWidgets.QHBoxLayout(self.navbar)
        nav_layout.setContentsMargins(40, 0, 40, 0)
        
        self.step_widgets = []
        steps = ["CONNECT", "SCAN", "LIBRARY", "IMPORT"]
        for i, s in enumerate(steps):
            lbl = QtWidgets.QLabel(s)
            lbl.setObjectName("step_text")
            lbl.setProperty("active", i == 0)
            self.step_widgets.append(lbl)
            nav_layout.addWidget(lbl)
            if i < len(steps) - 1:
                dot = QtWidgets.QLabel("•")
                dot.setObjectName("step_dot")
                nav_layout.addWidget(dot)
        nav_layout.addStretch()
        
        self.stacked_widget = QtWidgets.QStackedWidget()
        self.setup_connect_page()
        self.setup_syncing_page()
        self.setup_library_page()
        self.setup_celebration_page()
        
        self.root_layout.addWidget(self.navbar)
        self.root_layout.addWidget(self.stacked_widget)
        self.set_current_step(0, 1)

    def set_current_step(self, page_idx, step_idx):
        self.stacked_widget.setCurrentIndex(page_idx)
        for i, lbl in enumerate(self.step_widgets):
            lbl.setProperty("active", i == (step_idx - 1))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def setup_connect_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(80, 40, 80, 80)
        
        header = QtWidgets.QVBoxLayout()
        header.setSpacing(4)
        t = QtWidgets.QLabel("Ready to Sync")
        t.setObjectName("title")
        s = QtWidgets.QLabel("Plug in your phone to begin transferring your library.")
        s.setObjectName("subtitle")
        header.addWidget(t)
        header.addWidget(s)
        
        card = QtWidgets.QFrame()
        card.setObjectName("surfaceCard")
        card.setFixedWidth(520)
        c_layout = QtWidgets.QVBoxLayout(card)
        c_layout.setContentsMargins(40, 40, 40, 40)
        c_layout.setSpacing(32)
        
        picker_v = QtWidgets.QVBoxLayout()
        picker_v.setSpacing(12)
        l = QtWidgets.QLabel("SELECT TARGET DEVICE")
        l.setStyleSheet("font-size: 10px; font-weight: 900; color: rgba(255,255,255,0.3);")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setFixedHeight(48)
        picker_v.addWidget(l)
        picker_v.addWidget(self.device_combo)
        
        self.paths_lbl = QtWidgets.QLabel("")
        self.paths_lbl.setObjectName("subtitle")
        self.paths_lbl.setStyleSheet("font-size: 12px; font-style: italic;")
        
        actions = QtWidgets.QHBoxLayout()
        self.scan_btn = QtWidgets.QPushButton("Start Magic Scan")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.setFixedHeight(54)
        self.scan_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self.start_scan_flow)
        
        self.browse_btn = QtWidgets.QPushButton("Custom Folder")
        self.browse_btn.setObjectName("secondary")
        self.browse_btn.setFixedHeight(54)
        self.browse_btn.setFixedWidth(160)
        self.browse_btn.clicked.connect(self.open_mtp_picker)
        
        actions.addWidget(self.scan_btn, 1)
        actions.addWidget(self.browse_btn)
        
        c_layout.addLayout(picker_v)
        c_layout.addWidget(self.paths_lbl)
        c_layout.addLayout(actions)
        
        layout.addLayout(header)
        layout.addWidget(card, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        self.stacked_widget.addWidget(page)
        self.refresh_devices()

    def setup_syncing_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        card = QtWidgets.QFrame()
        card.setObjectName("surfaceCard")
        card.setFixedSize(540, 320)
        c_layout = QtWidgets.QVBoxLayout(card)
        c_layout.setContentsMargins(48, 48, 48, 48)
        c_layout.setSpacing(12)
        
        self.sync_phase_lbl = QtWidgets.QLabel("INITIALIZING")
        self.sync_phase_lbl.setObjectName("phase_lbl")
        self.sync_phase_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.sync_file_lbl = QtWidgets.QLabel("Searching...")
        self.sync_file_lbl.setObjectName("title")
        self.sync_file_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sync_file_lbl.setWordWrap(True)
        
        self.sync_folder_lbl = QtWidgets.QLabel("")
        self.sync_folder_lbl.setObjectName("subtitle")
        self.sync_folder_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.sync_bar = QtWidgets.QProgressBar()
        self.sync_bar.setRange(0, 0)
        
        stats = QtWidgets.QHBoxLayout()
        self.sync_timer_lbl = QtWidgets.QLabel("00:00")
        self.sync_timer_lbl.setObjectName("stats_text")
        self.sync_checked_lbl = QtWidgets.QLabel("0 items scanned")
        self.sync_checked_lbl.setObjectName("stats_text")
        self.sync_found_lbl = QtWidgets.QLabel("")
        self.sync_found_lbl.setStyleSheet("color: #007AFF; font-weight: 800; font-size: 13px;")
        
        stats.addWidget(self.sync_timer_lbl)
        stats.addWidget(self.sync_checked_lbl)
        stats.addStretch()
        stats.addWidget(self.sync_found_lbl)
        
        self.sync_pct = QtWidgets.QLabel("")
        self.sync_pct.setObjectName("stats_text")
        self.sync_pct.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.controls_stack = QtWidgets.QStackedWidget()
        self.controls_stack.setFixedHeight(80)
        
        stop_page = QtWidgets.QWidget()
        stop_l = QtWidgets.QHBoxLayout(stop_page)
        self._stop_btn = QtWidgets.QPushButton("■  Stop Scan")
        self._stop_btn.setObjectName("secondary")
        self._stop_btn.setFixedWidth(160)
        self._stop_btn.clicked.connect(self._on_stop_pressed)
        stop_l.addWidget(self._stop_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        options_page = QtWidgets.QWidget()
        opt_l = QtWidgets.QHBoxLayout(options_page)
        opt_l.setSpacing(12)
        self._resume_btn = QtWidgets.QPushButton("Resume")
        self._resume_btn.setObjectName("secondary")
        self._resume_btn.setFixedWidth(140)
        self._resume_btn.clicked.connect(self._resume_scan)
        self._partial_btn = QtWidgets.QPushButton("Use Partial Results")
        self._partial_btn.setObjectName("primary")
        self._partial_btn.setFixedWidth(180)
        self._partial_btn.clicked.connect(self._use_partial_scan)
        opt_l.addWidget(self._resume_btn)
        opt_l.addWidget(self._partial_btn)
        
        self.controls_stack.addWidget(stop_page)
        self.controls_stack.addWidget(options_page)
        
        c_layout.addWidget(self.sync_phase_lbl)
        c_layout.addWidget(self.sync_file_lbl)
        c_layout.addWidget(self.sync_folder_lbl)
        c_layout.addSpacing(16)
        c_layout.addWidget(self.sync_bar)
        c_layout.addLayout(stats)
        c_layout.addWidget(self.sync_pct)
        c_layout.addStretch()
        c_layout.addWidget(self.controls_stack)
        
        layout.addWidget(card)
        self.stacked_widget.addWidget(page)
        
        self._live_timer = QtCore.QTimer()
        self._live_timer.setInterval(1000)
        self._live_timer.timeout.connect(self._on_live_tick)
        self._scan_start_time = None

    def setup_library_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(40, 20, 40, 40)
        
        header = QtWidgets.QHBoxLayout()
        title_v = QtWidgets.QVBoxLayout()
        t = QtWidgets.QLabel("Library")
        t.setObjectName("title")
        s = QtWidgets.QLabel("Organized collection found on your device.")
        s.setObjectName("subtitle")
        title_v.addWidget(t)
        title_v.addWidget(s)
        header.addLayout(title_v)
        header.addStretch()
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_container = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.grid_container)
        self.scroll_area.setWidgetResizable(True)
        
        self.empty_state = QtWidgets.QLabel("Nothing Found")
        self.empty_state.setObjectName("title")
        self.empty_state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.empty_state.hide()
        
        footer = QtWidgets.QHBoxLayout()
        self.summary_lbl = QtWidgets.QLabel("0 Items Selected")
        self.summary_lbl.setStyleSheet("font-weight: 800; font-size: 15px;")
        
        self.import_btn = QtWidgets.QPushButton("Sync Library")
        self.import_btn.setObjectName("primary")
        self.import_btn.setFixedWidth(200)
        self.import_btn.clicked.connect(self.start_sync_flow)
        
        footer.addWidget(self.summary_lbl)
        footer.addStretch()
        footer.addWidget(self.import_btn)
        
        layout.addLayout(header)
        layout.addSpacing(24)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.empty_state)
        layout.addSpacing(24)
        layout.addLayout(footer)
        self.stacked_widget.addWidget(page)

    def setup_celebration_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        card = QtWidgets.QFrame()
        card.setObjectName("surfaceCard")
        card.setFixedSize(460, 380)
        c_layout = QtWidgets.QVBoxLayout(card)
        c_layout.setContentsMargins(48, 48, 48, 48)
        c_layout.setSpacing(24)
        c_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        icon = QtWidgets.QLabel("✨")
        icon.setStyleSheet("font-size: 64px;")
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        t = QtWidgets.QLabel("Sync Complete")
        t.setObjectName("title")
        s = QtWidgets.QLabel("Your collection is now ready on your PC.")
        s.setObjectName("subtitle")
        s.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        btn = QtWidgets.QPushButton("Watch Now")
        btn.setObjectName("primary")
        btn.setFixedHeight(50)
        btn.clicked.connect(self.open_library)
        
        c_layout.addWidget(icon)
        c_layout.addWidget(t)
        c_layout.addWidget(s)
        c_layout.addStretch()
        c_layout.addWidget(btn)
        
        layout.addWidget(card)
        self.stacked_widget.addWidget(page)

    def refresh_devices(self):
        self.device_combo.clear()
        devices = get_devices()
        if not devices:
            self.device_combo.addItem("Searching for connections...")
            self.scan_btn.setEnabled(False)
            QtCore.QTimer.singleShot(2000, self.refresh_devices)
        else:
            for d in devices: self.device_combo.addItem(d["name"])
            self.scan_btn.setEnabled(True)

    def open_mtp_picker(self):
        from .main_window_sub import MtpFolderPickerDialog
        dialog = MtpFolderPickerDialog(self, self.device_combo.currentText(), self.config)
        if dialog.exec():
            self.target_paths = dialog.selected_paths
            self.paths_lbl.setText(f"Target: {', '.join(self.target_paths)}")

    def start_scan_flow(self):
        self.execute_scan("mtp", self.device_combo.currentText())

    def execute_scan(self, mode, root_id):
        # Force string type to prevent 'dict' TypeError
        mode = str(mode)
        root_id = str(root_id)
        
        self.set_current_step(1, 2)
        self.controls_stack.setCurrentIndex(0)
        self.sync_phase_lbl.setText("INITIALIZING")
        self.sync_file_lbl.setText("Connecting...")
        self.sync_timer_lbl.setText("00:00")
        self._scan_start_time = time.time()
        self._live_timer.start()
        self.sync_found_lbl.setText("")
        self.sync_checked_lbl.setText("0 files scanned")
        self.scan_worker = ScanWorker(mode, root_id, self.config, self.target_paths)
        self.scan_worker.progress.connect(self.update_scan_progress)
        self.scan_worker.finished.connect(self.handle_scan_results)
        self.scan_worker.failed.connect(self.handle_scan_failure)
        self.scan_worker.start()

    def update_scan_progress(self, msg):
        if msg.startswith("__PHASE__:"):
            parts = msg.split(":", 3)
            self.sync_phase_lbl.setText(f"PHASE {parts[1]} OF {parts[2]}")
            self.sync_file_lbl.setText(parts[3])
        elif msg.startswith("__FOUND__:"):
            parts = msg.split(":")
            self.sync_found_lbl.setText(f"{parts[1]} Movies Found")
        elif msg.startswith("__INFO__:"):
            parts = msg.split(":")
            self.sync_checked_lbl.setText(f"{parts[2]} files scanned")
        elif msg.startswith("__FOLDER__:"):
            path = msg[11:].split("/")[-1]
            self.sync_folder_lbl.setText(f"Scanning: {path}")

    def handle_scan_results(self, videos, subtitles):
        self._live_timer.stop()
        items = build_transfer_plan(videos, subtitles, self.config)
        
        # Sort items: Shows first (grouped), then Movies
        items.sort(key=lambda x: (0 if x['media'].type == "episode" else 1, x['media'].title))
        
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.itemAt(i).widget().setParent(None)
        self.cards = []
        if not items:
            self.scroll_area.hide()
            self.empty_state.show()
        else:
            self.empty_state.hide()
            self.scroll_area.show()
            for idx, it in enumerate(items):
                card = MediaCard(it)
                self.cards.append(card)
                self.grid_layout.addWidget(card, idx // 3, idx % 3)
        self.refresh_summary()
        self.set_current_step(2, 3)
        
        # Start JIT Thumbnails
        self.thumb_worker = ThumbnailWorker(items, self.config)
        self.thumb_worker.pixel_ready.connect(self._on_thumb_ready)
        self.thumb_worker.start()

    def _on_thumb_ready(self, idx, pixmap):
        if idx < len(self.cards):
            self.cards[idx].set_thumbnail(pixmap)

    def refresh_summary(self):
        sel = sum(1 for c in self.cards if c.is_selected())
        self.summary_lbl.setText(f"{sel} Items Selected")
        self.import_btn.setEnabled(sel > 0)

    def start_sync_flow(self):
        selected = [c.item_data for c in self.cards if c.is_selected()]
        if not selected: return
        self.set_current_step(1, 4)
        self.sync_phase_lbl.setText("TRANSFERRING")
        self.sync_bar.setRange(0, 100)
        self.sync_worker = SyncWorker(selected, self.config)
        self.sync_worker.progress.connect(self._on_sync_progress)
        self.sync_worker.finished.connect(lambda: self.set_current_step(3, 4))
        self.sync_worker.start()

    def _on_sync_progress(self, msg):
        if ":" in msg:
            p = msg.split(":")
            self.sync_file_lbl.setText(f"Syncing {p[0]}")
            self.sync_bar.setValue(int(p[1]))

    def open_library(self):
        os.startfile(self.config["destinationRoot"])
        self.close()

    def _on_live_tick(self):
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            self.sync_timer_lbl.setText(f"{elapsed//60:02d}:{elapsed%60:02d}")

    def _on_stop_pressed(self):
        if self.scan_worker: 
            self.scan_worker.pause()
            self.controls_stack.setCurrentIndex(1)

    def _resume_scan(self):
        if self.scan_worker:
            self.scan_worker.resume()
            self.controls_stack.setCurrentIndex(0)

    def _use_partial_scan(self):
        if self.scan_worker: self.scan_worker.stop()

    def handle_scan_failure(self, msg):
        self._live_timer.stop()
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.set_current_step(0, 1)

    def open_library(self):
        os.startfile(self.config["destinationRoot"])
        self.close()

    def _on_live_tick(self):
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            self.sync_timer_lbl.setText(f"{elapsed//60:02d}:{elapsed%60:02d}")

    def _on_stop_pressed(self):
        if self.scan_worker: 
            self.scan_worker.pause()
            self.controls_stack.setCurrentIndex(1)

    def _resume_scan(self):
        if self.scan_worker:
            self.scan_worker.resume()
            self.controls_stack.setCurrentIndex(0)

    def _use_partial_scan(self):
        if self.scan_worker: self.scan_worker.stop()

    def handle_scan_failure(self, msg):
        self._live_timer.stop()
        QtWidgets.QMessageBox.critical(self, "Error", msg)
        self.set_current_step(0, 1)

class ThumbnailWorker(QtCore.QThread):
    pixel_ready = QtCore.Signal(int, QtGui.QPixmap)
    
    def __init__(self, items, config):
        super().__init__()
        self.items = items
        self.config = config
        
    def run(self):
        for idx, item in enumerate(self.items):
            try:
                path = item.get("virtual_path", "")
                if os.path.exists(path):
                    pixmap = self.get_shell_thumbnail(path)
                    if pixmap:
                        self.pixel_ready.emit(idx, pixmap)
            except Exception: continue

    def get_shell_thumbnail(self, path):
        provider = QtWidgets.QFileIconProvider()
        icon = provider.icon(QtCore.QFileInfo(path))
        return icon.pixmap(320, 240)
