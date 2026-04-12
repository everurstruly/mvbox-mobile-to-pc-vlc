from PySide6 import QtCore, QtWidgets


class MediaCard(QtWidgets.QFrame):
    def __init__(self, item_data, on_selection_changed):
        super().__init__()
        self.setObjectName("MediaCard")
        self.setFixedSize(200, 200)
        self.item_data = item_data
        self._selected = bool(item_data.get("selected", True))
        self._on_selection_changed = on_selection_changed
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.img = QtWidgets.QLabel("🎬" if item_data["media"].type == "movie" else "📺")
        self.img.setFixedHeight(130)
        self.img.setStyleSheet("font-size: 42px; background: rgba(0,0,0,0.25); border-top-left-radius: 20px; border-top-right-radius: 20px;")
        self.img.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.check = QtWidgets.QLabel("✓")
        self.check.setStyleSheet("background: #007AFF; color: white; border-radius: 11px; font-weight: 900;")
        self.check.setFixedSize(22, 22)
        self.check.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.check.setParent(self)

        info = QtWidgets.QWidget()
        info_l = QtWidgets.QVBoxLayout(info)
        info_l.setContentsMargins(20, 14, 20, 20)
        info_l.setSpacing(6)

        media = item_data["media"]
        if media.type == "episode":
            meta_text = f"EPISODE • S{media.season:02d}E{media.episode:02d}"
        elif getattr(media, "is_precise", False):
            meta_text = "MOVIE"
        else:
            meta_text = "VIDEO"

        meta = QtWidgets.QLabel(meta_text)
        meta.setStyleSheet("color: #007AFF; font-weight: 900; font-size: 9px; letter-spacing: 2px;")
        title = QtWidgets.QLabel(media.title)
        title.setStyleSheet("font-weight: 700; font-size: 14px; color: #FFF;")
        title.setWordWrap(True)
        info_l.addWidget(meta)
        info_l.addWidget(title)
        info_l.addStretch()
        layout.addWidget(self.img)
        layout.addWidget(info)
        self.update_style()

    def resizeEvent(self, event):
        self.check.move(self.width() - 34, 12)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self.set_selected(not self._selected)
        self._on_selection_changed()
        super().mousePressEvent(event)

    def is_selected(self):
        return self._selected

    def set_selected(self, value: bool):
        self._selected = value
        self.item_data["selected"] = value
        self.update_style()

    def update_style(self):
        self.check.setVisible(self._selected)
        self.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)


class LibraryGrid(QtWidgets.QScrollArea):
    def __init__(self, page_margin_x: int, on_selection_changed):
        super().__init__()
        self._page_margin_x = page_margin_x
        self._on_selection_changed = on_selection_changed
        self._items = []
        self.cards = []
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_w = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.grid_w)
        self.grid.setSpacing(16)
        self.grid.setContentsMargins(page_margin_x, 20, page_margin_x, 32)
        self.setWidget(self.grid_w)
        self.setWidgetResizable(True)

    def render_items(self, items: list[dict], fallback_width: int):
        self._items = list(items)
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)

        self.cards = []
        viewport_w = self.viewport().width()
        usable_w = max(viewport_w, fallback_width) - (self._page_margin_x * 2)
        card_w = 200
        min_slot_w = card_w + self.grid.horizontalSpacing()
        cols = max(1, usable_w // max(min_slot_w, 1))

        if not items:
            empty = QtWidgets.QFrame()
            empty.setObjectName("surfaceCard")
            empty.setMaximumWidth(520)
            el = QtWidgets.QVBoxLayout(empty)
            el.setContentsMargins(28, 28, 28, 28)
            el.setSpacing(10)
            title = QtWidgets.QLabel("Nothing here yet")
            title.setObjectName("hero_title")
            title.setStyleSheet("font-size: 24px;")
            subtitle = QtWidgets.QLabel("Try another tab, change your folder selection, or run a new discovery.")
            subtitle.setObjectName("hero_sub")
            subtitle.setWordWrap(True)
            el.addWidget(title, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
            el.addWidget(subtitle, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(empty, 0, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignCenter)
            self._on_selection_changed()
            return

        for index, item in enumerate(items):
            card = MediaCard(item, self._on_selection_changed)
            self.cards.append(card)
            self.grid.addWidget(card, index // cols, index % cols, QtCore.Qt.AlignmentFlag.AlignCenter)
        self._on_selection_changed()

    def selected_count(self) -> int:
        return sum(1 for card in self.cards if card.is_selected())

    def selected_items(self) -> list[dict]:
        return [card.item_data for card in self.cards if card.is_selected()]

    def set_all_selected(self, value: bool):
        for card in self.cards:
            card.set_selected(value)
        self._on_selection_changed()
