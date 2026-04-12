from PySide6 import QtCore, QtWidgets


class LibraryHeader(QtWidgets.QWidget):
    def __init__(self, page_margin_x: int, section_gap: int, on_back, on_filter, on_copy, on_select_toggle, on_sort_changed):
        super().__init__()
        self.setObjectName("library_header")
        self._on_select_toggle = on_select_toggle
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(page_margin_x, 24, page_margin_x, 20)
        layout.setSpacing(section_gap)

        # ── Top row: back, title, filter tabs, sort, copy ──
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(12)

        back = QtWidgets.QPushButton("←")
        back.setObjectName("back_inline")
        back.setFixedWidth(40)
        back.clicked.connect(on_back)
        top.addWidget(back, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QtWidgets.QLabel("Library")
        self.title_lbl.setObjectName("hero_title")
        self.title_lbl.setStyleSheet("font-size: 34px;")
        top.addWidget(self.title_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        tabs_w = QtWidgets.QWidget()
        tabs_l = QtWidgets.QHBoxLayout(tabs_w)
        tabs_l.setContentsMargins(8, 0, 0, 0)
        tabs_l.setSpacing(8)
        self._filters = {}
        for name in ["All", "Movies", "Shows", "Seasons"]:
            button = QtWidgets.QPushButton({"All": "All videos", "Movies": "Movies", "Shows": "Shows", "Seasons": "Seasons"}[name])
            button.setObjectName("filter_tab")
            button.clicked.connect(lambda _, x=name: on_filter(x))
            self._filters[name] = button
            tabs_l.addWidget(button)
        top.addWidget(tabs_w, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        top.addStretch()

        self.copy_top_btn = QtWidgets.QPushButton("Copy to PC")
        self.copy_top_btn.setObjectName("primary")
        self.copy_top_btn.clicked.connect(on_copy)
        top.addWidget(self.copy_top_btn, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(top)

        # ── Meta row: count label, selected label, select-all checkbox ──
        meta_w = QtWidgets.QWidget()
        meta_l = QtWidgets.QHBoxLayout(meta_w)
        meta_l.setContentsMargins(0, 8, 0, 0)
        meta_l.setSpacing(20)

        self.meta_lbl = QtWidgets.QLabel("0 videos")
        self.meta_lbl.setObjectName("hero_sub")
        self.meta_lbl.setStyleSheet("font-size: 12px;")

        self.summary_lbl = QtWidgets.QLabel("")
        self.summary_lbl.setObjectName("section_t")

        self.sort_lbl = QtWidgets.QLabel("SORT")
        self.sort_lbl.setObjectName("section_t")

        self._sort_combo = QtWidgets.QComboBox()
        self._sort_combo.blockSignals(True)
        self._sort_combo.addItem("Title A–Z", "title")
        self._sort_combo.addItem("Title Z–A", "title_desc")
        self._sort_combo.addItem("Newest Year", "year_desc")
        self._sort_combo.addItem("Season Order", "season")
        self._sort_combo.blockSignals(False)
        self._sort_combo.setFixedHeight(34)
        self._sort_combo.setObjectName("bulk_sort_combo")
        self._sort_combo.setStyleSheet(
            "QComboBox { padding: 4px 12px; font-size: 12px; font-weight: 700; "
            "border-radius: 10px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); }"
            "QComboBox::drop-down { border: none; }"
        )
        self._sort_combo.currentIndexChanged.connect(
            lambda: on_sort_changed(self._sort_combo.currentData())
        )

        # Single tri-state checkbox replacing the old Select All + Clear buttons
        self._select_cb = QtWidgets.QCheckBox("Select all")
        self._select_cb.setTristate(True)
        self._select_cb.clicked.connect(self._on_checkbox_clicked)

        meta_l.addWidget(self.meta_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        meta_l.addWidget(self.summary_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        meta_l.addStretch()
        meta_l.addWidget(self.sort_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        meta_l.addWidget(self._sort_combo, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        meta_l.addWidget(self._select_cb, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(meta_w)

    def _on_checkbox_clicked(self, checked: bool):
        # Tri-state cycles through states on click; we only want checked/unchecked.
        # Force it back to a clean binary state then fire the callback.
        if self._select_cb.checkState() == QtCore.Qt.CheckState.PartiallyChecked:
            # User clicked while partial — treat as "select all"
            self._select_cb.blockSignals(True)
            self._select_cb.setCheckState(QtCore.Qt.CheckState.Checked)
            self._select_cb.blockSignals(False)
            self._on_select_toggle(True)
        else:
            self._on_select_toggle(checked)

    def update_select_checkbox(self, selected_count: int, visible_count: int):
        """Called by MainWindow.refresh_summary to sync checkbox state with grid."""
        self._select_cb.blockSignals(True)
        if selected_count == 0:
            self._select_cb.setCheckState(QtCore.Qt.CheckState.Unchecked)
        elif visible_count > 0 and selected_count >= visible_count:
            self._select_cb.setCheckState(QtCore.Qt.CheckState.Checked)
        else:
            self._select_cb.setCheckState(QtCore.Qt.CheckState.PartiallyChecked)
        self._select_cb.blockSignals(False)

    def set_active_filter(self, filter_name: str):
        for name, button in self._filters.items():
            button.setProperty("active", name == filter_name)
            button.style().unpolish(button)
            button.style().polish(button)

    def set_counts(self, visible_count: int, total_count: int, selected_count: int, label_plural: str = "videos"):
        singular = label_plural[:-1] if label_plural.endswith("s") else label_plural
        if visible_count == total_count:
            noun = singular if total_count == 1 else label_plural
            self.meta_lbl.setText(f"{total_count} {noun}")
        else:
            self.meta_lbl.setText(f"{visible_count} of {total_count} {label_plural}")
        if selected_count > 0:
            self.summary_lbl.setText(f"{selected_count} selected")
        else:
            self.summary_lbl.setText("")

    def set_copy_enabled(self, enabled: bool):
        self.copy_top_btn.setEnabled(enabled)
