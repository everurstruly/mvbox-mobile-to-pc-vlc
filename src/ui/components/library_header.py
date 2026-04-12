from PySide6 import QtCore, QtWidgets


class LibraryHeader(QtWidgets.QWidget):
    def __init__(
        self,
        page_margin_x: int,
        section_gap: int,
        on_back,
        on_filter,
        on_copy,
        on_select_toggle,
        on_clear_selection,
        on_sort_changed,
    ):
        super().__init__()
        self.setObjectName("library_header")
        self._on_select_toggle = on_select_toggle
        self._page_margin_x = page_margin_x

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(page_margin_x, 24, page_margin_x, 18)
        layout.setSpacing(section_gap)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(14)

        back = QtWidgets.QPushButton("‹")
        back.setObjectName("back_inline")
        back.setFixedSize(44, 44)
        back.clicked.connect(on_back)
        top.addWidget(back, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        title_w = QtWidgets.QWidget()
        title_l = QtWidgets.QHBoxLayout(title_w)
        title_l.setContentsMargins(0, 0, 0, 0)
        title_l.setSpacing(12)

        self.title_icon_lbl = QtWidgets.QLabel("💿")
        self.title_icon_lbl.setStyleSheet("font-size: 22px;")
        title_l.addWidget(self.title_icon_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QtWidgets.QLabel("Scanned Device Library")
        self.title_lbl.setObjectName("hero_title")
        self.title_lbl.setStyleSheet("font-size: 34px;")
        title_l.addWidget(self.title_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.meta_lbl = QtWidgets.QLabel("0 videos")
        self.meta_lbl.setObjectName("hero_sub")
        self.meta_lbl.setStyleSheet("font-size: 14px;")
        title_l.addWidget(self.meta_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        top.addWidget(title_w, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()

        layout.addLayout(top)

        tabs_w = QtWidgets.QWidget()
        tabs_l = QtWidgets.QHBoxLayout(tabs_w)
        tabs_l.setContentsMargins(58, 0, 0, 0)
        tabs_l.setSpacing(8)
        self._filters = {}
        for name in ["All", "Movies", "Shows", "Seasons"]:
            button = QtWidgets.QPushButton({"All": "All videos", "Movies": "Movies", "Shows": "Shows", "Seasons": "Seasons"}[name])
            button.setObjectName("filter_tab")
            button.clicked.connect(lambda _, x=name: on_filter(x))
            self._filters[name] = button
            tabs_l.addWidget(button)

        tabs_l.addStretch()

        self.sort_lbl = QtWidgets.QLabel("SORT")
        self.sort_lbl.setObjectName("section_t")
        tabs_l.addWidget(self.sort_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

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
        self._sort_combo.currentIndexChanged.connect(lambda: on_sort_changed(self._sort_combo.currentData()))
        tabs_l.addWidget(self._sort_combo, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(tabs_w)

        self.footer_bar = QtWidgets.QFrame()
        self.footer_bar.setObjectName("library_footer")
        footer_l = QtWidgets.QHBoxLayout(self.footer_bar)
        footer_l.setContentsMargins(page_margin_x, 10, page_margin_x, 10)
        footer_l.setSpacing(14)

        self._select_cb = QtWidgets.QCheckBox("Select all")
        self._select_cb.setTristate(True)
        self._select_cb.clicked.connect(self._on_checkbox_clicked)
        footer_l.addWidget(self._select_cb, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.summary_lbl = QtWidgets.QLabel("")
        self.summary_lbl.setObjectName("section_t")
        footer_l.addWidget(self.summary_lbl, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.clear_selection_btn = QtWidgets.QPushButton("Dismiss Selection")
        self.clear_selection_btn.setObjectName("ghost")
        self.clear_selection_btn.clicked.connect(on_clear_selection)
        self.clear_selection_btn.setVisible(False)
        footer_l.addWidget(self.clear_selection_btn, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        footer_l.addStretch()

        self.copy_top_btn = QtWidgets.QPushButton("Copy Selected Videos to this Device  →")
        self.copy_top_btn.setObjectName("primary")
        self.copy_top_btn.setFixedHeight(42)
        self.copy_top_btn.clicked.connect(on_copy)
        footer_l.addWidget(self.copy_top_btn, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

    def _on_checkbox_clicked(self, checked: bool):
        if self._select_cb.checkState() == QtCore.Qt.CheckState.PartiallyChecked:
            self._select_cb.blockSignals(True)
            self._select_cb.setCheckState(QtCore.Qt.CheckState.Checked)
            self._select_cb.blockSignals(False)
            self._on_select_toggle(True)
        else:
            self._on_select_toggle(checked)

    def update_select_checkbox(self, selected_count: int, visible_count: int):
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
        noun = "video" if total_count == 1 else "videos"
        self.meta_lbl.setText(f"{total_count} {noun}")
        self.summary_lbl.setText(f"{selected_count} selected" if selected_count > 0 else "")
        self.clear_selection_btn.setVisible(selected_count > 0)

    def set_copy_enabled(self, enabled: bool):
        self.copy_top_btn.setEnabled(enabled)

    def set_copy_label(self, label: str):
        self.copy_top_btn.setText(label)
