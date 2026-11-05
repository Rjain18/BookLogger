import tempfile
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit
import unittest
from pathlib import Path
from unittest.mock import patch

from app import BookLogger
from catalogue import Catalogue
from qt_sheet import DateDropdown, display_date


class SheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.catalogue = Catalogue(self.temporary.name)
        self.app = BookLogger(self.catalogue)
        self.addCleanup(self.app.deleteLater)
        self.app.show()
        self.application.processEvents()
        self.app.sheet.cancel_edit()
        self.key = next(iter(self.app.drafts))

    def create_book(self):
        self.assertTrue(self.app.update_cell(self.key, "name", "Test book"))
        self.assertTrue(self.app.update_cell(self.key, "author", "Test author"))
        return self.catalogue.books[0]["serial"]

    def test_new_row_and_persistence(self):
        self.assertEqual(len(self.app.sheet.rows), 1)
        self.assertEqual(self.catalogue.books, [])
        serial = self.create_book()
        self.assertFalse(self.app.drafts)
        self.assertEqual(self.app.sheet.active[0], serial)
        self.assertEqual(Catalogue(self.temporary.name).books[0]["name"], "Test book")
        self.app.new_book()
        self.assertEqual(len(self.app.sheet.rows), 2)

    def test_inline_edit_commit_and_cancel(self):
        serial = self.create_book()
        self.app.edit_cell(serial, 1)
        self.app.sheet.editor.clear()
        self.app.sheet.editor.setText("Revised")
        self.assertTrue(self.app.sheet.finish_edit())
        self.assertEqual(self.catalogue.books[0]["name"], "Revised")
        self.app.edit_cell(serial, 1)
        self.app.sheet.editor.clear()
        self.app.sheet.cancel_edit()
        self.assertEqual(self.catalogue.books[0]["name"], "Revised")

    def test_invalid_edit_keeps_editor_and_saved_value(self):
        serial = self.create_book()
        self.app.edit_cell(serial, 3)
        self.app.sheet.editor.clear()
        with patch("app.QMessageBox.warning"):
            self.assertFalse(self.app.sheet.finish_edit())
        self.assertIsNotNone(self.app.sheet.editor)
        self.assertEqual(self.catalogue.books[0]["author"], "Test author")

    def test_dates_are_dropdown_only_and_handle_leap_years(self):
        selected = []
        picker = DateDropdown(self.app, "2024-01-31", lambda value: selected.append(value) or True)
        self.assertFalse(picker.calendar.isDateEditEnabled())
        self.assertFalse(picker.month.isEditable())
        self.assertFalse(picker.year.isEditable())
        self.assertEqual(picker.label.text(), "31-01-2024")
        picker.calendar.setSelectedDate(QDate(2024, 2, 29))
        self.assertEqual(picker.label.text(), "29-02-2024")
        picker.submit()
        self.assertEqual(selected, ["2024-02-29"])
        picker.deleteLater()
        serial = self.create_book()
        with patch("app.DateDropdown.exec") as opened:
            self.app.edit_cell(serial, 4)
        opened.assert_called_once()
        self.assertIsNone(self.app.sheet.editor)

    def test_invalid_date_does_not_modify_saved_book(self):
        serial = self.create_book()
        self.assertTrue(self.app.update_cell(serial, "start_date", "2026-03-01"))
        with patch("app.QMessageBox.warning"):
            self.assertFalse(self.app.update_cell(serial, "end_date", "2026-02-28"))
        self.assertEqual(self.catalogue.books[0]["end_date"], "")

    def test_draft_image_survives_row_completion(self):
        path = Path(self.temporary.name) / "cover.png"
        image = QImage(2, 2, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.blue)
        self.assertTrue(image.save(str(path)))
        self.assertTrue(self.app.update_cell(self.key, "image", "", image_source=str(path)))
        self.create_book()
        self.assertTrue(self.catalogue.image_path(self.catalogue.books[0]).exists())

    def test_notes_search_export_and_delete(self):
        serial = self.create_book()
        self.app.update_cell(serial, "notes", "Line one\nLine two")
        self.app.query.setText("missing")
        self.assertEqual(self.app.sheet.rows, [])
        self.app.query.setText("line two")
        self.assertEqual(len(self.app.sheet.rows), 1)
        path = Path(self.temporary.name) / "books.csv"
        with patch("app.QFileDialog.getSaveFileName", return_value=(str(path), "")), patch("app.QMessageBox.information"):
            self.app.export()
        self.assertIn("Line one\nLine two", path.read_text(encoding="utf-8-sig"))
        self.app.sheet.select(serial)
        with patch.object(self.app, "confirm", return_value=True):
            self.app.delete_book()
        self.assertEqual(self.catalogue.books, [])

    def test_display_and_csv_dates_preserve_iso_storage(self):
        serial = self.create_book()
        self.app.update_cell(serial, "start_date", "2024-02-29")
        self.assertEqual(self.app.sheet.item(0, 4).text(), "29-02-2024")
        self.assertEqual(Catalogue(self.temporary.name).books[0]["start_date"], "2024-02-29")
        self.assertEqual(display_date("2026-11-05"), "05-11-2026")
        path = Path(self.temporary.name) / "dates.csv"
        with patch("app.QFileDialog.getSaveFileName", return_value=(str(path), "")), patch("app.QMessageBox.information"):
            self.app.export()
        self.assertIn("29-02-2024", path.read_text(encoding="utf-8-sig"))

    def test_add_row_cell_and_keyboard_editing(self):
        serial = self.create_book()
        self.app.sheet.clicked_cell(len(self.app.sheet.rows), 1)
        self.assertEqual(len(self.app.drafts), 1)
        self.assertIsInstance(self.app.sheet.editor, QLineEdit)
        QTest.keyClick(self.app.sheet.editor, Qt.Key.Key_Escape)
        self.assertIsNone(self.app.sheet.editor)
        self.app.edit_cell(serial, 1)
        self.app.sheet.editor.setText("Keyboard book")
        QTest.keyClick(self.app.sheet.editor, Qt.Key.Key_Return)
        self.assertEqual(self.catalogue.books[0]["name"], "Keyboard book")
        self.app.edit_cell(serial, 6)
        self.assertIsInstance(self.app.sheet.editor, QPlainTextEdit)
        self.app.sheet.editor.setPlainText("Multiple\nlines")
        QTest.keyClick(self.app.sheet.editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.catalogue.books[0]["notes"], "Multiple\nlines")

    def test_theme_toggle_preserves_unsaved_editor_and_row_colors(self):
        self.app.edit_cell(self.key, 1)
        self.app.sheet.editor.setText("Unsaved title")
        self.app.theme_button.click()
        self.assertTrue(self.app.dark_mode)
        self.assertEqual(self.app.theme_button.text(), "Light mode")
        self.assertEqual(self.app.sheet.editor.text(), "Unsaved title")
        self.assertEqual(self.app.sheet.item(0, 1).background().color().name(), "#3b3325")
        self.assertEqual(self.app.sheet.item(len(self.app.sheet.rows), 1).foreground().color().name(), "#c7d2fe")
        self.app.theme_button.click()
        self.assertFalse(self.app.dark_mode)
        self.assertEqual(self.app.sheet.editor.text(), "Unsaved title")
        self.assertEqual(self.app.sheet.item(0, 1).background().color().name(), "#fff8e8")

    def test_calendar_contrast_in_light_and_dark_themes(self):
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QAbstractItemView
        picker = DateDropdown(self.app, "2026-11-06", lambda _: True)
        picker.show()
        for dark in (False, True, False):
            if self.app.dark_mode != dark:
                self.app.toggle_theme()
            self.application.processEvents()
            expected = "#e2e8f0" if dark else "#24324b"
            self.assertEqual(picker.calendar.weekdayTextFormat(Qt.DayOfWeek.Monday).foreground().color().name(), expected)
            self.assertEqual(picker.calendar.headerTextFormat().foreground().color().name(), expected)
            view = picker.calendar.findChild(QAbstractItemView)
            self.assertEqual(view.palette().color(QPalette.ColorRole.Text).name(), expected)
            self.assertEqual(picker.month.palette().color(QPalette.ColorRole.Text).name(), expected)
            self.assertFalse(picker.calendar.isDateEditEnabled())
            self.assertEqual(picker.label.text(), "06-11-2026")
        picker.deleteLater()

    def test_clear_date_and_reject_invalid_selection(self):
        serial = self.create_book()
        self.app.update_cell(serial, "start_date", "2026-03-01")
        picker = DateDropdown(self.app, "", lambda value: self.app.update_cell(serial, "end_date", value))
        picker.calendar.setSelectedDate(QDate(2026, 2, 28))
        with patch("app.QMessageBox.warning"):
            self.assertFalse(picker.submit())
        self.assertTrue(picker.submit(""))
        picker.deleteLater()


if __name__ == "__main__":
    unittest.main()
