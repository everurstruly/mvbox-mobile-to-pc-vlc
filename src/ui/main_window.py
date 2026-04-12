import os
import time
import ctypes
from types import SimpleNamespace
from PySide6 import QtWidgets, QtCore, QtGui

from ..core.config_manager import load_config, normalize_key
from ..core.transfer_planner import build_transfer_plan
from ..devices.mtp_client import get_devices
from ..sync.sync_controller import ScanWorker, SyncWorker
from .components import LibraryGrid, LibraryHeader

# ── Obsidian Core: Approved Final Architecture ──────────────────────────────
MASTER_QSS = """
QMainWindow { background-color: #020202; }
QWidget { font-family: 'Inter', 'Segoe UI Variable', sans-serif; color: #FFFFFF; }
#main_canvas { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #050818, stop:1 #020202); }

#navbar { border-bottom: 1px solid rgba(255, 255, 255, 0.05); background: rgba(0,0,0,0.2); }
#app_logo { font-size: 16px; font-weight: 900; color: #FFF; letter-spacing: -0.5px; }

#step_dot { background-color: rgba(255, 255, 255, 0.1); border-radius: 4px; border: none; }
#step_dot[active="true"] { background-color: #007AFF; }

/* ── Typography ── */
#hero_title { font-size: 48px; font-weight: 800; letter-spacing: -2px; color: #FFF; }
#hero_sub { font-size: 16px; color: rgba(255, 255, 255, 0.4); }
#section_t { font-size: 10px; font-weight: 900; color: rgba(255, 255, 255, 0.3); letter-spacing: 2px; text-transform: uppercase; }

/* ── Buttons ── */
QPushButton#primary {
    background-color: #007AFF; color: white; border-radius: 14px;
    font-weight: 800; font-size: 15px; padding: 16px 42px; border: none;
}
QPushButton#primary:hover { background-color: #1a8aff; }
QPushButton#primary:disabled { background-color: #111; color: #333; }

QPushButton#secondary {
    background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px; color: #EEE; padding: 12px 28px; font-weight: 700;
}
QPushButton#utility { color: rgba(255, 255, 255, 0.3); font-size: 12px; font-weight: 700; background: transparent; border: none; }
QPushButton#utility:hover { color: #FFF; }

QPushButton#ghost { background-color: transparent; border: none; color: rgba(255,255,255,0.4); font-size: 13px; font-weight: 700; }
QPushButton#ghost:hover { color: #FFF; }

QPushButton#filter_tab {
    background-color: transparent; border-radius: 10px;
    color: rgba(255, 255, 255, 0.4); font-size: 12px; font-weight: 700; padding: 10px 20px;
}
QPushButton#filter_tab[active="true"] { background-color: rgba(0, 122, 255, 0.12); color: #007AFF; border: 1px solid rgba(0,122,255,0.25); }
QPushButton#back_inline {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); color: rgba(255,255,255,0.85);
    font-size: 24px; font-weight: 500; border-radius: 12px; padding: 0;
}
QPushButton#back_inline:hover { color: #FFF; border-color: rgba(255,255,255,0.18); background: rgba(255,255,255,0.08); }

/* ── Media Card ── */
#MediaCard { background-color: rgba(255, 255, 255, 0.04); border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.08); }
#MediaCard[selected="true"] { border: 2.5px solid #007AFF; background-color: rgba(0, 122, 255, 0.1); }

QComboBox { background-color: rgba(0,0,0,0.3); border: 1px solid #222; border-radius: 14px; padding: 14px 20px; font-size: 15px; color: #FFF; }
QProgressBar { background: rgba(255,255,255,0.04); border-radius: 2px; height: 3px; border: none; }
QProgressBar::chunk { background: #007AFF; border-radius: 2px; }

#surfaceCard { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 24px; }
#library_header { border-bottom: 1px solid rgba(255,255,255,0.06); }
#library_footer {
    background: rgba(7,10,20,0.94);
    border-top: 1px solid rgba(255,255,255,0.08);
}

QCheckBox { color: rgba(255,255,255,0.4); font-size: 13px; font-weight: 700; spacing: 8px; background: transparent; border: none; }
QCheckBox:hover { color: #FFF; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid rgba(255,255,255,0.2); background: transparent; }
QCheckBox::indicator:checked { background: #007AFF; border-color: #007AFF; image: url("__CHECK_ICON__"); }
QCheckBox::indicator:indeterminate { background: rgba(0,122,255,0.35); border-color: #007AFF; }
QCheckBox::indicator:hover { border-color: rgba(255,255,255,0.5); }

QComboBox#device_picker {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px;
    padding: 14px 18px;
}
QComboBox#device_picker:hover { border-color: rgba(255,255,255,0.22); background: rgba(255,255,255,0.07); }
QComboBox#device_picker:focus { border-color: rgba(0,122,255,0.8); background: rgba(0,122,255,0.08); }
QPushButton#device_reload {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    color: #EEE;
    padding: 12px 22px;
    font-weight: 700;
}
QPushButton#device_reload:hover { border-color: rgba(255,255,255,0.24); background-color: rgba(255,255,255,0.08); }
QPushButton#device_reload:pressed { background-color: rgba(255,255,255,0.12); }
#device_status { font-size: 12px; }
#device_status[state="info"] { color: rgba(255,255,255,0.48); }
#device_status[state="success"] { color: #79D28A; }
#device_status[state="warning"] { color: #FFB454; }
#device_status[state="danger"] { color: #FF7A7A; }
"""

