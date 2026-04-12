import os

from PySide6 import QtCore, QtGui, QtWidgets


class MediaCard(QtWidgets.QFrame):
    def __init__(self, item_data, on_selection_changed):
        super().__init__()
        self.setObjectName("MediaCard")
        self.setFixedSize(200, 200)
        self.item_data = item_data
        self._on_selection_changed = on_selection_changed
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        icons_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons"))

        group_items = self._group_items()
        media_type = item_data["media"].type
        icon_name = "movie.svg" if media_type == "movie" else "show.svg"
        icon_pixmap = QtGui.QPixmap(os.path.join(icons_dir, icon_name))
        self.img = QtWidgets.QLabel()
        self.img.setFixedHeight(130)
        self.img.setPixmap(icon_pixmap.scaled(52, 52, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
        self.img.setStyleSheet("background: rgba(0,0,0,0.25); border-top-left-radius: 20px; border-top-right-radius: 20px;")
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
        if group_items and media.type == "show":
            season_count = len({item["media"].season for item in group_items if item["media"].season is not None})
            meta_text = f"SHOW • {season_count} SEASONS • {len(group_items)} EPISODES"
            title_text = media.title
        elif group_items:
            meta_text = f"SEASON • {len(group_items)} EPISODES"
            title_text = f"{media.title}\nSeason {media.season:02d}"
        elif media.type == "episode":
            meta_text = f"EPISODE • S{media.season:02d}E{media.episode:02d}"
            title_text = media.title
        elif getattr(media, "is_precise", False):
            meta_text = "MOVIE"
            title_text = media.title
        else:
            meta_text = "VIDEO"
            title_text = media.title

        meta = QtWidgets.QLabel(meta_text)
        meta.setStyleSheet("color: #007AFF; font-weight: 900; font-size: 9px; letter-spacing: 2px;")
        title = QtWidgets.QLabel(title_text)
        title.setStyleSheet("font-weight: 700; font-size: 14px; color: #FFF;")
        title.setWordWrap(True)
        info_l.addWidget(meta)
        info_l.addWidget(title)
        info_l.addStretch()
        layout.addWidget(self.img)
        layout.addWidget(info)
        self._selected = False
        self.update_style()

    def resizeEvent(self, event):
        self.check.move(self.width() - 34, 12)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self.set_selected(not self._selected)
        self._on_selection_changed()
        super().mousePressEvent(event)

    def is_selected(self):
        selected_count, total_count = self._selection_totals()
        return total_count > 0 and selected_count >= total_count

    def selected_count(self) -> int:
        selected_count, _ = self._selection_totals()
        return selected_count

    def represented_count(self) -> int:
        _, total_count = self._selection_totals()
        return total_count

    def selected_items(self) -> list[dict]:
        group_items = self._group_items()
        if group_items:
            return [item for item in group_items if item.get("selected", True)]
        return [self.item_data] if self._selected else []

    def set_selected(self, value: bool):
        group_items = self._group_items()
        if group_items:
            for item in group_items:
                item["selected"] = value
            self.item_data["selected"] = value
        else:
            self.item_data["selected"] = value
        self._selected = value
        self.update_style()

    def update_style(self):
        selected_count, total_count = self._selection_totals()
        self._selected = total_count > 0 and selected_count >= total_count
        is_partial = 0 < selected_count < total_count
        self.check.setText("–" if is_partial else "✓")
        self.check.setVisible(self._selected or is_partial)
        self.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def _group_items(self) -> list[dict]:
        return list(self.item_data.get("group_items", []))

    def _selection_totals(self) -> tuple[int, int]:
        group_items = self._group_items()
        if group_items:
            selected_count = sum(1 for item in group_items if item.get("selected", True))
            return selected_count, len(group_items)
        return (1 if bool(self.item_data.get("selected", True)) else 0, 1)


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
        self._clear_grid()

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

    def show_loading(self, label: str = "Updating library..."):
        self._items = []
        self.cards = []
        self._clear_grid()

        loading = QtWidgets.QFrame()
        loading.setObjectName("surfaceCard")
        loading.setMaximumWidth(380)
        layout = QtWidgets.QVBoxLayout(loading)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(label)
        title.setObjectName("hero_title")
        title.setStyleSheet("font-size: 22px;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        spinner = QtWidgets.QProgressBar()
        spinner.setRange(0, 0)
        spinner.setTextVisible(False)
        spinner.setFixedHeight(4)

        subtitle = QtWidgets.QLabel("Preparing the next view...")
        subtitle.setObjectName("hero_sub")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(spinner)
        layout.addWidget(subtitle)
        self.grid.addWidget(loading, 0, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignCenter)

    def selected_count(self) -> int:
        return sum(card.selected_count() for card in self.cards)

    def selectable_count(self) -> int:
        return sum(card.represented_count() for card in self.cards)

    def selected_items(self) -> list[dict]:
        items = []
        for card in self.cards:
            items.extend(card.selected_items())
        return items

    def set_all_selected(self, value: bool):
        for card in self.cards:
            card.set_selected(value)
        self._on_selection_changed()

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
