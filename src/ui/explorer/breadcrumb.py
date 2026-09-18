"""
OP(AI)UM — Breadcrumb Bar

Clickable path segments for the explorer. Clicking the empty area (or
pressing Alt+D) switches to an editable path field; Enter navigates,
Escape returns to the breadcrumb.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

from src.ui.widgets.icon_button import IconButton


class BreadcrumbBar(QStackedWidget):
    """
    Signals:
        path_requested(str): user wants to navigate to this path ("" = Home).
    """

    path_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(34)

        # Page 0: crumbs
        self._crumb_host = QWidget()
        self._crumb_host.setObjectName("breadcrumb")
        self._crumb_host.setCursor(Qt.CursorShape.IBeamCursor)
        host_layout = QHBoxLayout(self._crumb_host)
        host_layout.setContentsMargins(4, 0, 4, 0)
        host_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("breadcrumbScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._crumbs = QWidget()
        self._crumb_layout = QHBoxLayout(self._crumbs)
        self._crumb_layout.setContentsMargins(0, 0, 0, 0)
        self._crumb_layout.setSpacing(0)
        self._crumb_layout.addStretch()
        self._scroll.setWidget(self._crumbs)
        host_layout.addWidget(self._scroll)
        self.addWidget(self._crumb_host)

        # Page 1: editable path
        self._edit = QLineEdit()
        self._edit.setObjectName("pathEdit")
        self._edit.setPlaceholderText("Type a path and press Enter")
        self._edit.returnPressed.connect(self._commit_edit)
        self.addWidget(self._edit)

        # Event filters last: the filter references attributes created above.
        self._crumb_host.installEventFilter(self)
        self._scroll.viewport().installEventFilter(self)
        self._crumbs.installEventFilter(self)
        self._edit.installEventFilter(self)

        self.set_path("")

    # === Public API ===

    @property
    def path(self) -> str:
        return self._path

    def set_path(self, path: str) -> None:
        self._path = path
        self._edit.setText(path)
        self._rebuild()
        self.setCurrentIndex(0)

    def begin_edit(self) -> None:
        self._edit.setText(self._path)
        self.setCurrentIndex(1)
        self._edit.setFocus()
        self._edit.selectAll()

    # === Internals ===

    def _clear_crumbs(self) -> None:
        while self._crumb_layout.count() > 1:
            item = self._crumb_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()

    def _rebuild(self) -> None:
        self._clear_crumbs()
        insert_at = 0

        home = IconButton("home", "Home", role="text_sub", icon_size=14, object_name="breadcrumbBtn")
        home.setToolTip("Recent files and folders")
        home.setProperty("current", not self._path)
        home.clicked.connect(lambda: self.path_requested.emit(""))
        self._crumb_layout.insertWidget(insert_at, home)
        insert_at += 1

        if not self._path:
            return

        parts = Path(self._path).parts
        for i, seg in enumerate(parts):
            sep = QLabel("›")
            sep.setObjectName("breadcrumbSep")
            sep.setContentsMargins(2, 0, 2, 0)
            self._crumb_layout.insertWidget(insert_at, sep)
            insert_at += 1

            target = str(Path(*parts[: i + 1]))
            label = seg.rstrip("\\/") or seg
            btn = QPushButton(label)
            btn.setObjectName("breadcrumbBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("current", i == len(parts) - 1)
            btn.setToolTip(target)
            btn.clicked.connect(lambda checked=False, p=target: self.path_requested.emit(p))
            self._crumb_layout.insertWidget(insert_at, btn)
            insert_at += 1

        # Scroll to the end so the deepest folder is visible
        self._scroll.horizontalScrollBar().setValue(self._scroll.horizontalScrollBar().maximum())

    def _commit_edit(self) -> None:
        text = self._edit.text().strip().strip('"')
        expanded = os.path.expandvars(os.path.expanduser(text))
        self.setCurrentIndex(0)
        if not expanded:
            self.path_requested.emit("")
        else:
            self.path_requested.emit(expanded)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if watched in (self._crumb_host, self._crumbs, self._scroll.viewport()):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.begin_edit()
                    return True
        if watched is self._edit and event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Escape:
                self.setCurrentIndex(0)
                return True
        if watched is self._edit and event.type() == QEvent.Type.FocusOut:
            self.setCurrentIndex(0)
        return super().eventFilter(watched, event)
