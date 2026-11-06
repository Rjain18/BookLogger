import csv
import os
import re
import sys
from pathlib import Path
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImageReader, QKeySequence, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from catalogue import Catalogue
from qt_sheet import BookSheet, DateDropdown, display_date


STYLE = """
QWidget { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; color: #24324b; }
QMainWindow, QDialog { background: #f3f5fb; }
QLabel#title { font-size: 32px; font-weight: 700; color: #18233c; }
QLabel#subtitle, QLabel#status { color: #718096; }
QLabel#badge { background: #e8eaff; color: #4f46e5; border-radius: 12px; padding: 6px 14px; font-weight: 600; }
QPushButton { background: white; border: 1px solid #dde3ed; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #eef2ff; border-color: #a5b4fc; }
QPushButton#primary { background: #4f46e5; color: white; border: none; }
QPushButton#primary:hover { background: #4338ca; }
QPushButton#danger { color: #c24154; }
QMenu { background: white; color: #24324b; border: 1px solid #dde3ed; padding: 6px; }
QMenu::item { padding: 10px 18px; background: transparent; color: #24324b; }
QMenu::item:selected { background: #4f46e5; color: white; }
QMenu::item:disabled { color: #718096; }
QLineEdit, QPlainTextEdit { background: white; border: 1px solid #dbe2ef; border-radius: 6px; padding: 8px; selection-background-color: #c7d2fe; }
QLineEdit:focus, QPlainTextEdit:focus { border: 2px solid #6366f1; }
QTableWidget { background: white; alternate-background-color: #f8faff; border: 1px solid #e0e6f0; border-radius: 10px; gridline-color: #e6ebf3; selection-background-color: #e5e9ff; selection-color: #24324b; }
QTableWidget::item { padding: 10px; }
QTableWidget::item:selected { border: 2px solid #6366f1; }
QHeaderView::section { background: #edf1f8; color: #64748b; border: none; border-right: 1px solid #e0e6f0; padding: 12px; font-size: 11px; font-weight: 700; }
QScrollBar:vertical { background: #f3f5fb; width: 12px; }
QScrollBar:horizontal { background: #f3f5fb; height: 12px; }
QScrollBar::handle { background: #c3ccdc; border-radius: 5px; min-height: 30px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QComboBox { background: white; color: #24324b; border: 1px solid #dbe2ef; border-radius: 6px; padding: 8px; min-width: 95px; }
QComboBox QAbstractItemView { background: white; color: #24324b; selection-background-color: #4f46e5; selection-color: white; }
QCalendarWidget QWidget { background: white; color: #24324b; }
QCalendarWidget QAbstractItemView { background: white; alternate-background-color: #edf1f8; color: #24324b; selection-background-color: #4f46e5; selection-color: white; }
"""

DARK_COLORS = {
    "#24324b": "#e2e8f0", "#f3f5fb": "#111827", "#18233c": "#f1f5f9",
    "#718096": "#a6b4c8", "#e8eaff": "#303458", "#4f46e5": "#818cf8",
    "#dde3ed": "#3b475c", "#eef2ff": "#303458", "#a5b4fc": "#a5b4fc",
    "#4338ca": "#6366f1", "#c24154": "#fda4af", "#dbe2ef": "#3b475c",
    "#c7d2fe": "#414a7b", "#6366f1": "#a5b4fc", "#f8faff": "#202c40",
    "#e0e6f0": "#3b475c", "#e6ebf3": "#344156", "#e5e9ff": "#374367",
    "#edf1f8": "#263247", "#64748b": "#b8c5d8", "#c3ccdc": "#52627c",
}


def theme_palette(dark):
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#111827" if dark else "#f3f5fb",
        QPalette.ColorRole.WindowText: "#e2e8f0" if dark else "#24324b",
        QPalette.ColorRole.Base: "#1b2536" if dark else "#ffffff",
        QPalette.ColorRole.AlternateBase: "#263247" if dark else "#edf1f8",
        QPalette.ColorRole.Text: "#e2e8f0" if dark else "#24324b",
        QPalette.ColorRole.Button: "#263247" if dark else "#ffffff",
        QPalette.ColorRole.ButtonText: "#e2e8f0" if dark else "#24324b",
        QPalette.ColorRole.Highlight: "#6366f1" if dark else "#4f46e5",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#263247" if dark else "#ffffff",
        QPalette.ColorRole.ToolTipText: "#e2e8f0" if dark else "#24324b",
        QPalette.ColorRole.PlaceholderText: "#a6b4c8" if dark else "#64748b",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#a6b4c8" if dark else "#64748b"))
    return palette


