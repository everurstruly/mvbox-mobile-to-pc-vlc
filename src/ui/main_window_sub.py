from pathlib import Path

from PySide6 import QtWidgets, QtCore
import pythoncom

from ..core.config_manager import save_config


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(620)
        self.setStyleSheet(parent.styleSheet())

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        title = QtWidgets.QLabel("Settings")
        title.setObjectName("hero_title")
        title.setStyleSheet("font-size: 30px;")
        root.addWidget(title)

        subtitle = QtWidgets.QLabel("Choose where imports go and how device detection behaves.")
        subtitle.setObjectName("hero_sub")
        root.addWidget(subtitle)

        card = QtWidgets.QFrame()
        card.setObjectName("surfaceCard")
        form = QtWidgets.QFormLayout(card)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        destination_row = QtWidgets.QWidget()
        destination_layout = QtWidgets.QHBoxLayout(destination_row)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        destination_layout.setSpacing(10)
        self.destination_edit = QtWidgets.QLineEdit(self.config.get("destinationRoot", ""))
        self.destination_edit.setPlaceholderText("Choose a destination folder")
        browse_btn = QtWidgets.QPushButton("Browse…")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._browse_destination)
        destination_layout.addWidget(self.destination_edit, 1)
        destination_layout.addWidget(browse_btn)
        form.addRow("Library folder", destination_row)

        self.movie_root_edit = QtWidgets.QLineEdit(self.config.get("movieRootName", "Movies"))
        form.addRow("Movie folder name", self.movie_root_edit)

        self.tv_root_edit = QtWidgets.QLineEdit(self.config.get("tvRootName", "TV Shows"))
        form.addRow("TV folder name", self.tv_root_edit)

        self.prefer_android_cb = QtWidgets.QCheckBox("Prefer Android app folders during scan")
        self.prefer_android_cb.setChecked(bool(self.config.get("scan", {}).get("preferAndroidData", True)))
        form.addRow("Scan behavior", self.prefer_android_cb)

        self.auto_refresh_cb = QtWidgets.QCheckBox("Auto-refresh connected devices")
        self.auto_refresh_cb.setChecked(bool(self.config.get("ui", {}).get("autoRefreshDevices", True)))
        form.addRow("Device detection", self.auto_refresh_cb)

        self.device_refresh_spin = QtWidgets.QSpinBox()
        self.device_refresh_spin.setRange(1, 30)
        self.device_refresh_spin.setSuffix(" sec")
        self.device_refresh_spin.setValue(int(self.config.get("ui", {}).get("deviceRefreshSeconds", 3)))
        form.addRow("Refresh interval", self.device_refresh_spin)

        root.addWidget(card)

        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("ghost")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QtWidgets.QPushButton("Save Settings")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        root.addLayout(actions)

    def _browse_destination(self):
        current = self.destination_edit.text().strip() or self.config.get("destinationRoot", "")
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Library Folder", current)
        if chosen:
            self.destination_edit.setText(chosen)

    def _save(self):
        destination = self.destination_edit.text().strip()
        if not destination:
            QtWidgets.QMessageBox.warning(self, "Missing Folder", "Choose a library folder before saving.")
            return

        updated = dict(self.config)
        updated["destinationRoot"] = str(Path(destination).expanduser())
        updated["movieRootName"] = self.movie_root_edit.text().strip() or "Movies"
        updated["tvRootName"] = self.tv_root_edit.text().strip() or "TV Shows"
        updated["scan"] = {
            **self.config.get("scan", {}),
            "preferAndroidData": self.prefer_android_cb.isChecked(),
        }
        updated["ui"] = {
            **self.config.get("ui", {}),
            "autoRefreshDevices": self.auto_refresh_cb.isChecked(),
            "deviceRefreshSeconds": self.device_refresh_spin.value(),
        }
        save_config(updated)
        self.config = updated
        self.accept()

