from datetime import date
from math import cos, sin, pi

from PySide6.QtCore import QDate, QEvent, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QCalendarWidget, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


from star_rating import StarRating


class CoverDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        base = QStyleOptionViewItem(option)
        self.initStyleOption(base, index)
        icon = index.data(Qt.ItemDataRole.DecorationRole) or QIcon()
        if icon.isNull():
            super().paint(painter, option, index)
            return
        base.icon = QIcon()
        base.text = ""
        style = option.widget.style() if option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, base, painter, option.widget)
        bounds = option.rect.adjusted(10, 8, -10, -8)
        size = QSize(min(62, bounds.width()), min(68, bounds.height()))
        pixmap = icon.pixmap(size)
        painter.save()
        painter.setClipRect(bounds)
        painter.drawPixmap(bounds.center().x() - pixmap.width() // 2, bounds.center().y() - pixmap.height() // 2, pixmap)
        painter.restore()


def display_date(value):
    return date.fromisoformat(value).strftime("%d-%m-%Y") if value else ""


class DateDropdown(QDialog):
    def __init__(self, parent, value, apply):
        super().__init__(parent)
        self.setWindowTitle("Choose date · DD-MM-YYYY")
        self.setModal(True)
        self.apply = apply
        layout = QVBoxLayout(self)
        self.label = QLabel()
        heading = QHBoxLayout()
        heading.addWidget(self.label)
        heading.addStretch()
        self.help_info = QLabel("ⓘ")
        self.help_info.setAccessibleName("Date selection help")
        self.help_info.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.help_info.setToolTip("Choose a month and year, then click a day and Apply date.<br>Dates display as DD-MM-YYYY and cannot be typed.<br>An end date requires a start date and cannot be earlier.<br>Clear date removes the value; Cancel keeps it unchanged.")
        heading.addWidget(self.help_info)
        layout.addLayout(heading)
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setDateEditEnabled(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        initial = QDate.fromString(value, "yyyy-MM-dd") if value else QDate.currentDate()
        self.calendar.setSelectedDate(initial)
        self.calendar.setNavigationBarVisible(False)
        navigation = QHBoxLayout()
        self.calendar.setToolTip("Click a day to select it. Apply date saves it; double-clicking a day also applies it.")
        self.month = QComboBox()
        self.month.setToolTip("Choose the month to browse. Then select a day in the calendar.")
        self.month.addItems([QDate(2000, month, 1).toString("MMMM") for month in range(1, 13)])
        self.month.setCurrentIndex(initial.month() - 1)
        self.year = QComboBox()
        self.year.setToolTip("Choose the year to browse. Then select a day in the calendar.")
        self.year.addItems([str(year) for year in range(min(1900, initial.year()), max(2100, initial.year()) + 1)])
        self.year.setCurrentText(str(initial.year()))
        navigation.addWidget(self.month)
        navigation.addWidget(self.year)
        layout.addLayout(navigation)
        self.month.currentIndexChanged.connect(self.change_page)
        self.year.currentTextChanged.connect(self.change_page)
        self.calendar.currentPageChanged.connect(self.sync_page)
        self.calendar.selectionChanged.connect(self.update_label)
        self.calendar.activated.connect(lambda _: self.submit())
        layout.addWidget(self.calendar)
        actions = QHBoxLayout()
        for title, callback in (("Clear date", lambda: self.submit("")),
                                ("Cancel", self.reject), ("Apply date", lambda: self.submit())):
            button = QPushButton(title)
            button.setToolTip({"Clear date": "Remove this date from the book.", "Cancel": "Close without changing the date.", "Apply date": "Save the selected day to this book."}[title])
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.update_label()
        self.apply_theme(getattr(parent, "dark_mode", False))

    def apply_theme(self, dark):
        if self.parentWidget() is not None:
            self.setPalette(self.parentWidget().palette())
            self.calendar.setPalette(self.parentWidget().palette())
        foreground = QColor("#e2e8f0" if dark else "#24324b")
        background = QColor("#1b2536" if dark else "#ffffff")
        for day in (Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday, Qt.DayOfWeek.Wednesday,
                    Qt.DayOfWeek.Thursday, Qt.DayOfWeek.Friday, Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            format = QTextCharFormat()
            format.setForeground(QColor("#fda4af" if dark else "#be123c") if day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday) else foreground)
            format.setBackground(background)
            self.calendar.setWeekdayTextFormat(day, format)
        header = QTextCharFormat()
        header.setForeground(foreground)
        header.setBackground(QColor("#263247" if dark else "#edf1f8"))
        self.calendar.setHeaderTextFormat(header)

    def change_page(self, *_):
        self.calendar.setCurrentPage(int(self.year.currentText()), self.month.currentIndex() + 1)

    def sync_page(self, year, month):
        self.month.blockSignals(True)
        self.year.blockSignals(True)
        if self.year.findText(str(year)) < 0:
            self.year.addItem(str(year))
        self.year.setCurrentText(str(year))
        self.month.setCurrentIndex(month - 1)
        self.month.blockSignals(False)
        self.year.blockSignals(False)

    def update_label(self):
        self.label.setText(self.calendar.selectedDate().toString("dd-MM-yyyy"))

    def submit(self, value=None):
        if value is None:
            value = self.calendar.selectedDate().toString("yyyy-MM-dd")
        if self.apply(value):
            self.accept()
            return True
        return False


def rating_stars(value):
    pixmap = QPixmap(100, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for star in range(5):
        points = QPolygonF([QPointF(star * 20 + 10 + (9 if point % 2 == 0 else 4) * cos(-pi / 2 + point * pi / 5),
                                   10 + (9 if point % 2 == 0 else 4) * sin(-pi / 2 + point * pi / 5)) for point in range(10)])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#94a3b8"))
        painter.drawPolygon(points)
        painter.save()
        painter.setClipRect(star * 20, 0, round(20 * max(0, min(1, float(value) - star))), 20)
        painter.setBrush(QColor("#f59e0b"))
        painter.drawPolygon(points)
        painter.restore()
    painter.end()
    return pixmap


class BookSheet(QTableWidget):
    columns = ("serial", "name", "image", "author", "start_date", "end_date", "notes", "rating")
    headings = ("Sr. No, ⓘ", "BOOK NAME ⓘ", "COVER ⓘ", "AUTHOR ⓘ", "START DATE ▾ ⓘ", "END DATE ▾ ⓘ", "NOTES ⓘ", "RATING ★ ⓘ")
    help_text = (
        "Automatic serial number. Read-only and never reused after deletion.",
        "Double-click to enter the book title. Automatically saved when you leave the cell; other fields may be filled later.",
        "Double-click to choose a cover. Right-click this cell to change or remove the cover.",
        "Double-click to enter the author. Automatically saved when you leave the cell; other fields may be filled later.",
        "Click to select a start date. Optional; displayed as DD-MM-YYYY. Typing is disabled.",
        "Click to select an end date. Requires a start date and cannot be earlier. Displayed as DD-MM-YYYY.",
        "Double-click to edit notes. Enter adds a new line; Ctrl+Enter or Tab saves; Esc cancels.",
        "Hover over stars to preview; click to save 1–5 in steps of 0.5. Delete clears; arrow keys adjust the rating.",
    )
    widths = (110, 250, 110, 200, 170, 170, 300, 180)
    new_row_requested = Signal()
    cover_change_requested = Signal(object)
    cover_remove_requested = Signal(object)
    rating_changed = Signal(object, str)

    def __init__(self, parent, edit, image_loader):
        super().__init__(parent)
        self.edit_callback = edit
        self.image_loader = image_loader
        self.rows = []
        self.dark_mode = False
        self.editor = None
        self.editor_cell = None
        self.on_commit = None
        self.setColumnCount(len(self.columns))
        self.setHorizontalHeaderLabels(self.headings)
        for column, text in enumerate(self.help_text):
            self.horizontalHeaderItem(column).setToolTip(text)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(False)
        self.setIconSize(QSize(62, 68))
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(84)
        self.horizontalHeader().setMinimumHeight(46)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setFirstSectionMovable(True)
        self.horizontalHeader().setToolTip("Drag headings to reorder columns; drag their edges to resize. Layout is saved automatically.")
        self.setItemDelegateForColumn(self.columns.index("image"), CoverDelegate(self))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_cover_menu)
        for column, width in enumerate(self.widths):
            self.setColumnWidth(column, width)
        self.horizontalHeader().sectionResized.connect(self.enforce_heading_width)
        self.horizontalHeader().sectionResized.connect(self.position_editor)
        self.horizontalHeader().sectionMoved.connect(self.position_editor)
        self.enforce_heading_width()
        self.cellClicked.connect(self.clicked_cell)
        self.cellDoubleClicked.connect(self.double_clicked_cell)
        self.horizontalScrollBar().valueChanged.connect(self.position_editor)
        self.verticalScrollBar().valueChanged.connect(self.position_editor)

    def create_cover_menu(self, key):
        menu = QMenu(self)
        menu.addAction("Change cover…", lambda: self.cover_change_requested.emit(key))
        remove = menu.addAction("Remove cover", lambda: self.cover_remove_requested.emit(key))
        book = next((book for row_key, book in self.rows if row_key == key), {})
        remove.setEnabled(bool(book.get("image")))
        return menu

    def show_cover_menu(self, point):
        item = self.itemAt(point)
        if item is None or item.row() >= len(self.rows) or item.column() != self.columns.index("image"):
            return
        key = self.rows[item.row()][0]
        if not self.finish_edit():
            return
        self.select(key, item.column())
        menu = self.create_cover_menu(key)
        menu.exec(self.viewport().mapToGlobal(point))
        menu.deleteLater()

    def enforce_heading_width(self, *_):
        header = self.horizontalHeader()
        for column in range(self.columnCount()):
            minimum = header.sectionSizeHint(column)
            if column == self.columns.index("rating"):
                minimum = max(minimum, 180)
            if self.columnWidth(column) < minimum:
                self.setColumnWidth(column, minimum)

    @property
    def active(self):
        row, column = self.currentRow(), self.currentColumn()
        return (self.rows[row][0], column) if 0 <= row < len(self.rows) else None

    def set_rows(self, rows, selected=None):
        active = selected or self.active
        vertical = self.verticalScrollBar().value()
        horizontal = self.horizontalScrollBar().value()
        self.rows = rows
        self.setRowCount(len(rows) + 1)
        for row, (key, book) in enumerate(rows):
            for column, field in enumerate(self.columns):
                if self.cellWidget(row, column) is not None:
                    self.removeCellWidget(row, column)
                text = str(book.get(field, ""))
                if field in ("start_date", "end_date"):
                    text = display_date(text) or "Choose date…"
                elif field == "serial":
                    text = text or "New"
                elif field == "image":
                    text = ""
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setToolTip(str(book.get(field, "")) if field == "notes" else text)
                if isinstance(key, str):
                    item.setBackground(QColor("#3b3325" if self.dark_mode else "#fff8e8"))
                    item.setForeground(QColor("#f5e6c8" if self.dark_mode else "#24324b"))
                if field in ("serial", "image", "start_date", "end_date"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if field == "image":
                    pixmap = self.image_loader(key, book)
                    if pixmap is not None and not pixmap.isNull():
                        item.setIcon(QIcon(pixmap))
                        item.setToolTip("Double-click to change cover; right-click for change/remove options")
                    else:
                        item.setText("+ Cover")
                self.setItem(row, column, item)
                if field == "rating":
                    item.setText("")
                    widget = StarRating(book.get("rating", ""), self)
                    widget.changed.connect(lambda value, key=key: self.rating_changed.emit(key, value))
                    self.setCellWidget(row, column, widget)
        for column in range(len(self.columns)):
            if self.cellWidget(len(rows), column) is not None:
                self.removeCellWidget(len(rows), column)
            item = QTableWidgetItem("+ Add a new book" if column == 1 else "")
            item.setToolTip("Click to add a blank book row. Fill any cell and leave it to save the row automatically.")
            item.setForeground(QColor("#c7d2fe" if self.dark_mode else "#4f46e5"))
            item.setBackground(QColor("#303458" if self.dark_mode else "#eef2ff"))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.setItem(len(rows), column, item)
        if active:
            self.select(*active)
        self.verticalScrollBar().setValue(vertical)
        self.horizontalScrollBar().setValue(horizontal)
        self.position_editor()

    def select(self, key, column=1):
        row = next((i for i, (row_key, _) in enumerate(self.rows) if row_key == key), None)
        if row is not None:
            self.setCurrentCell(row, column)
            self.scrollToItem(self.item(row, column))

    def clicked_cell(self, row, column):
        if not self.finish_edit():
            if self.editor_cell:
                self.select(*self.editor_cell)
            return
        if row == len(self.rows):
            self.new_row_requested.emit()
        elif self.columns[column] in ("start_date", "end_date"):
            self.edit_callback(self.rows[row][0], column)

    def double_clicked_cell(self, row, column):
        if self.finish_edit() and row < len(self.rows) and self.columns[column] not in ("start_date", "end_date"):
            self.edit_callback(self.rows[row][0], column)

    def begin_edit(self, key, column, value, commit):
        if not self.finish_edit():
            return
        self.select(key, column)
        self.editor_cell = (key, column)
        self.on_commit = commit
        if self.columns[column] == "rating":
            self.editor = StarRating(value, self.viewport())
            self.editor.changed.connect(lambda _: self.finish_edit())
        elif self.columns[column] == "notes":
            self.editor = QPlainTextEdit(self.viewport())
            self.editor.setPlainText(value)
        else:
            self.editor = QLineEdit(value, self.viewport())
        self.editor.installEventFilter(self)
        self.position_editor()
        self.editor.show()
        self.editor.setFocus()
        if not isinstance(self.editor, (QComboBox, StarRating)):
            self.editor.selectAll()

    def position_editor(self, *_):
        if self.editor and self.editor_cell:
            key, column = self.editor_cell
            row = next((i for i, (row_key, _) in enumerate(self.rows) if row_key == key), None)
            if row is not None:
                self.editor.setGeometry(self.visualItemRect(self.item(row, column)).adjusted(2, 2, -2, -2))

    def finish_edit(self):
        if self.editor is None:
            return True
        editor = self.editor
        if isinstance(editor, (QComboBox, StarRating)):
            value = editor.currentData()
        else:
            value = editor.toPlainText() if isinstance(editor, QPlainTextEdit) else editor.text()
        if not self.on_commit(value):
            editor.setFocus()
            return False
        self.editor = None
        self.editor_cell = None
        self.on_commit = None
        editor.hide()
        editor.deleteLater()
        return True

    def cancel_edit(self):
        if self.editor:
            self.editor.hide()
            self.editor.deleteLater()
        self.editor = None
        self.editor_cell = None
        self.on_commit = None
        self.setFocus()

    def move_cell(self, backwards=False):
        row, column = self.currentRow(), self.currentColumn()
        header = self.horizontalHeader()
        visual = header.visualIndex(column) + (-1 if backwards else 1)
        if visual >= len(self.columns):
            row, visual = row + 1, 0
        elif visual < 0:
            row, visual = row - 1, len(self.columns) - 1
        self.setCurrentCell(max(0, min(self.rowCount() - 1, row)), header.logicalIndex(visual))

    def save_after_focus_change(self, editor):
        if editor is not self.editor or QApplication.activePopupWidget() is not None:
            return
        focus = QApplication.focusWidget()
        if focus is not editor and (focus is None or not editor.isAncestorOf(focus)):
            self.finish_edit()

    def eventFilter(self, watched, event):
        if watched == self.editor and event.type() == QEvent.Type.FocusOut:
            editor = watched
            QTimer.singleShot(0, lambda: self.save_after_focus_change(editor))
        if watched == self.editor and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.cancel_edit()
                return True
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                if self.finish_edit():
                    self.move_cell(key == Qt.Key.Key_Backtab or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                    self.setFocus()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not isinstance(watched, QPlainTextEdit) or event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    if self.finish_edit():
                        self.setFocus()
                    return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2):
            if self.currentRow() == len(self.rows):
                self.new_row_requested.emit()
            elif self.active and self.finish_edit():
                self.edit_callback(*self.active)
            return
        super().keyPressEvent(event)