PAGE_MARGIN_X = 32
SURFACE_INNER_X = 28
LIBRARY_SECTION_GAP = 16

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Windows Taskbar Icon Fix (AppUserModelID)
        try:
            myappid = u'movieknight.desktop.v1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        self.setWindowTitle("Movieknight"); self.setMinimumSize(500, 500); self.resize(960, 680)
        
        # Set Branding Icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
            
        check_icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "check.svg").replace("\\", "/")
        self.config = load_config(); self.setStyleSheet(MASTER_QSS.replace("__CHECK_ICON__", check_icon_path))
        self.target_paths = []; self._all_items = []; self._af = "All"; self._sort_key = "title"; self._scan_videos = []; self._scan_subtitles = []
        self._view_cache = {}; self._library_render_token = 0; self._device_snapshot = tuple()
        self._grid_reflow = QtCore.QTimer(self); self._grid_reflow.setSingleShot(True); self._grid_reflow.timeout.connect(self._reflow_library_grid)
        self._device_poll = QtCore.QTimer(self); self._device_poll.timeout.connect(self._auto_refresh_devices)
        self._build_ui()
        self._apply_runtime_config()

    def _build_ui(self):
        root = QtWidgets.QWidget(); root.setObjectName("main_canvas")
        self.setCentralWidget(root); layout = QtWidgets.QVBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        self.navbar = QtWidgets.QFrame(); self.navbar.setObjectName("navbar"); self.navbar.setFixedHeight(72)
        nl = QtWidgets.QHBoxLayout(self.navbar); nl.setContentsMargins(PAGE_MARGIN_X, 0, PAGE_MARGIN_X, 0)
        
        # Brand Logo in Navbar
        brand_w = QtWidgets.QWidget(); bl = QtWidgets.QHBoxLayout(brand_w); bl.setContentsMargins(0,0,0,0); bl.setSpacing(12)
        logo_icon = QtWidgets.QLabel()
        logo_pix = QtGui.QPixmap(os.path.join(os.path.dirname(__file__), "assets", "logo.png"))
        if not logo_pix.isNull():
            logo_icon.setPixmap(logo_pix.scaled(28, 28, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
        bl.addWidget(logo_icon)
        logo_text = QtWidgets.QLabel("MOVIEKNIGHT"); logo_text.setObjectName("app_logo")
        bl.addWidget(logo_text)
        nl.addWidget(brand_w); nl.addStretch()
        self._dots = []; dot_w = QtWidgets.QWidget(); dl = QtWidgets.QHBoxLayout(dot_w); dl.setSpacing(8)
        for i in range(4):
            d = QtWidgets.QFrame(); d.setObjectName("step_dot"); d.setFixedSize(8, 8); self._dots.append(d); dl.addWidget(d)
        nl.addWidget(dot_w); nl.addStretch()
        self.settings_btn = QtWidgets.QPushButton("Settings"); self.settings_btn.setObjectName("utility"); self.settings_btn.clicked.connect(self._open_settings); nl.addWidget(self.settings_btn); nl.addSpacing(20)
        self.help_btn = QtWidgets.QPushButton("Support"); self.help_btn.setObjectName("utility"); nl.addWidget(self.help_btn)
        layout.addWidget(self.navbar)
        self.stack = QtWidgets.QStackedWidget(); layout.addWidget(self.stack)
        self.stack.addWidget(self._page_connect()); self.stack.addWidget(self._page_scanning()); self.stack.addWidget(self._page_library()); self.stack.addWidget(self._page_done())
        self._go(0, 0)

    def _go(self, p, s):
        self.stack.setCurrentIndex(p)
        for i, d in enumerate(self._dots): d.setProperty("active", i == s); d.style().unpolish(d); d.style().polish(d)

    def _return_to_setup(self):
        self._go(0, 0)

    def _page_connect(self):
        page = QtWidgets.QWidget(); l = QtWidgets.QVBoxLayout(page); l.setContentsMargins(PAGE_MARGIN_X, 48, PAGE_MARGIN_X, 64); l.setSpacing(40)
        header = QtWidgets.QVBoxLayout(); header.setSpacing(8); header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        t = QtWidgets.QLabel("Ready to Sync."); t.setObjectName("hero_title"); t.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter); s = QtWidgets.QLabel("Plug in your phone to find your videos."); s.setObjectName("hero_sub"); s.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter); header.addWidget(t); header.addWidget(s)
        container = QtWidgets.QFrame(); container.setObjectName("surfaceCard"); container.setFixedWidth(540)
        cl = QtWidgets.QVBoxLayout(container); cl.setContentsMargins(SURFACE_INNER_X, 48, SURFACE_INNER_X, 48); cl.setSpacing(0)
        chosen_phone_lbl = QtWidgets.QLabel("CHOSEN PHONE"); chosen_phone_lbl.setObjectName("section_t"); cl.addWidget(chosen_phone_lbl); cl.addSpacing(12)
        device_row = QtWidgets.QHBoxLayout(); device_row.setSpacing(12)
        self.device_combo = QtWidgets.QComboBox(); self.device_combo.setObjectName("device_picker"); self.device_combo.setFixedHeight(56); device_row.addWidget(self.device_combo, 1)
        self.device_refresh_btn = QtWidgets.QPushButton("Reload"); self.device_refresh_btn.setObjectName("device_reload"); self.device_refresh_btn.setFixedHeight(56); self.device_refresh_btn.clicked.connect(self._manual_refresh_devices); device_row.addWidget(self.device_refresh_btn)
        cl.addLayout(device_row)
        self.device_status_lbl = QtWidgets.QLabel(""); self.device_status_lbl.setObjectName("device_status"); cl.addSpacing(12); cl.addWidget(self.device_status_lbl)
        only_folders_lbl = QtWidgets.QLabel("ONLY THESE FOLDERS (OPTIONAL)"); only_folders_lbl.setObjectName("section_t"); cl.addSpacing(64); cl.addWidget(only_folders_lbl); cl.addSpacing(12)
        self.add_b = QtWidgets.QPushButton("+ Add Folders"); self.add_b.setObjectName("ghost"); self.add_b.setFixedHeight(40); self.add_b.clicked.connect(self._open_picker); cl.addWidget(self.add_b, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.dest_hint = QtWidgets.QLabel(f"Library folder: {self.config['destinationRoot']}"); self.dest_hint.setObjectName("hero_sub"); self.dest_hint.setWordWrap(True); self.dest_hint.setStyleSheet("font-size: 12px;"); cl.addSpacing(20); cl.addWidget(self.dest_hint)
        self.tags_l = QtWidgets.QHBoxLayout(); self.tags_l.setSpacing(8); self.tags_l.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft); self.tags_w = QtWidgets.QWidget(); self.tags_w.setLayout(self.tags_l); self.tags_sc = QtWidgets.QScrollArea(); self.tags_sc.setWidget(self.tags_w); self.tags_sc.setWidgetResizable(True); self.tags_sc.setFixedHeight(48); cl.addWidget(self.tags_sc); self.tags_sc.setVisible(False)
        cl.addSpacing(32); self.scan_btn = QtWidgets.QPushButton("Scan for Videos  →"); self.scan_btn.setObjectName("primary"); self.scan_btn.setFixedHeight(60); self.scan_btn.clicked.connect(self._start_scan)
        cl.addWidget(self.scan_btn); l.addLayout(header); body_l = QtWidgets.QHBoxLayout(); body_l.addStretch(); body_l.addWidget(container); body_l.addStretch(); l.addLayout(body_l); l.addStretch(); self.refresh_devices(force=True); return page

    def _page_scanning(self):
        page = QtWidgets.QWidget(); l = QtWidgets.QVBoxLayout(page); l.setContentsMargins(80, 80, 80, 80); l.setSpacing(24); l.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._scan_title = QtWidgets.QLabel("Finding your videos..."); self._scan_title.setObjectName("hero_title"); self._scan_title.setStyleSheet("font-size: 32px;"); self._scan_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter); l.addWidget(self._scan_title)
        container = QtWidgets.QFrame(); container.setObjectName("surfaceCard"); container.setFixedWidth(540)
        cl = QtWidgets.QVBoxLayout(container); cl.setContentsMargins(SURFACE_INNER_X, 48, SURFACE_INNER_X, 48); cl.setSpacing(32)
        
        # 1. Vertical Sequence (Mechanical Discovery)
        self.seq_w = QtWidgets.QWidget(); self.seq_l = QtWidgets.QVBoxLayout(self.seq_w); self.seq_l.setSpacing(12); self.seq_l.setContentsMargins(0, 0, 0, 0)
        self._slots = []
        for i in range(3):
            s = QtWidgets.QLabel("..."); s.setObjectName("hero_sub"); s.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: rgba(255,255,255,0.15);"); s.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self._slots.append(s); self.seq_l.addWidget(s)
        self._slots[1].setStyleSheet("font-family: 'Consolas', monospace; font-size: 13px; font-weight: 700; color: #007AFF;")
        cl.addWidget(self.seq_w)
        
        # 2. Movie Count (Primary Result)
        self._s_count = QtWidgets.QLabel("0 Videos Found"); self._s_count.setStyleSheet("font-size: 20px; font-weight: 800; color: #FFF;"); self._s_count.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self._s_count)

        # 3. Progress Bar (Foundation)
        self._s_bar = QtWidgets.QProgressBar(); self._s_bar.setRange(0, 0); self._s_bar.setFixedHeight(3); cl.addWidget(self._s_bar)
        
        # 4. Controls
        self._ctrl_stack = QtWidgets.QStackedWidget(); self._ctrl_stack.setMaximumWidth(380); self._ctrl_stack.setMinimumHeight(116)
        cl.addWidget(self._ctrl_stack, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Active State
        act_w = QtWidgets.QWidget(); al = QtWidgets.QHBoxLayout(act_w); al.setContentsMargins(0, 0, 0, 0); act_w.setMinimumHeight(116)
        self.primary_stop_btn = QtWidgets.QPushButton(" Stop"); self.primary_stop_btn.setObjectName("secondary"); self.primary_stop_btn.setIcon(QtGui.QIcon("src/ui/assets/icons/stop.svg")); self.primary_stop_btn.setIconSize(QtCore.QSize(18, 18)); self.primary_stop_btn.setFixedSize(160, 44)
        self.primary_stop_btn.clicked.connect(self._on_primary_stop); al.addStretch(); al.addWidget(self.primary_stop_btn); al.addStretch(); self._ctrl_stack.addWidget(act_w)
        
        # Decision State
        dec_w = QtWidgets.QWidget(); dl = QtWidgets.QVBoxLayout(dec_w); dl.setSpacing(0); dl.setContentsMargins(0, 0, 0, 0); dec_w.setMinimumHeight(116)
        
        # Row 1: The Encouraged Path
        r1_w = QtWidgets.QWidget(); r1 = QtWidgets.QHBoxLayout(r1_w); r1.setContentsMargins(0, 0, 0, 0)
        self.resume_btn = QtWidgets.QPushButton(" Resume"); self.resume_btn.setObjectName("primary"); self.resume_btn.setIcon(QtGui.QIcon("src/ui/assets/icons/play.svg")); self.resume_btn.setFixedHeight(50)
        r1.addWidget(self.resume_btn); dl.addWidget(r1_w)
        
        dl.addSpacing(10) # TIGHT ZEN GAP
        
        # Row 2: Utility Choices
        r2_w = QtWidgets.QWidget(); r2 = QtWidgets.QHBoxLayout(r2_w); r2.setContentsMargins(0, 0, 0, 0); r2.setSpacing(12)
        self.restart_btn = QtWidgets.QPushButton(" Restart"); self.restart_btn.setObjectName("secondary"); self.restart_btn.setFixedHeight(42)
        self.restart_btn.setIcon(QtGui.QIcon("src/ui/assets/icons/restart.svg")); self.restart_btn.setIconSize(QtCore.QSize(18, 18))
        self.skip_btn = QtWidgets.QPushButton(" Skip Full Scan"); self.skip_btn.setObjectName("secondary"); self.skip_btn.setFixedHeight(42)
        self.skip_btn.setIcon(QtGui.QIcon("src/ui/assets/icons/skip.svg")); self.skip_btn.setIconSize(QtCore.QSize(18, 18))
        
        r2.addWidget(self.restart_btn); r2.addWidget(self.skip_btn); dl.addWidget(r2_w)
        dl.addStretch() # Anchors buttons together
        self._ctrl_stack.addWidget(dec_w)
        
        self.resume_btn.clicked.connect(self._on_resume); self.restart_btn.clicked.connect(self._on_stop); self.skip_btn.clicked.connect(self._on_review)
        l.addWidget(container); l.addStretch(); return page

    def _on_primary_stop(self):
        if hasattr(self, "sync_worker") and self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.abort()
            self.primary_stop_btn.setText(" Stopping...")
            self._slots[1].setText("Stopping — finishing current file...")
            self._slots[2].setText("Will stop cleanly after this file completes.")
            return
        if hasattr(self, "scan_worker"): self.scan_worker.pause()
        self._ctrl_stack.setCurrentIndex(1); self._slots[1].setText(self._slots[1].text() + " • PAUSED")

    def _on_resume(self):
        if hasattr(self, "scan_worker"): self.scan_worker.resume()
        self._ctrl_stack.setCurrentIndex(0); self._slots[1].setText(self._slots[1].text().replace(" • PAUSED", ""))

    def _on_review(self):
        if hasattr(self, "scan_worker") and self.scan_worker.isRunning():
            self.scan_worker.abort(use_partial=True); self.scan_worker.wait(1000)
            self._on_done(self.scan_worker.videos, self.scan_worker.subtitles)

    def _on_stop(self):
        if hasattr(self, "scan_worker"): self.scan_worker.abort(use_partial=False); self.scan_worker.wait(1000)
        self._return_to_setup()

    def _on_progress(self, msg):
        try:
            if "__FOLDER__:" in msg:
                _, path = msg.split(":", 1)
                name = path.split("/")[-1] if "/" in path else (path.split("\\")[-1] if "\\" in path else path)
                self._slots[0].setText(self._slots[1].text())
                self._slots[1].setText(f"📁  /{name[:24]}")
                self._slots[2].setText("Scanning next...")
            elif "__FOUND__:" in msg:
                _, v, _ = msg.split(":") # __FOUND__:v:s
                self._s_count.setText(f"{v} Videos Found")
            elif "__PHASE__:" in msg:
                self._slots[1].setText(msg.split(":")[-1])
        except Exception: pass

    def _start_scan(self):
        device_ref = self._selected_device_ref()
        self._scan_title.setText("Finding your videos...")
        self.primary_stop_btn.setText(" Stop")
        self.primary_stop_btn.setEnabled(True)
        self._s_count.setText("0 Videos Found")
        self._s_bar.setRange(0, 0)
        for slot in self._slots: slot.setText("...")
        self._go(1, 1); self._scan_start = time.time(); self.scan_worker = ScanWorker("mtp", device_ref, self.config, self.target_paths)
        self.scan_worker.progress.connect(self._on_progress); self.scan_worker.finished.connect(self._on_done); self.scan_worker.failed.connect(self._on_scan_failed); self.scan_worker.start(); self._ctrl_stack.setCurrentIndex(0)

    def _on_done(self, v, s):
        self._scan_videos = list(v)
        self._scan_subtitles = list(s)
        self._all_items = build_transfer_plan(v, s, self.config)
        for item in self._all_items: item["selected"] = item.get("selected", True)
        self._sort_key = "title"
        self._apply_sort()
        self._go(2, 2)
        QtCore.QTimer.singleShot(0, lambda: self._apply_filter("All"))

    def _on_scan_failed(self, msg):
        self.primary_stop_btn.setEnabled(True)
        text = str(msg)
        if "allow file access" in text.lower() or "file transfer" in text.lower() or "cannot read its files" in text.lower():
            self._set_device_status(text, "danger")
        QtWidgets.QMessageBox.critical(self, "Scan Failed", text)
        self._return_to_setup()

    def closeEvent(self, event):
        for attr in ["scan_worker", "sync_worker"]:
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w and w.isRunning(): w.abort(); w.wait(1000)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._grid_reflow.start(60)

    # ────── Library / Results ──────
    def _page_library(self):
        page = QtWidgets.QWidget(); l = QtWidgets.QVBoxLayout(page); l.setContentsMargins(0, 0, 0, 0); l.setSpacing(0)
        self.library_header = LibraryHeader(
            PAGE_MARGIN_X,
            LIBRARY_SECTION_GAP,
            self._return_to_setup,
            self._apply_filter,
            self._start_import,
            self._on_select_toggle,
            self._clear_visible_selection,
            self._on_sort_changed,
        )
        l.addWidget(self.library_header)
        self.library_grid = LibraryGrid(PAGE_MARGIN_X, self.refresh_summary)
        l.addWidget(self.library_grid, 1)
        l.addWidget(self.library_header.footer_bar)
        self.import_btn = self.library_header.copy_top_btn
        return page

    def _apply_filter(self, f):
        self._af = f
        self.library_header.set_active_filter(f)
        self._render_library_view(f, show_loading=True)

    def refresh_summary(self):
        visible_count = len(getattr(self.library_grid, "_items", [])) if hasattr(self, "library_grid") else 0
        selected_count = self.library_grid.selected_count() if hasattr(self, "library_grid") else 0
        selectable_count = self.library_grid.selectable_count() if hasattr(self, "library_grid") else 0
        total_count = len(self._all_items)
        self.library_header.set_counts(visible_count, total_count, selected_count, self._view_label_plural())
        self.library_header.update_select_checkbox(selected_count, selectable_count)
        self.library_header.set_copy_label(self._copy_button_label(selected_count))
        self.import_btn.setEnabled(selected_count > 0)
        self.library_header.set_copy_enabled(selected_count > 0)

    def _on_select_toggle(self, checked: bool):
        self.library_grid.set_all_selected(checked)

    def _clear_visible_selection(self):
        self.library_grid.set_all_selected(False)

    def _apply_sort(self):
        self._view_cache = {}

    def _on_sort_changed(self, sort_key: str):
        self._sort_key = sort_key
        self._apply_sort()
        self._render_library_view(getattr(self, "_af", "All"), show_loading=True)

    def _start_import(self):
        selected = self.library_grid.selected_items()
        self._go(1, 3)
        self._scan_title.setText("Copying selected videos...")
        self.primary_stop_btn.setText(" Stop Copy")
        self.primary_stop_btn.setEnabled(True)
        self._ctrl_stack.setCurrentIndex(0)
        self._s_bar.setRange(0, 0)
        self._s_count.setText(f"{len(selected)} items queued")
        self._slots[0].setText("Preparing transfer...")
        self._slots[1].setText("Waiting for first file...")
        self._slots[2].setText("Transfer stays active even if Windows opens a copy dialog.")
        self.sync_worker = SyncWorker(selected, self.config)
        self.sync_worker.progress.connect(self._on_sync_progress)
        self.sync_worker.finished.connect(self._on_sync_finished)
        self.sync_worker.failed.connect(self._on_sync_failed)
        self.sync_worker.cancelled.connect(self._on_sync_cancelled)
        self.sync_worker.start()

    def _on_sync_progress(self, msg):
        text = str(msg or "")
        if text.startswith("__FILE_PROGRESS__:"):
            value = text.split(":", 1)[1]
            if value == "PULSE":
                if self._s_bar.maximum() != 0:
                    self._s_bar.setRange(0, 0)
            else:
                if self._s_bar.maximum() == 0:
                    self._s_bar.setRange(0, 100)
                try:
                    self._s_bar.setValue(int(value))
                except ValueError:
                    pass
            return

        if self._s_bar.maximum() == 0:
            self._s_bar.setRange(0, 100)

        if text.startswith("[") and "] Processing: " in text:
            left, right = text.split(" Processing: ", 1)
            self._slots[0].setText(left)
            self._slots[1].setText(right[:48])
            self._slots[2].setText("Copying video and subtitles...")
            return

        if text.startswith("Awaiting MTP transfer: "):
            self._slots[2].setText(f"Waiting for Windows copy: {text.replace('Awaiting MTP transfer: ', '')[:34]}")
            return

        if text.startswith("__TRANSFER_STATE__:"):
            self._slots[1].setText(text.replace("__TRANSFER_STATE__:", "")[:64])
            if self._s_bar.maximum() != 0:
                self._s_bar.setRange(0, 0)
            return

        if text.startswith("__TRANSFER_HINT__:"):
            self._slots[2].setText(text.replace("__TRANSFER_HINT__:", "")[:72])
            return

        if text.startswith("Moved video to -> "):
            self._slots[2].setText("Video saved to library")
            return

        if text.startswith("Moved subtitle to -> "):
            self._slots[2].setText("Subtitle saved to library")
            return

        if text.startswith("Starting import of "):
            self._slots[0].setText(text)
            return

        if text.startswith("Import complete."):
            self._slots[1].setText("Import complete")
            self._slots[2].setText("")
            self._s_bar.setRange(0, 100)
            self._s_bar.setValue(100)
            return

        self._slots[1].setText(text[:48])

    def _on_sync_finished(self):
        self.primary_stop_btn.setEnabled(True)
        self._go(3, 3)

    def _on_sync_cancelled(self):
        # User stopped intentionally. Return to library, no error dialog.
        self.primary_stop_btn.setText(" Stop Copy")
        self.primary_stop_btn.setEnabled(True)
        self._go(2, 2)
        self.refresh_summary()

    def _on_sync_failed(self, msg):
        self.primary_stop_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Import Failed", str(msg))
        self._go(2, 2)

    def _page_done(self):
        page = QtWidgets.QWidget(); l = QtWidgets.QVBoxLayout(page); l.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter); l.setSpacing(24)
        t = QtWidgets.QLabel("All Saved!"); t.setObjectName("hero_title"); l.addWidget(t, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        s = QtWidgets.QLabel("Your videos are ready on this device."); s.setObjectName("hero_sub"); l.addWidget(s, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        actions = QtWidgets.QWidget(); al = QtWidgets.QHBoxLayout(actions); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(14)
        watch_btn = QtWidgets.QPushButton("Watch now  →"); watch_btn.setObjectName("primary"); watch_btn.setFixedHeight(58); watch_btn.clicked.connect(self._open_dest)
        discover_btn = QtWidgets.QPushButton("Discover New"); discover_btn.setObjectName("secondary"); discover_btn.setFixedHeight(58); discover_btn.clicked.connect(self._start_new_discovery)
        al.addWidget(watch_btn); al.addWidget(discover_btn); l.addWidget(actions, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        return page

    def _open_dest(self): os.startfile(self.config["destinationRoot"])
    def _start_new_discovery(self):
        self._all_items = []
        self._scan_videos = []
        self._scan_subtitles = []
        self._view_cache = {}
        self.target_paths = []
        while self.tags_l.count():
            item = self.tags_l.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
        self.tags_sc.setVisible(False)
        self.scan_btn.setText("Scan for Videos  →")
        self.refresh_devices(force=True)
        self._return_to_setup()
    def _open_picker(self):
        from .main_window_sub import MtpFolderPickerDialog
        d = MtpFolderPickerDialog(self, self.device_combo.currentText(), self._selected_device_ref(), self.config)
        if d.exec(): [ (self.target_paths.append(p), self._add_chip(p)) for p in d.selected_paths if p not in self.target_paths ]
    def _reflow_library_grid(self):
        if hasattr(self, "stack") and self.stack.currentIndex() == 2 and self._all_items:
            self._render_library_view(getattr(self, "_af", "All"), show_loading=False)
    def _selected_device_ref(self):
        data = self.device_combo.currentData()
        return str(data if data else self.device_combo.currentText())
    def _add_chip(self, p):
        c = QtWidgets.QPushButton(f"📁 {p.split('/')[-1]} ✕"); c.setObjectName("ghost"); c.clicked.connect(lambda _, x=p, w=c: self._rem_chip(x, w)); self.tags_l.addWidget(c); self.tags_sc.setVisible(True); self.scan_btn.setText("Scan Specific Videos  →")
    def _rem_chip(self, path, widget):
        if path in self.target_paths: self.target_paths.remove(path)
        widget.setParent(None); 
        if self.tags_l.count() == 0: self.tags_sc.setVisible(False); self.scan_btn.setText("Scan for Videos  →")
    def refresh_devices(self, force=False):
        selected_id = self.device_combo.currentData() if hasattr(self, "device_combo") else None
        selected_text = self.device_combo.currentText() if hasattr(self, "device_combo") else ""
        ds = get_devices()
        previous_snapshot = self._device_snapshot
        snapshot = tuple(sorted((d["name"], d.get("id") or d.get("path") or d["name"]) for d in ds))
        if not force and snapshot == self._device_snapshot:
            return

        self._device_snapshot = snapshot
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        if ds:
            for name, device_id in snapshot:
                self.device_combo.addItem(name, device_id)
            match_index = next((i for i in range(self.device_combo.count()) if self.device_combo.itemData(i) == selected_id), -1)
            if match_index < 0:
                match_index = next((i for i in range(self.device_combo.count()) if self.device_combo.itemText(i) == selected_text), 0)
            self.device_combo.setCurrentIndex(max(match_index, 0))
            self.scan_btn.setEnabled(True)
            if previous_snapshot and len(snapshot) > len(previous_snapshot):
                self._set_device_status("New device detected. Ready to scan.", "success")
            elif force:
                noun = "device" if len(snapshot) == 1 else "devices"
                self._set_device_status(f"{len(snapshot)} {noun} available.", "success")
            else:
                noun = "device" if len(snapshot) == 1 else "devices"
                self._set_device_status(f"{len(snapshot)} {noun} ready.", "info")
        else:
            self.device_combo.addItem("Plug in a phone...")
            self.scan_btn.setEnabled(False)
            self._set_device_status("No accessible phone detected. Unlock the phone, switch USB to File Transfer, then tap Reload.", "warning")
        self.device_combo.blockSignals(False)

    def _apply_runtime_config(self):
        self.dest_hint.setText(f"Library folder: {self.config['destinationRoot']}")
        ui_config = self.config.get("ui", {})
        if ui_config.get("autoRefreshDevices", True):
            self._device_poll.start(max(1, int(ui_config.get("deviceRefreshSeconds", 3))) * 1000)
        else:
            self._device_poll.stop()

    def _manual_refresh_devices(self):
        self._set_device_status("Refreshing devices...", "info")
        self.refresh_devices(force=True)

    def _auto_refresh_devices(self):
        if self.stack.currentIndex() != 0:
            return
        if hasattr(self, "scan_worker") and self.scan_worker and self.scan_worker.isRunning():
            return
        if hasattr(self, "sync_worker") and self.sync_worker and self.sync_worker.isRunning():
            return
        self.refresh_devices(force=False)

    def _open_settings(self):
        from .main_window_sub import SettingsDialog

        dialog = SettingsDialog(self, self.config)
        if dialog.exec():
            self.config = load_config()
            self._apply_runtime_config()
            self.refresh_devices(force=True)
            if self._scan_videos or self._scan_subtitles:
                self._all_items = build_transfer_plan(self._scan_videos, self._scan_subtitles, self.config)
                for item in self._all_items:
                    item["selected"] = item.get("selected", True)
            if self._all_items:
                self._apply_sort()
                self._render_library_view(getattr(self, "_af", "All"), show_loading=True)

    def _view_items(self, filter_name: str) -> list[dict]:
        cache_key = (filter_name, getattr(self, "_sort_key", "title"))
        if cache_key in self._view_cache:
            return self._view_cache[cache_key]

        if filter_name == "Movies":
            items = [
                item for item in self._all_items
                if item["media"].type == "movie" and not self._is_series_like_movie(item)
            ]
        elif filter_name == "Shows":
            items = self._build_show_items()
        elif filter_name == "Seasons":
            items = self._build_season_items()
        else:
            items = list(self._all_items)

        items = self._sorted_view_items(items, filter_name)
        self._view_cache[cache_key] = items
        return items

    def _build_season_items(self) -> list[dict]:
        season_map = {}
        for item in self._all_items:
            media = item["media"]
            if media.type != "episode" or media.season is None:
                continue
            key = (media.title, media.season)
            if key not in season_map:
                season_map[key] = {
                    "media": SimpleNamespace(
                        type="season",
                        title=media.title,
                        season=media.season,
                        episode=None,
                        year=media.year,
                        destination_base=f"{media.title} - Season {media.season:02d}",
                        extension="",
                        is_precise=True,
                    ),
                    "group_items": [],
                    "selected": True,
                }
            season_map[key]["group_items"].append(item)

        season_items = []
        for season_item in season_map.values():
            season_item["selected"] = all(child.get("selected", True) for child in season_item["group_items"])
            season_items.append(season_item)
        return season_items

    def _build_show_items(self) -> list[dict]:
        show_map = {}
        for item in self._all_items:
            media = item["media"]
            if media.type == "episode":
                key = normalize_key(media.title)
                if key not in show_map:
                    show_map[key] = {
                        "media": SimpleNamespace(
                            type="show",
                            title=media.title,
                            season=None,
                            episode=None,
                            year=media.year,
                            destination_base=media.title,
                            extension="",
                            is_precise=True,
                        ),
                        "group_items": [],
                        "selected": True,
                    }
                show_map[key]["group_items"].append(item)
            elif self._is_series_like_movie(item):
                key = normalize_key(media.title)
                if key not in show_map:
                    show_map[key] = {
                        "media": SimpleNamespace(
                            type="show",
                            title=media.title,
                            season=None,
                            episode=None,
                            year=media.year,
                            destination_base=media.title,
                            extension="",
                            is_precise=True,
                        ),
                        "group_items": [],
                        "selected": True,
                    }
                show_map[key]["group_items"].append(item)

        show_items = []
        for show_item in show_map.values():
            show_item["selected"] = all(child.get("selected", True) for child in show_item["group_items"])
            show_items.append(show_item)
        return show_items

    def _sorted_view_items(self, items: list[dict], filter_name: str) -> list[dict]:
        key = getattr(self, "_sort_key", "title")

        def media_value(item):
            return item["media"]

        def title_key(item):
            media = media_value(item)
            return (media.title.lower(), media.season or 0, media.episode or 0, media.destination_base.lower())

        if key == "title_desc":
            return sorted(items, key=title_key, reverse=True)
        if key == "year_desc":
            return sorted(
                items,
                key=lambda item: (
                    -(media_value(item).year or -1),
                    media_value(item).title.lower(),
                    media_value(item).season or 0,
                    media_value(item).episode or 0,
                ),
            )
        if key == "season":
            return sorted(
                items,
                key=lambda item: (
                    media_value(item).title.lower(),
                    media_value(item).season or 0,
                    media_value(item).episode or 0,
                ),
            )
        return sorted(items, key=title_key)

    def _is_series_like_movie(self, item: dict) -> bool:
        media = item["media"]
        if media.type != "movie":
            return False
        title_key = normalize_key(media.title)
        if not title_key:
            return False
        if any(
            other["media"].type == "episode" and normalize_key(other["media"].title) == title_key
            for other in self._all_items
        ):
            return True
        if media.is_precise:
            return False
        family_count = sum(
            1
            for other in self._all_items
            if other["media"].type == "movie" and normalize_key(other["media"].title) == title_key
        )
        return family_count >= 2

    def _render_library_view(self, filter_name: str, show_loading: bool):
        if not hasattr(self, "library_grid"):
            return
        if show_loading:
            loading_label = {
                "Movies": "Loading movies...",
                "Shows": "Loading shows...",
                "Seasons": "Loading seasons...",
            }.get(filter_name, "Loading library...")
            self.library_grid.show_loading(loading_label)
            self._library_render_token += 1
            token = self._library_render_token
            QtCore.QTimer.singleShot(0, lambda: self._commit_library_render(token, filter_name))
            return
        self._commit_library_render(self._library_render_token, filter_name)

    def _commit_library_render(self, token: int, filter_name: str):
        if token != self._library_render_token and token != 0:
            return
        items = self._view_items(filter_name)
        fallback_w = max(self.library_grid.width(), self.stack.width(), self.width())
        self.library_grid.render_items(items, fallback_w)

    def _view_label_plural(self) -> str:
        return {"Movies": "movies", "Shows": "shows", "Seasons": "seasons"}.get(getattr(self, "_af", "All"), "videos")

    def _copy_button_label(self, selected_count: int) -> str:
        if selected_count <= 0:
            return "Copy Selected Videos to this Device  →"
        noun_map = {
            "All": ("video", "videos"),
            "Movies": ("movie", "movies"),
            "Shows": ("show", "shows"),
            "Seasons": ("season", "seasons"),
        }
        singular, plural = noun_map.get(getattr(self, "_af", "All"), ("video", "videos"))
        noun = singular if selected_count == 1 else plural
        return f"Copy {selected_count} {noun} to this Device  →"

    def _set_device_status(self, text: str, state: str = "info"):
        if not hasattr(self, "device_status_lbl"):
            return
        self.device_status_lbl.setProperty("state", state)
        self.device_status_lbl.setText(text)
        self.device_status_lbl.style().unpolish(self.device_status_lbl)
        self.device_status_lbl.style().polish(self.device_status_lbl)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