# ── High-Density Folder Picker ──────────────────────────────────────────────
class MtpFolderPickerDialog(QtWidgets.QDialog):
    def __init__(self, parent, device_name, device_id, config):
        super().__init__(parent)
        self.device_name = device_name
        self.device_id = device_id
        self.config = config
        self.selected_paths = []
        self.current_stack = []

        self.setWindowTitle("Choose Folders")
        self.setMinimumSize(540, 560)
        self.setStyleSheet(parent.styleSheet())

        root = QtWidgets.QVBoxLayout(self); root.setContentsMargins(24, 24, 24, 24); root.setSpacing(16)

        # Header: Breadcrumbs
        self.breadcrumb = QtWidgets.QLabel(device_name); self.breadcrumb.setObjectName("section_t"); root.addWidget(self.breadcrumb)
        
        # High-Density Folder List
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 12px; padding: 4px;
            }
            QListWidget::item {
                padding: 6px 12px; border-radius: 6px; margin: 1px 0px;
                color: rgba(255,255,255,0.8); border: 1px solid transparent;
            }
            QListWidget::item:hover { background-color: rgba(255,255,255,0.05); color: #FFF; }
            QListWidget::item:selected { 
                background-color: rgba(0, 122, 255, 0.22); 
                border: 1px solid rgba(0, 122, 255, 0.4);
                color: #FFF; font-weight: 600;
            }
            QListWidget::item:selected:hover { background-color: rgba(0, 122, 255, 0.3); }
        """)
        self.list_widget.itemDoubleClicked.connect(self._drill_down)
        self.list_widget.itemSelectionChanged.connect(self._sync_selection_state)
        root.addWidget(self.list_widget, 1)

        # Status & Navigation
        nav = QtWidgets.QHBoxLayout(); self.back_btn = QtWidgets.QPushButton("← Back"); self.back_btn.setObjectName("ghost"); self.back_btn.clicked.connect(self._drill_up); self.back_btn.setEnabled(False)
        self.status_lbl = QtWidgets.QLabel(""); self.status_lbl.setObjectName("hero_sub"); self.status_lbl.setStyleSheet("font-size: 11px;")
        nav.addWidget(self.back_btn); nav.addStretch(); nav.addWidget(self.status_lbl); root.addLayout(nav)

        # Selected Area
        sel_box = QtWidgets.QFrame(); sel_box.setObjectName("surfaceCard"); sel_box.setFixedHeight(100)
        sl = QtWidgets.QVBoxLayout(sel_box); sl.setContentsMargins(16, 12, 16, 12); sl.setSpacing(8)
        sl.addWidget(QtWidgets.QLabel("SELECTED FOLDERS", objectName="section_t"))
        self.chips_area = QtWidgets.QScrollArea(); self.chips_area.setWidgetResizable(True); self.chips_w = QtWidgets.QWidget(); self.chips_flow = QtWidgets.QHBoxLayout(self.chips_w); self.chips_flow.setContentsMargins(0, 0, 0, 0); self.chips_flow.setSpacing(6); self.chips_area.setWidget(self.chips_w)
        sl.addWidget(self.chips_area)
        root.addWidget(sel_box)

        # Action row
        actions = QtWidgets.QHBoxLayout(); actions.setSpacing(12)
        self.add_btn = QtWidgets.QPushButton("Add Selection"); self.add_btn.setObjectName("secondary"); self.add_btn.setFixedHeight(40); self.add_btn.clicked.connect(self._add_selected); self.add_btn.setEnabled(False)
        cancel_btn = QtWidgets.QPushButton("Cancel"); cancel_btn.setObjectName("ghost"); cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = QtWidgets.QPushButton("Use Selected  →"); self.confirm_btn.setObjectName("primary"); self.confirm_btn.setFixedHeight(44); self.confirm_btn.setEnabled(False); self.confirm_btn.clicked.connect(self._confirm_selection)
        actions.addWidget(self.add_btn); actions.addStretch(); actions.addWidget(cancel_btn); actions.addWidget(self.confirm_btn)
        root.addLayout(actions)

        self._load_folder()
        self._refresh_chips()

    def _load_folder(self):
        self.list_widget.clear(); pythoncom.CoInitialize()
        try:
            from ..devices.mtp_client import get_device_root, get_mtp_subfolder
            root_item = get_device_root(self.device_id)
            if not root_item: self.status_lbl.setText("Phone not responding."); return
            path_str = "/".join(self.current_stack); target = get_mtp_subfolder(root_item.GetFolder, path_str)
            if target:
                items = target.Items()
                names = sorted([i.Name for i in items if i.IsFolder], key=str.lower)
                for name in names:
                    li = QtWidgets.QListWidgetItem(f"📁  {name}"); li.setData(QtCore.Qt.ItemDataRole.UserRole, name); self.list_widget.addItem(li)
                self.status_lbl.setText(f"{self.list_widget.count()} folders found")
            else: self.status_lbl.setText("Empty folder.")
            self.breadcrumb.setText(" › ".join([self.device_name] + self.current_stack))
            self.back_btn.setEnabled(bool(self.current_stack))
            self._sync_selection_state()
        finally: pythoncom.CoUninitialize()

    def _drill_down(self, item): self.current_stack.append(item.data(QtCore.Qt.ItemDataRole.UserRole)); self._load_folder()
    def _drill_up(self):
        if self.current_stack: self.current_stack.pop(); self._load_folder()

    def _add_selected(self):
        items = self.list_widget.selectedItems()
        for i in items: self._register_path("/".join(self.current_stack + [i.data(QtCore.Qt.ItemDataRole.UserRole)]))
        self._sync_selection_state()

    def _confirm_selection(self):
        if self.list_widget.selectedItems():
            self._add_selected()
        if self.selected_paths:
            self.accept()

    def _register_path(self, path):
        if path not in self.selected_paths: self.selected_paths.append(path); self._refresh_chips()

    def _refresh_chips(self):
        while self.chips_flow.count():
            w = self.chips_flow.takeAt(0).widget()
            if w: w.setParent(None)
        if not self.selected_paths: self.chips_flow.addWidget(QtWidgets.QLabel("Pick folders above, then confirm.", objectName="hero_sub"))
        else:
            for path in list(self.selected_paths):
                chip = QtWidgets.QPushButton(f"📁 {path.split('/')[-1]}  ✕"); chip.setObjectName("ghost"); chip.setFixedHeight(28); chip.clicked.connect(lambda _, p=path: self._remove_path(p)); self.chips_flow.addWidget(chip)
        self.confirm_btn.setEnabled(bool(self.selected_paths) or bool(self.list_widget.selectedItems()))

    def _remove_path(self, path):
        if path in self.selected_paths: self.selected_paths.remove(path)
        self._refresh_chips()

    def _sync_selection_state(self):
        selected_now = len(self.list_widget.selectedItems())
        if selected_now:
            self.status_lbl.setText(f"{self.list_widget.count()} folders found • {selected_now} selected")
        elif self.list_widget.count():
            self.status_lbl.setText(f"{self.list_widget.count()} folders found")
        self.add_btn.setEnabled(selected_now > 0)
        self.confirm_btn.setEnabled(bool(self.selected_paths) or selected_now > 0)
