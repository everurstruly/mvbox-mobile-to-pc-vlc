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

OBSIDIAN_QSS = """
QMainWindow {
    background-color: #090909;
}
QWidget {
    font-family: 'Inter', 'Segoe UI Variable', 'Segoe UI', sans-serif;
    color: #ffffff;
}
QWidget#sidebar {
    background-color: #111111;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}
QWidget#main_canvas {
    background: qradialgradient(
        cx: 0.16, cy: 0.08, radius: 1.15,
        stop: 0 rgba(72, 57, 137, 0.12),
        stop: 1 rgba(9, 9, 9, 1.0)
    );
}

/* Sidebar Item */
QPushButton#SidebarItem {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 12px 16px;
    text-align: left;
    color: #888888;
    font-weight: 600;
    font-size: 13px;
    margin: 4px 12px;
}
QPushButton#SidebarItem:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #ffffff;
}
QPushButton#SidebarItem[active="true"] {
    background: rgba(197, 154, 255, 0.1);
    color: #c59aff;
}

/* Typography */
QLabel#title {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.8px;
}
QLabel#subtitle {
    color: #888888;
    font-size: 14px;
}

/* Buttons */
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #c59aff, stop:1 #a45dfc);
    color: #ffffff;
    border-radius: 14px;
    font-size: 14px;
    font-weight: 700;
    padding: 14px 28px;
    border: none;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d1a8ff, stop:1 #b373fd);
}
QPushButton#secondary {
    background-color: transparent;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 600;
    padding: 12px 24px;
}
QPushButton#secondary:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

/* Surfaces */
QFrame#surfaceHigh {
    background-color: #1a1a1a;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
QFrame#surfaceLow {
    background-color: #121212;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.03);
}

/* Inputs */
QComboBox {
    background-color: #0e0e0e;
    color: #ffffff;
    border-radius: 10px;
    padding: 12px;
    font-size: 14px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
QComboBox:focus {
    border: 1px solid #c59aff;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1a1a1a;
    border-radius: 10px;
    color: #ffffff;
    selection-background-color: #262626;
    outline: none;
}

/* Scroll Area */
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.12); }
"""

class SidebarItem(QtWidgets.QFrame):
    """Read-only step indicator — shows progress, not a navigation button."""
    def __init__(self, glyph, text):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(14)

        self._dot = QtWidgets.QLabel(glyph)
        self._dot.setFixedWidth(20)
        self._dot.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._dot.setStyleSheet("font-size: 14px; color: #333;")

        self._lbl = QtWidgets.QLabel(text)
        self._lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #444;")

        layout.addWidget(self._dot)
        layout.addWidget(self._lbl)
        layout.addStretch()
        self._active = False

    def set_active(self, active: bool, done: bool = False):
        self._active = active
        if active:
            self._dot.setStyleSheet("font-size: 14px; color: #c59aff;")
            self._lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #ffffff;")
        elif done:
            self._dot.setStyleSheet("font-size: 14px; color: #666;")
            self._lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #666; text-decoration: line-through;")
        else:
            self._dot.setStyleSheet("font-size: 14px; color: #333;")
            self._lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #444;")