class BookLogger(QMainWindow):
    def __init__(self, catalogue):
        super().__init__()
        self.catalogue = catalogue
        catalogue.directory.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(catalogue.directory / "gui.ini"), QSettings.Format.IniFormat)
        self.settings_timer = QTimer(self)
        self.settings_timer.setSingleShot(True)
        self.settings_timer.setInterval(250)
        self.settings_timer.timeout.connect(self.save_gui_settings)
        self.drafts = {}
        self.draft_images = {}
        self.draft_counter = 0
        self.photo_cache = {}
        self.setWindowTitle("BookLogger · Your reading space")
        self.resize(1380, 820)
        self.setMinimumSize(950, 560)
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        outer = QWidget()
        self.setCentralWidget(outer)
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(32, 28, 32, 22)
        layout.setSpacing(18)
        header = QHBoxLayout()
        title = QLabel("BookLogger")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.badge = QLabel()
        self.badge.setObjectName("badge")
        header.addWidget(self.badge)
        self.theme_button = QPushButton("☾")
        self.theme_button.setFixedWidth(46)
        self.theme_button.setAccessibleName("Toggle light and dark mode")
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        self.help_info = QLabel("ⓘ")
        self.help_info.setAccessibleName("Catalogue help")
        self.help_info.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.help_info.setToolTip("<b>Quick guide</b><br>Double-click a cell to edit. Enter or Tab saves; Esc cancels.<br>For notes, Enter adds a line and Ctrl+Enter saves.<br>Rows save automatically when you leave a cell. Filling any cell saves a new row.<br>Hover over column headings for field-specific help.")
        header.addWidget(self.help_info)
        layout.addLayout(header)
        subtitle = QLabel("Your reading space. One book, one row, every chapter remembered.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        toolbar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search books, authors or notes…")
        self.query.setClearButtonEnabled(True)
        self.query.setToolTip("Search saved books by serial number, title, author or notes. Blank new rows remain visible.")
        toolbar.addWidget(self.query, 1)
        self.export_button = QPushButton("Export ▾")
        self.export_button.setToolTip("Export all saved books as a JSON backup with covers or as a CSV spreadsheet.")
        self.export_menu = QMenu(self.export_button)
        self.export_menu.addAction("JSON backup (with covers)", self.export_json)
        self.export_menu.addAction("CSV spreadsheet", self.export)
        self.export_button.setMenu(self.export_menu)
        toolbar.addWidget(self.export_button)
        for title, command, name in (("Import JSON", self.import_json, ""),
                                      ("Delete row", self.delete_book, "danger"),
                                      ("+ New book", self.new_book, "primary")):
            button = QPushButton(title)
            button.setObjectName(name)
            button.setToolTip({
                "Import JSON": "Append books from a JSON backup with new serial numbers. Existing books are preserved; repeated imports add duplicates.",

                "Delete row": "Delete the selected book row after confirmation. Serial numbers are not reused.",
                "+ New book": "Add a blank book row (Ctrl+N). Filling any cell saves the row automatically when you leave the cell.",
            }[title])
            button.clicked.connect(command)
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.sheet = BookSheet(outer, self.edit_cell, self.load_image)
        self.sheet.new_row_requested.connect(self.new_book)
        self.sheet.cover_change_requested.connect(self.choose_image)
        self.sheet.cover_remove_requested.connect(lambda key: self.update_cell(key, "image", ""))
        self.sheet.rating_changed.connect(self.change_rating)
        layout.addWidget(self.sheet, 1)
        hint = QLabel("ⓘ  Double-click to edit  ·  Click dates to select (DD-MM-YYYY)  ·  Tab to move  ·  Ctrl+Enter to save notes  ·  Esc to cancel")
        hint.setObjectName("subtitle")
        layout.addWidget(hint)
        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setToolTip("Books and covers are stored locally. Back up books.json together with the images folder. Rows with any filled cell are saved automatically; completely blank new rows are not saved.")
        layout.addWidget(self.status)
        self.query.textChanged.connect(self.search_changed)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_book)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_book)
        self.apply_theme()
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        header = self.sheet.horizontalHeader()
        state = self.settings.value("columns")
        if state is not None:
            header.restoreState(state)
        self.sheet.enforce_heading_width()
        header.sectionResized.connect(lambda *_: self.settings_timer.start())
        header.sectionMoved.connect(lambda *_: self.settings_timer.start())
        self.refresh()
        if not catalogue.books:
            self.new_book()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.settings_timer.start()

    def save_gui_settings(self):
        self.settings.setValue("dark_mode", self.dark_mode)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("columns", self.sheet.horizontalHeader().saveState())
        self.settings.sync()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sheet"):
            self.settings_timer.start()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "sheet"):
            self.settings_timer.start()

    def change_rating(self, key, value):
        if not self.sheet.finish_edit():
            self.refresh()
            return
        self.update_cell(key, "rating", value)

    def apply_theme(self):
        style = STYLE
        if self.dark_mode:
            style = re.sub(r"#[0-9a-f]{6}|\bwhite\b", lambda match: "#1b2536" if match.group() == "white" else DARK_COLORS.get(match.group(), match.group()), style)
            style += "\nQPushButton#primary { color: #111827; }\nQComboBox QAbstractItemView, QCalendarWidget QAbstractItemView { selection-color: #ffffff; }"
        self.setPalette(theme_palette(self.dark_mode))
        self.setStyleSheet(style)
        self.theme_button.setText("☀" if self.dark_mode else "☾")
        self.theme_button.setToolTip("Switch to light mode" if self.dark_mode else "Switch to dark mode")
        self.sheet.dark_mode = self.dark_mode
        self.refresh()
        for picker in self.findChildren(DateDropdown):
            picker.apply_theme(self.dark_mode)

    def refresh(self, selected=None):
        books = self.catalogue.search(self.query.text())
        self.sheet.set_rows([(book["serial"], book) for book in books] + list(self.drafts.items()), selected)
        self.badge.setText(f"{len(self.catalogue.books)} books in your library")
        self.status.setText(f"{len(books)} shown · {len(self.drafts)} blank new rows · Changes save when you leave a cell · Saved locally: {self.catalogue.directory}")

    def search_changed(self, *_):
        if self.sheet.finish_edit():
            self.refresh()

    def get_book(self, key):
        if key in self.drafts:
            return self.drafts[key].copy()
        return next((book.copy() for book in self.catalogue.books if book["serial"] == key), None)

    def new_book(self):
        if not self.sheet.finish_edit():
            return
        self.draft_counter += 1
        key = f"draft-{self.draft_counter}"
        self.drafts[key] = {field: "" for field in BookSheet.columns}
        self.refresh()
        self.sheet.select(key, 1)
        self.edit_cell(key, 1)

    def edit_cell(self, key, column):
        field = BookSheet.columns[column]
        book = self.get_book(key)
        if field == "serial" or book is None:
            return
        if field in ("start_date", "end_date"):
            picker = DateDropdown(self, book.get(field, ""), lambda value: self.update_cell(key, field, value))
            picker.exec()
        elif field == "image":
            self.choose_image(key)
        else:
            self.sheet.begin_edit(key, column, book.get(field, ""),
                                  lambda value: self.update_cell(key, field, value))

    def update_cell(self, key, field, value, image_source=None):
        book = self.get_book(key)
        if book is None:
            return False
        book[field] = value.strip()
        draft = key in self.drafts
        source = image_source or self.draft_images.get(key)
        if field == "image" and not image_source:
            source = None
        selected = self.sheet.active
        try:
            if draft and not (any(book.get(key, "") not in ("", None) for key in BookSheet.columns if key != "serial") or source):
                Catalogue.validate(book)
                self.drafts[key] = book
                if field == "image" and not image_source:
                    self.draft_images.pop(key, None)
                elif image_source:
                    self.draft_images[key] = image_source
            else:
                saved = self.catalogue.save(book, None if draft else key, source)
                if draft:
                    del self.drafts[key]
                    self.draft_images.pop(key, None)
                    if self.sheet.active and self.sheet.active[0] == key:
                        selected = (saved["serial"], self.sheet.active[1])
                self.photo_cache.clear()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot save cell", str(error))
            return False
        self.refresh(selected)
        return True

    def load_image(self, key, book):
        path = self.draft_images.get(key) or self.catalogue.image_path(book)
        if not path:
            return None
        cache_key = str(path)
        if cache_key in self.photo_cache:
            return self.photo_cache[cache_key]
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            return None
        photo = QPixmap.fromImage(image).scaled(62, 68, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.photo_cache[cache_key] = photo
        return photo

    def choose_image(self, key):
        path, _ = QFileDialog.getOpenFileName(self, "Choose book cover", "", "Images (*.png *.jpg *.jpeg *.JPG *.JPEG *.gif *.bmp *.webp);;JPEG images (*.jpg *.jpeg *.JPG *.JPEG);;All files (*)")
        if path:
            probe = f"probe-{key}"
            self.draft_images[probe] = path
            valid = self.load_image(probe, {})
            self.draft_images.pop(probe, None)
            if valid:
                self.update_cell(key, "image", "", image_source=path)
            else:
                QMessageBox.warning(self, "Cannot open image", "Choose a valid image file.")

    def remove_image(self):
        if self.sheet.finish_edit() and self.sheet.active:
            self.update_cell(self.sheet.active[0], "image", "")

    def save_book(self):
        self.sheet.finish_edit()
        return "break"

    def delete_book(self):
        if not self.sheet.finish_edit() or not self.sheet.active:
            return
        key = self.sheet.active[0]
        if not self.confirm("Delete row", "Permanently delete this book row?"):
            return
        try:
            if key in self.drafts:
                del self.drafts[key]
                self.draft_images.pop(key, None)
            else:
                self.catalogue.delete(key)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot delete book", str(error))
            return
        self.photo_cache.clear()
        self.refresh()

    def confirm(self, title, text):
        return QMessageBox.question(self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        if not self.sheet.finish_edit() or (self.drafts and not self.confirm("Unsaved rows", "Rows with any filled cell are saved automatically; completely blank new rows are not saved. Close and discard them?")):
            event.ignore()
            return
        self.settings_timer.stop()
        self.save_gui_settings()
        event.accept()

    def import_json(self):
        if not self.sheet.finish_edit():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import JSON backup", "", "JSON files (*.json)")
        if not path:
            return
        if not self.confirm("Import books", "Append books from this JSON file with new serial numbers? Existing books are preserved. Importing the same file again adds duplicates."):
            return
        try:
            count = self.catalogue.import_json(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot import JSON", str(error))
            return
        self.photo_cache.clear()
        self.query.clear()
        self.refresh()
        QMessageBox.information(self, "Import complete", f"Imported {count} books. Existing books were preserved.")

    def export_json(self):
        if not self.sheet.finish_edit():
            return
        if self.drafts and not self.confirm("Unsaved rows", "Export saved books only? Completely blank new rows will not be included."):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON backup", "books-backup.json", "JSON files (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.catalogue.export_json(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot export JSON", str(error))
            return
        QMessageBox.information(self, "Export complete", f"Exported {len(self.catalogue.books)} books with covers.")

    def export(self):
        if not self.sheet.finish_edit():
            return
        if self.drafts and not self.confirm("Unsaved rows", "Export saved books only? Completely blank new rows will not be included."):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export entire catalogue", "books.csv", "CSV files (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        keys = ("serial", "name", "image", "author", "start_date", "end_date", "notes", "rating")
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("Serial number", "Book name", "Book image", "Author", "Start date", "End date", "Notes", "Rating"))
                for book in self.catalogue.books:
                    values = [str(book.get(key, "")) for key in keys]
                    for index in (4, 5):
                        values[index] = display_date(values[index])
                    writer.writerow(["'" + value if value.startswith(("=", "+", "-", "@")) else value for value in values])
        except OSError as error:
            QMessageBox.warning(self, "Cannot export", str(error))
            return
        QMessageBox.information(self, "Export complete", f"Exported {len(self.catalogue.books)} books.")


def main():
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI", 10))
    directory = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "BookLogger"
    try:
        catalogue = Catalogue(directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        QMessageBox.critical(None, "Cannot load catalogue", f"Your saved file could not be read and has not been changed.\n\n{error}\n\nLocation: {directory}")
        return
    window = BookLogger(catalogue)
    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
