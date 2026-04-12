import os
import time
import ctypes
from PySide6 import QtWidgets, QtCore, QtGui

from ..core.config_manager import load_config
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
    background: transparent; border: none; color: rgba(255,255,255,0.75);
    font-size: 14px; font-weight: 700; padding: 8px 12px;
}
QPushButton#back_inline:hover { color: #FFF; }

/* ── Media Card ── */
#MediaCard { background-color: rgba(255, 255, 255, 0.04); border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.08); }
#MediaCard[selected="true"] { border: 2.5px solid #007AFF; background-color: rgba(0, 122, 255, 0.1); }

QComboBox { background-color: rgba(0,0,0,0.3); border: 1px solid #222; border-radius: 14px; padding: 14px 20px; font-size: 15px; color: #FFF; }
QProgressBar { background: rgba(255,255,255,0.04); border-radius: 2px; height: 3px; border: none; }
QProgressBar::chunk { background: #007AFF; border-radius: 2px; }

#surfaceCard { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 24px; }
#library_header { border-bottom: 1px solid rgba(255,255,255,0.06); }

QCheckBox { color: rgba(255,255,255,0.4); font-size: 13px; font-weight: 700; spacing: 8px; background: transparent; border: none; }
QCheckBox:hover { color: #FFF; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid rgba(255,255,255,0.2); background: transparent; }
QCheckBox::indicator:checked { background: #007AFF; border-color: #007AFF; image: none; }
QCheckBox::indicator:indeterminate { background: rgba(0,122,255,0.35); border-color: #007AFF; }
QCheckBox::indicator:hover { border-color: rgba(255,255,255,0.5); }
"""

PAGE_MARGIN_X = 32
SURFACE_INNER_X = 28
LIBRARY_SECTION_GAP = 16

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Windows Taskbar Icon Fix (AppUserModelID)
        try:
            myappid = u'moviebox.sync.desktop.v2'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        self.setWindowTitle("MovieBox Sync"); self.setMinimumSize(500, 500); self.resize(960, 680)
        
        # Set Branding Icon
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
            
        self.config = load_config(); self.setStyleSheet(MASTER_QSS)
        self.target_paths = []; self._all_items = []; self._af = "All"
        self._grid_reflow = QtCore.QTimer(self); self._grid_reflow.setSingleShot(True); self._grid_reflow.timeout.connect(self._reflow_library_grid)
        self._build_ui()

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
        logo_text = QtWidgets.QLabel("MOVIEBOX SYNC"); logo_text.setObjectName("app_logo")
        bl.addWidget(logo_text)
        nl.addWidget(brand_w); nl.addStretch()
        self._dots = []; dot_w = QtWidgets.QWidget(); dl = QtWidgets.QHBoxLayout(dot_w); dl.setSpacing(8)
        for i in range(4):
            d = QtWidgets.QFrame(); d.setObjectName("step_dot"); d.setFixedSize(8, 8); self._dots.append(d); dl.addWidget(d)
        nl.addWidget(dot_w); nl.addStretch()
        self.help_btn = QtWidgets.QPushButton("Support"); self.help_btn.setObjectName("utility"); nl.addWidget(self.help_btn); nl.addSpacing(20)
        self.upd_btn = QtWidgets.QPushButton("Check for Updates"); self.upd_btn.setObjectName("utility"); nl.addWidget(self.upd_btn)
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
        self.device_combo = QtWidgets.QComboBox(); self.device_combo.setFixedHeight(56); cl.addWidget(self.device_combo)
        only_folders_lbl = QtWidgets.QLabel("ONLY THESE FOLDERS (OPTIONAL)"); only_folders_lbl.setObjectName("section_t"); cl.addSpacing(64); cl.addWidget(only_folders_lbl); cl.addSpacing(12)
        self.add_b = QtWidgets.QPushButton("+ Add Folders"); self.add_b.setObjectName("ghost"); self.add_b.setFixedHeight(40); self.add_b.clicked.connect(self._open_picker); cl.addWidget(self.add_b, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.tags_l = QtWidgets.QHBoxLayout(); self.tags_l.setSpacing(8); self.tags_l.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft); self.tags_w = QtWidgets.QWidget(); self.tags_w.setLayout(self.tags_l); self.tags_sc = QtWidgets.QScrollArea(); self.tags_sc.setWidget(self.tags_w); self.tags_sc.setWidgetResizable(True); self.tags_sc.setFixedHeight(48); cl.addWidget(self.tags_sc); self.tags_sc.setVisible(False)
        cl.addSpacing(32); self.scan_btn = QtWidgets.QPushButton("Look for All Videos  →"); self.scan_btn.setObjectName("primary"); self.scan_btn.setFixedHeight(60); self.scan_btn.clicked.connect(self._start_scan)
        cl.addWidget(self.scan_btn); l.addLayout(header); body_l = QtWidgets.QHBoxLayout(); body_l.addStretch(); body_l.addWidget(container); body_l.addStretch(); l.addLayout(body_l); l.addStretch(); self.refresh_devices(); return page

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
        self._all_items = build_transfer_plan(v, s, self.config)
        for item in self._all_items: item["selected"] = item.get("selected", True)
        self._sort_key = "title"
        self._apply_sort()
        self._go(2, 2)
        QtCore.QTimer.singleShot(0, lambda: self._apply_filter("All"))

    def _on_scan_failed(self, msg):
        self.primary_stop_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Scan Failed", str(msg))
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
            self._on_sort_changed,
        )
        l.addWidget(self.library_header)
        self.library_grid = LibraryGrid(PAGE_MARGIN_X, self.refresh_summary)
        l.addWidget(self.library_grid)
        self.import_btn = self.library_header.copy_top_btn
        return page

    def _apply_filter(self, f):
        self._af = f
        self.library_header.set_active_filter(f)
        vis = [i for i in self._all_items if (f == "All" or (f == "Movies" and i['media'].type == "movie") or (f == "Episodes" and i['media'].type == "episode"))]
        fallback_w = max(self.library_grid.width(), self.stack.width(), self.width())
        self.library_grid.render_items(vis, fallback_w)

    def refresh_summary(self):
        visible_count = len(getattr(self.library_grid, "_items", [])) if hasattr(self, "library_grid") else 0
        selected_count = self.library_grid.selected_count() if hasattr(self, "library_grid") else 0
        self.library_header.set_counts(visible_count, len(self._all_items), selected_count)
        self.library_header.update_select_checkbox(selected_count, visible_count)
        self.import_btn.setEnabled(selected_count > 0)
        self.library_header.set_copy_enabled(selected_count > 0)

    def _on_select_toggle(self, checked: bool):
        self.library_grid.set_all_selected(checked)

    def _apply_sort(self):
        key = getattr(self, "_sort_key", "title")
        if key == "title":
            self._all_items.sort(key=lambda x: (0 if x["media"].type == "episode" else 1, x["media"].title.lower()))
        elif key == "season":
            self._all_items.sort(key=lambda x: (
                x["media"].title.lower(),
                x["media"].season or 0,
                x["media"].episode or 0,
            ))
        elif key == "type":
            self._all_items.sort(key=lambda x: (x["media"].type, x["media"].title.lower()))

    def _on_sort_changed(self, sort_key: str):
        self._sort_key = sort_key
        self._apply_sort()
        self._apply_filter(getattr(self, "_af", "All"))

    def _start_import(self):
        selected = self.library_grid.selected_items()
        self._go(1, 3)
        self._scan_title.setText("Copying to PC...")
        self.primary_stop_btn.setText(" Stop Import")
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
        self.primary_stop_btn.setText(" Stop Import")
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
        s = QtWidgets.QLabel("Your videos are ready on your PC."); s.setObjectName("hero_sub"); l.addWidget(s, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        actions = QtWidgets.QWidget(); al = QtWidgets.QHBoxLayout(actions); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(14)
        watch_btn = QtWidgets.QPushButton("Watch now  →"); watch_btn.setObjectName("primary"); watch_btn.setFixedHeight(58); watch_btn.clicked.connect(self._open_dest)
        discover_btn = QtWidgets.QPushButton("Discover New"); discover_btn.setObjectName("secondary"); discover_btn.setFixedHeight(58); discover_btn.clicked.connect(self._start_new_discovery)
        al.addWidget(watch_btn); al.addWidget(discover_btn); l.addWidget(actions, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        return page

    def _open_dest(self): os.startfile(self.config["destinationRoot"])
    def _start_new_discovery(self):
        self._all_items = []
        self.target_paths = []
        while self.tags_l.count():
            item = self.tags_l.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
        self.tags_sc.setVisible(False)
        self.scan_btn.setText("Look for All Videos  →")
        self.refresh_devices()
        self._return_to_setup()
    def _open_picker(self):
        from .main_window_sub import MtpFolderPickerDialog
        d = MtpFolderPickerDialog(self, self.device_combo.currentText(), self._selected_device_ref(), self.config)
        if d.exec(): [ (self.target_paths.append(p), self._add_chip(p)) for p in d.selected_paths if p not in self.target_paths ]
    def _reflow_library_grid(self):
        if hasattr(self, "stack") and self.stack.currentIndex() == 2 and self._all_items:
            self._apply_filter(getattr(self, "_af", "All"))
    def _selected_device_ref(self):
        data = self.device_combo.currentData()
        return str(data if data else self.device_combo.currentText())
    def _add_chip(self, p):
        c = QtWidgets.QPushButton(f"📁 {p.split('/')[-1]} ✕"); c.setObjectName("ghost"); c.clicked.connect(lambda _, x=p, w=c: self._rem_chip(x, w)); self.tags_l.addWidget(c); self.tags_sc.setVisible(True); self.scan_btn.setText("Look for Specific Videos  →")
    def _rem_chip(self, path, widget):
        if path in self.target_paths: self.target_paths.remove(path)
        widget.setParent(None); 
        if self.tags_l.count() == 0: self.tags_sc.setVisible(False); self.scan_btn.setText("Look for All Videos  →")
    def refresh_devices(self):
        self.device_combo.clear(); ds = get_devices()
        if ds: [self.device_combo.addItem(d["name"], d.get("id") or d.get("path") or d["name"]) for d in ds]; self.scan_btn.setEnabled(True)
        else: self.device_combo.addItem("Plug in a phone..."); self.scan_btn.setEnabled(False)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