class MediaCard(QtWidgets.QFrame):
    def __init__(self, item_data):
        super().__init__()
        self.item_data = item_data
        self.setFixedWidth(210)
        self.setMinimumHeight(120)
        self.setObjectName("MediaCard")
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        top_layout = QtWidgets.QHBoxLayout()
        type_lbl = QtWidgets.QLabel(item_data['media'].type.upper())
        type_lbl.setStyleSheet("color: rgba(255,255,255,0.3); font-weight: 900; font-size: 10px; letter-spacing: 1.5px;")
        
        self.checkbox = QtWidgets.QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.stateChanged.connect(self.update_style)
        
        top_layout.addWidget(type_lbl)
        top_layout.addStretch()
        top_layout.addWidget(self.checkbox)
        
        self.title_lbl = QtWidgets.QLabel(item_data['media'].title)
        self.title_lbl.setStyleSheet("font-weight: 700; font-size: 15px;")
        self.title_lbl.setWordWrap(True)
        
        meta_layout = QtWidgets.QHBoxLayout()
        season_ep = f"S{item_data['media'].season:02d} E{item_data['media'].episode:02d}" if item_data['media'].type == "episode" else str(item_data['media'].year or "")
        
        meta_lbl = QtWidgets.QLabel(season_ep)
        meta_lbl.setStyleSheet("color: #777; font-size: 11px;")
        
        subs_lbl = QtWidgets.QLabel("● SUBS" if item_data['subtitles'] else "")
        subs_lbl.setStyleSheet("color: #c59aff; font-weight: 900; font-size: 9px; letter-spacing: 1px;")
        
        meta_layout.addWidget(meta_lbl)
        meta_layout.addStretch()
        meta_layout.addWidget(subs_lbl)
        
        layout.addLayout(top_layout)
        layout.addStretch()
        layout.addWidget(self.title_lbl)
        layout.addSpacing(4)
        layout.addLayout(meta_layout)
        
        self.update_style()
        
    def is_selected(self):
        return self.checkbox.isChecked()
        
    def update_style(self):
        if self.is_selected():
            self.setStyleSheet("QFrame#MediaCard { background-color: rgba(197, 154, 255, 0.05); border: 1.5px solid #c59aff; border-radius: 20px; }")
            self.title_lbl.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 15px;")
        else:
            self.setStyleSheet("QFrame#MediaCard { background-color: #121212; border: 1.5px solid rgba(255, 255, 255, 0.05); border-radius: 20px; }")
            self.title_lbl.setStyleSheet("color: #555555; font-weight: 700; font-size: 15px;")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MovieBox Sync")
        self.resize(1000, 680)
        self.setStyleSheet(OBSIDIAN_QSS)

        self.config = load_config()
        self.scan_worker = None
        self.sync_worker = None
        self.cards = []
        self.target_paths = []

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(240)
        sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 32, 0, 32)
        sidebar_layout.setSpacing(8)

        logo = QtWidgets.QLabel("MBOX")
        logo.setStyleSheet("font-weight: 900; font-size: 20px; color: #fff; padding: 0 32px 32px 32px;")
        sidebar_layout.addWidget(logo)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.05); margin: 0 20px 16px 20px;")
        sidebar_layout.addWidget(sep)

        steps = [
            ("◎", "Connect"),
            ("⊙", "Scan"),
            ("☰", "Review"),
            ("▶", "Import"),
            ("✓", "Done"),
        ]
        self.sidebar_items = [SidebarItem(g, t) for g, t in steps]
        for item in self.sidebar_items:
            sidebar_layout.addWidget(item)

        sidebar_layout.addStretch()

        version = QtWidgets.QLabel("v2.0")
        version.setStyleSheet("color: #333; font-size: 11px; padding: 0 32px;")
        sidebar_layout.addWidget(version)
        
        # Main Canvas
        self.canvas = QtWidgets.QWidget()
        self.canvas.setObjectName("main_canvas")
        canvas_layout = QtWidgets.QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QtWidgets.QStackedWidget()
        canvas_layout.addWidget(self.stacked_widget)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.canvas, 1)

        self.setup_welcome_page()
        self.setup_discovery_page()
        self.setup_syncing_page()
        self.setup_celebration_page()

        self.set_current_step(0)
        self.refresh_devices()

    def set_current_step(self, page_idx: int, sidebar_step: int = None):
        """Show stacked page page_idx, highlight sidebar_step (defaults to page_idx)."""
        self.stacked_widget.setCurrentIndex(page_idx)
        step = sidebar_step if sidebar_step is not None else page_idx
        for i, item in enumerate(self.sidebar_items):
            item.set_active(i == step, done=(i < step))

    def closeEvent(self, event):
        for worker in [self.scan_worker, self.sync_worker]:
            if worker and worker.isRunning():
                if hasattr(worker, "abort"): worker.abort()
                worker.wait()
        event.accept()

    def cancel_operation(self):
        if self.scan_worker and self.scan_worker.isRunning(): self.scan_worker.abort()
        if self.sync_worker and self.sync_worker.isRunning(): self.sync_worker.abort()
        # Reset the stop UI so it's clean for the next operation
        self._stop_btn.setText("■  Stop")
        self._stop_btn.setEnabled(True)
        self._stop_options.hide()
        self.set_current_step(0)

    def _on_stop_pressed(self):
        """Called when Stop is pressed during an active operation."""
        if self.scan_worker and self.scan_worker.isRunning():
            # Truly pause the scan thread at the next walk checkpoint
            self.scan_worker.pause()
            self._stop_btn.hide()
            self.sync_pct.setText("PAUSED")
            self.sync_file_lbl.setText("Scan is paused. What would you like to do?")
            self._stop_options.show()
        elif self.sync_worker and self.sync_worker.isRunning():
            # During a file sync there's no partial option — just cancel
            self.sync_worker.abort()
            self.cancel_operation()

    def _resume_scan(self):
        """Resume the paused scan from where it left off."""
        if self.scan_worker and self.scan_worker.isRunning():
            self._stop_options.hide()
            self._stop_btn.show()
            self.sync_file_lbl.setText("Resuming scan...")
            self.sync_pct.setText("SCANNING")
            self.scan_worker.resume()

    def _use_partial_scan(self):
        """Accept whatever the scan found before it was stopped."""
        self._stop_options.hide()
        self._stop_btn.show()
        self._stop_btn.setEnabled(False)
        self.sync_file_lbl.setText("Collecting partial results...")
        self.sync_pct.setText("STOPPING")
        if self.scan_worker:
            # abort(use_partial=True) causes run() to emit finished() with partial data
            self.scan_worker.abort(use_partial=True)
            # handle_scan_results is already connected to finished signal

    def _discard_scan(self):
        """Stop scan and go back to the welcome screen."""
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.abort(use_partial=False)
        self._stop_btn.setText("\u25a0  Stop")
        self._stop_btn.setEnabled(True)
        self._stop_btn.show()
        self._stop_options.hide()
        self.set_current_step(0)

    def setup_welcome_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(60, 60, 60, 60)

        title = QtWidgets.QLabel("Start Your Move")
        title.setObjectName("title")
        subtitle = QtWidgets.QLabel("Connect your device to begin the media discovery process.")
        subtitle.setObjectName("subtitle")
        
        surface = QtWidgets.QFrame()
        surface.setObjectName("surfaceLow")
        surface.setFixedWidth(520)
        s_layout = QtWidgets.QVBoxLayout(surface)
        s_layout.setContentsMargins(40, 48, 40, 48)
        s_layout.setSpacing(24)

        icon_lbl = QtWidgets.QLabel("⚲") # Connection glyph
        icon_lbl.setStyleSheet("font-size: 48px; color: #c59aff;")
        icon_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumHeight(50)

        picker_btn = QtWidgets.QPushButton("Choose Specific Directory")
        picker_btn.setObjectName("secondary")
        picker_btn.clicked.connect(self.open_mtp_picker)

        self.paths_lbl = QtWidgets.QLabel("")
        self.paths_lbl.setStyleSheet("color: #c59aff; font-size: 12px;")
        self.paths_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        action_layout = QtWidgets.QHBoxLayout()
        local_btn = QtWidgets.QPushButton("Local Scour")
        local_btn.setObjectName("secondary")
        local_btn.clicked.connect(self.start_local_scan_flow)
        
        self.scan_btn = QtWidgets.QPushButton("Scan for Movies")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.clicked.connect(self.start_scan_flow)
        
        action_layout.addWidget(local_btn)
        action_layout.addWidget(self.scan_btn)

        s_layout.addWidget(icon_lbl)
        s_layout.addWidget(self.device_combo)
        s_layout.addWidget(picker_btn)
        s_layout.addWidget(self.paths_lbl)
        s_layout.addLayout(action_layout)

        layout.addStretch()
        layout.addWidget(title, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(40)
        layout.addWidget(surface, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        
        self.stacked_widget.addWidget(page)

    def setup_discovery_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 32)
        layout.setSpacing(0)

        # Header
        header = QtWidgets.QWidget()
        h_layout = QtWidgets.QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 32)
        
        title_v = QtWidgets.QVBoxLayout()
        self.disc_title = QtWidgets.QLabel("Library Scanned")
        self.disc_title.setObjectName("title")
        self.disc_subtitle = QtWidgets.QLabel("Select the movies and shows you want to sync to your PC.")
        self.disc_subtitle.setObjectName("subtitle")
        title_v.addWidget(self.disc_title)
        title_v.addWidget(self.disc_subtitle)
        
        h_layout.addLayout(title_v)
        h_layout.addStretch()
        
        btn_back = QtWidgets.QPushButton("← Back")
        btn_back.setObjectName("secondary")
        btn_back.clicked.connect(self.cancel_operation)
        h_layout.addWidget(btn_back)

        # Content
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_container = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.grid_container)

        # Empty state
        self.empty_state = QtWidgets.QWidget()
        es_layout = QtWidgets.QVBoxLayout(self.empty_state)
        es_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        es_card = QtWidgets.QFrame()
        es_card.setObjectName("surfaceLow")
        es_card.setFixedWidth(400)
        es_cv = QtWidgets.QVBoxLayout(es_card)
        es_cv.setContentsMargins(40, 40, 40, 40)
        es_icon = QtWidgets.QLabel("⊘")
        es_icon.setStyleSheet("font-size: 48px; color: #444;")
        es_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        es_txt = QtWidgets.QLabel("Nothing Found")
        es_txt.setObjectName("title")
        es_txt.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        es_sub = QtWidgets.QLabel("We couldn't find any supported files in the scanned directories.")
        es_sub.setObjectName("subtitle")
        es_sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        es_sub.setWordWrap(True)
        es_cv.addWidget(es_icon)
        es_cv.addWidget(es_txt)
        es_cv.addWidget(es_sub)
        es_layout.addWidget(es_card)
        self.empty_state.hide()

        # Footer
        footer = QtWidgets.QFrame()
        footer.setObjectName("surfaceLow")
        footer.setFixedHeight(100)
        f_layout = QtWidgets.QHBoxLayout(footer)
        f_layout.setContentsMargins(32, 0, 32, 0)
        
        self.summary_lbl = QtWidgets.QLabel("0 Items Selected")
        self.summary_lbl.setStyleSheet("font-weight: 800; font-size: 16px;")
        
        self.select_all_btn = QtWidgets.QPushButton("Clear Selection")
        self.select_all_btn.setObjectName("secondary")
        self.select_all_btn.setFixedWidth(140)
        self.select_all_btn.clicked.connect(self.toggle_all_cards)

        self.import_btn = QtWidgets.QPushButton("Sync to Library")
        self.import_btn.setObjectName("primary")
        self.import_btn.setFixedWidth(200)
        self.import_btn.clicked.connect(self.start_sync_flow)

        f_layout.addWidget(self.summary_lbl)
        f_layout.addSpacing(16)
        f_layout.addWidget(self.select_all_btn)
        f_layout.addStretch()
        f_layout.addWidget(self.import_btn)

        layout.addWidget(header)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.empty_state, 1)
        layout.addSpacing(24)
        layout.addWidget(footer)
        
        self.stacked_widget.addWidget(page)

    def setup_syncing_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        container = QtWidgets.QFrame()
        container.setObjectName("surfaceLow")
        container.setFixedWidth(520)
        container.setMinimumHeight(380)
        c_layout = QtWidgets.QVBoxLayout(container)
        c_layout.setContentsMargins(48, 48, 48, 48)
        c_layout.setSpacing(24)
        c_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.sync_phase_lbl = QtWidgets.QLabel("INITIALIZING")
        self.sync_phase_lbl.setStyleSheet("color: #c59aff; font-size: 10px; font-weight: 900; letter-spacing: 2.5px;")
        self.sync_phase_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.sync_file_lbl = QtWidgets.QLabel("Preparing Transfer...")
        self.sync_file_lbl.setObjectName("title")
        self.sync_file_lbl.setStyleSheet("font-size: 20px;")
        self.sync_file_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sync_file_lbl.setWordWrap(True)

        self.sync_folder_lbl = QtWidgets.QLabel("")
        self.sync_folder_lbl.setStyleSheet("color: #555; font-size: 12px; font-family: 'Courier New', monospace;")
        self.sync_folder_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sync_folder_lbl.setWordWrap(True)

        self.sync_bar = QtWidgets.QProgressBar()
        self.sync_bar.setRange(0, 0)
        self.sync_bar.setFixedHeight(3)
        self.sync_bar.setTextVisible(False)
        self.sync_bar.setStyleSheet("""
            QProgressBar { background: #222; border-radius: 2px; border: none; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #9547f7, stop:1 #c59aff); border-radius: 2px; }
        """)

        # Live Stats
        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.setSpacing(24)
        stats_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.sync_timer_lbl = QtWidgets.QLabel("00:00")
        self.sync_timer_lbl.setStyleSheet("color: #444; font-size: 13px; font-family: monospace;")
        
        self.sync_found_lbl = QtWidgets.QLabel("")
        self.sync_found_lbl.setStyleSheet("color: #c59aff; font-size: 13px; font-weight: 700;")

        self.sync_checked_lbl = QtWidgets.QLabel("")
        self.sync_checked_lbl.setStyleSheet("color: #444; font-size: 13px;")

        stats_layout.addWidget(self.sync_timer_lbl)
        stats_layout.addWidget(self.sync_checked_lbl)
        stats_layout.addWidget(self.sync_found_lbl)

        self.sync_pct = QtWidgets.QLabel("0%")
        self.sync_pct.setStyleSheet("color: #c59aff; font-weight: 900; font-size: 12px; letter-spacing: 2px;")
        self.sync_pct.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # ── Stop Controls ──────────────────────────────────────────────────
        self._stop_btn = QtWidgets.QPushButton("■  Stop")
        self._stop_btn.setObjectName("secondary")
        self._stop_btn.setFixedWidth(140)
        self._stop_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self._on_stop_pressed)

        # Options shown after Stop is pressed
        self._stop_options = QtWidgets.QWidget()
        opt_layout = QtWidgets.QHBoxLayout(self._stop_options)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_layout.setSpacing(12)

        self._change_src_btn = QtWidgets.QPushButton("Change Source")
        self._change_src_btn.setObjectName("secondary")
        self._change_src_btn.clicked.connect(self._discard_scan)

        self._resume_btn = QtWidgets.QPushButton("Resume")
        self._resume_btn.setObjectName("secondary")
        self._resume_btn.clicked.connect(self._resume_scan)

        self._partial_btn = QtWidgets.QPushButton("Use What Was Found")
        self._partial_btn.setObjectName("primary")
        self._partial_btn.clicked.connect(self._use_partial_scan)

        opt_layout.addWidget(self._change_src_btn)
        opt_layout.addWidget(self._resume_btn)
        opt_layout.addWidget(self._partial_btn)
        self._stop_options.hide()
        # ────────────────────────────────────────────────────────────────────

        c_layout.addWidget(self.sync_phase_lbl)
        c_layout.addSpacing(8)
        c_layout.addWidget(self.sync_file_lbl)
        c_layout.addWidget(self.sync_folder_lbl)
        c_layout.addSpacing(16)
        c_layout.addWidget(self.sync_bar)
        c_layout.addSpacing(8)
        c_layout.addLayout(stats_layout)
        c_layout.addWidget(self.sync_pct)
        c_layout.addStretch()
        c_layout.addWidget(self._stop_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self._stop_options, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

        # Internal timer for live feedback
        self._live_timer = QtCore.QTimer()
        self._live_timer.setInterval(1000)
        self._live_timer.timeout.connect(self._on_live_tick)
        self._scan_start_time = None

    def _on_live_tick(self):
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            mins, secs = divmod(elapsed, 60)
            self.sync_timer_lbl.setText(f"{mins:02d}:{secs:02d}")

    def setup_celebration_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        container = QtWidgets.QFrame()
        container.setObjectName("surfaceLow")
        container.setFixedWidth(400)
        c_layout = QtWidgets.QVBoxLayout(container)
        c_layout.setContentsMargins(40, 48, 40, 48)
        c_layout.setSpacing(24)
        c_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        icon = QtWidgets.QLabel("✓")
        icon.setStyleSheet("font-size: 64px; color: #c59aff;")
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        txt = QtWidgets.QLabel("Success")
        txt.setObjectName("title")
        
        sub = QtWidgets.QLabel("Your media has been synced and organized in your library.")
        sub.setObjectName("subtitle")
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)

        btn = QtWidgets.QPushButton("View Library")
        btn.setObjectName("primary")
        btn.clicked.connect(self.open_library)

        c_layout.addWidget(icon)
        c_layout.addWidget(txt)
        c_layout.addWidget(sub)
        c_layout.addSpacing(8)
        c_layout.addWidget(btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(container)
        self.stacked_widget.addWidget(page)

    def refresh_devices(self):
        self.device_combo.clear()
        self.target_paths = []
        self.paths_lbl.setText("")
        devices = get_devices()
        if not devices:
            self.device_combo.addItem("No connections detected")
            self.scan_btn.setEnabled(False)
            return
        for dev in devices: self.device_combo.addItem(dev["name"])
        self.scan_btn.setEnabled(True)

    def open_mtp_picker(self):
        device = self.device_combo.currentText()
        if not device or device.startswith("No "): return
        from .main_window_sub import MtpFolderPickerDialog # Helper moved to avoid bloat
        dialog = MtpFolderPickerDialog(self, device, self.config)
        if dialog.exec():
            self.target_paths = dialog.selected_paths
            if self.target_paths: self.paths_lbl.setText(f"Target: {', '.join(self.target_paths)}")
            else: self.paths_lbl.setText("")

    def start_scan_flow(self):
        if self.device_combo.currentText().startswith("No "): return
        self.execute_scan("mtp", self.device_combo.currentText())

    def start_local_scan_flow(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select MovieBox folder")
        if folder: self.execute_scan("local", folder)

    def execute_scan(self, mode: str, root_id: str):
        # page 2 = syncing page, sidebar step 1 = Scan
        self.set_current_step(2, sidebar_step=1)
        self.sync_phase_lbl.setText("INITIALIZING")
        self.sync_file_lbl.setText("Connecting to device...")
        self.sync_folder_lbl.setText("")
        self.sync_found_lbl.setText("")
        self.sync_checked_lbl.setText("Checking folders...")
        self.sync_timer_lbl.setText("00:00")
        self._scan_start_time = time.time()
        self._live_timer.start()
        self.sync_pct.setText("")
        self.sync_bar.setRange(0, 0)  # indeterminate
        self.sync_bar.show()
        self._stop_btn.setEnabled(True)
        self._stop_btn.show()
        self._stop_options.hide()
        targets = self.target_paths if mode == "mtp" else None
        self.scan_worker = ScanWorker(self.config, mode, root_id, target_paths=targets)
        self.scan_worker.progress.connect(self.update_scan_progress)
        self.scan_worker.finished.connect(self.handle_scan_results)
        self.scan_worker.failed.connect(self.handle_scan_failure)
        self.scan_worker.start()

    def update_scan_progress(self, msg: str):
        if msg.startswith("__PHASE__:"):
            # __PHASE__:current:total:description
            parts = msg.split(":", 3)
            cur, total, desc = parts[1], parts[2], parts[3]
            self.sync_phase_lbl.setText(f"PHASE {cur} OF {total}")
            self.sync_file_lbl.setText(desc)
        elif msg.startswith("__FOLDER__:"):
            raw = msg[11:]
            parts = [p for p in raw.replace("\\", "/").split("/") if p]
            # Show last 4 segments as a readable breadcrumb
            crumb = " › " .join(parts[-4:]) if len(parts) > 4 else " › ".join(parts)
            self.sync_folder_lbl.setText(crumb)
        elif msg.startswith("__FOUND__:"):
            parts = msg.split(":")
            vids, subs = parts[1], parts[2]
            v, s = int(vids), int(subs)
            if v > 0 or s > 0:
                self.sync_found_lbl.setText(f"{v} Movies Found")
        elif msg.startswith("__INFO__:"):
            parts = msg.split(":")
            folder_c, file_c = parts[1], parts[2]
            self.sync_checked_lbl.setText(f"{file_c} files scanned")
        elif msg.startswith("__DONE__:"):
            parts = msg.split(":")
            self._live_timer.stop()
            self.sync_found_lbl.setText(f"Complete — {parts[1]} found")
            self.sync_phase_lbl.setText("FINISHING UP")
        elif msg.startswith("__WARN__:"):
            self.sync_folder_lbl.setText(msg[8:])
        elif msg.startswith("__FILE_PROGRESS__:"):
            val = msg.split(":")[1]
            self.sync_pct.setText("COPYING" if val == "PULSE" else f"{val}%")
        else:
            # Catch-all for any other progress strings
            self.sync_pct.setText(msg[:50])

    def handle_scan_results(self, videos, subtitles):
        # 1. Clear the old grid
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
        self.cards = []

        # 2. Build the plan with logging
        self.sync_phase_lbl.setText("BUILDING PLAN")
        try:
            items = build_transfer_plan(videos, subtitles, self.config)
        except Exception as e:
            items = []
            QtWidgets.QMessageBox.warning(self, "Plan Error", f"Failed to build transfer plan: {e}")

        # 3. Check for the Zero-Result mismatch
        if not items:
            self.scroll_area.hide()
            self.empty_state.show()
            self.select_all_btn.hide()
            self.import_btn.setEnabled(False)
            
            if videos:
                self.summary_lbl.setText(f"Found {len(videos)} files but they were rejected.")
            else:
                self.summary_lbl.setText("0 Items Found")
            
            self.set_current_step(1, sidebar_step=2)
            return

        # 4. Success — Show the grid
        self.empty_state.hide()
        self.scroll_area.show()
        self.select_all_btn.show()
        
        for idx, item in enumerate(items):
            card = MediaCard(item)
            self.cards.append(card)
            card.checkbox.stateChanged.connect(self.refresh_summary)
            self.grid_layout.addWidget(card, idx // 3, idx % 3)
            
        self.refresh_summary()
        self.set_current_step(1, sidebar_step=2)

    def handle_scan_failure(self, msg: str):
        self.scan_worker = None
        if msg != "Scan cancelled.": QtWidgets.QMessageBox.warning(self, "Scan Fault", msg)
        self.set_current_step(0)

    def toggle_all_cards(self):
        active = any(c.is_selected() for c in self.cards)
        for c in self.cards: c.checkbox.setChecked(not active)
        self.select_all_btn.setText("Select All" if active else "Clear Selection")

    def refresh_summary(self):
        sel = sum(1 for c in self.cards if c.is_selected())
        self.summary_lbl.setText(f"{sel} Items Selected")
        self.import_btn.setEnabled(sel > 0)

    def start_sync_flow(self):
        selected_items = [c.item_data for c in self.cards if c.is_selected()]
        if not selected_items: return
        videos = [i["video"] for i in selected_items]
        subtitles = [sub for i in selected_items for sub in i["subtitles"]]
        # page 2 = syncing page, sidebar step 3 = Import
        self.set_current_step(2, sidebar_step=3)
        self.sync_phase_lbl.setText("IMPORTING")
        self.sync_file_lbl.setText("Preparing transfer...")
        self.sync_folder_lbl.setText("")
        self.sync_found_lbl.setText("")
        self.sync_pct.setText("")
        self.sync_bar.setRange(0, 0)
        self._stop_btn.show()
        self._stop_btn.setEnabled(True)
        self._stop_options.hide()
        self.sync_worker = SyncWorker(self.config, videos, subtitles)
        self.sync_worker.progress.connect(self.update_scan_progress)
        self.sync_worker.finished.connect(lambda: self.set_current_step(3, sidebar_step=4))
        self.sync_worker.failed.connect(self.handle_sync_failure)
        self.sync_worker.start()

    def update_sync_progress(self, msg: str):
        if msg.startswith("__FILE_PROGRESS__:"):
            val = msg.split(":")[1]
            self.sync_pct.setText("BUSY" if val == "PULSE" else f"{val}%")
        elif "Processing" in msg:
            self.sync_file_lbl.setText(msg.split("Processing: ", 1)[-1])
        else: self.sync_pct.setText(msg)

    def handle_sync_failure(self, msg: str):
        self.sync_worker = None
        if msg != "Sync cancelled.": QtWidgets.QMessageBox.warning(self, "Import Fault", msg)
        self.set_current_step(0)

    def open_library(self):
        dest = Path(self.config.get("destinationRoot", ""))
        if dest.exists(): os.startfile(dest)
        self.set_current_step(0, sidebar_step=0)
