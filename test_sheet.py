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
        self.addCleanup(self.app.settings_timer.stop)
        self.app.show()
        self.application.processEvents()
        self.app.sheet.cancel_edit()
        self.key = next(iter(self.app.drafts))

    def create_book(self):
        self.assertTrue(self.app.update_cell(self.key, "name", "Test book"))
        self.assertTrue(self.app.update_cell(self.catalogue.books[0]["serial"], "author", "Test author"))
        return self.catalogue.books[0]["serial"]

    def test_animated_stars_and_persistence(self):
        from PySide6.QtCore import QPoint
        from star_rating import StarRating
        self.create_book()
        column = self.app.sheet.columns.index("rating")
        widget = self.app.sheet.cellWidget(0, column)
        self.assertIsInstance(widget, StarRating)
        left, top, size = widget.star_bounds()
        position = QPoint(round(left + size * 3.25), round(top + size / 2))
        from PySide6.QtCore import QEvent, QPointF
        from PySide6.QtGui import QMouseEvent
        event = QMouseEvent(QEvent.Type.MouseMove, QPointF(position), QPointF(position), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, event)
        QTest.qWait(160)
        self.assertAlmostEqual(widget.fill, 3.5)
        self.assertEqual(self.catalogue.books[0]["rating"], "")
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=position)
        self.assertEqual(Catalogue(self.temporary.name).books[0]["rating"], 3.5)
        widget = self.app.sheet.cellWidget(0, column)
        QTest.keyClick(widget, Qt.Key.Key_Delete)
        self.assertEqual(self.catalogue.books[0]["rating"], "")

    def test_gui_settings_persist_column_order_width_and_theme(self):
        self.create_book()
        header = self.app.sheet.horizontalHeader()
        header.moveSection(header.visualIndex(2), 0)
        self.app.sheet.setColumnWidth(2, 240)
        self.app.toggle_theme()
        self.app.resize(950, 700)
        self.app.save_gui_settings()
        restored = BookLogger(Catalogue(self.temporary.name))
        try:
            self.assertTrue(restored.dark_mode)
            self.assertEqual(restored.sheet.horizontalHeader().visualIndex(2), 0)
            self.assertEqual(restored.sheet.columnWidth(2), 240)
            self.assertEqual(restored.size(), self.app.size())
            self.assertEqual(restored.sheet.columns[2], "image")
        finally:
            restored.settings_timer.stop()
            restored.deleteLater()

    def test_cover_delegate_and_context_menu(self):
        from qt_sheet import CoverDelegate
        serial = self.create_book()
        column = self.app.sheet.columns.index("image")
        path = Path(self.temporary.name) / "cover.jpeg"
        image = QImage(400, 60, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.cyan)
        image.save(str(path), "JPEG")
        self.app.update_cell(serial, "image", "", image_source=str(path))
        self.assertIsInstance(self.app.sheet.itemDelegateForColumn(column), CoverDelegate)
        self.assertEqual(self.app.sheet.item(0, column).text(), "")
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QPainter, QPixmap
        from PySide6.QtWidgets import QStyleOptionViewItem
        canvas = QPixmap(180, 120)
        canvas.fill(QColor("#ff00ff"))
        painter = QPainter(canvas)
        option = QStyleOptionViewItem()
        option.rect = QRect(20, 20, 110, 84)
        option.widget = self.app.sheet
        option.decorationSize = self.app.sheet.iconSize()
        delegate = self.app.sheet.itemDelegateForColumn(column)
        delegate.paint(painter, option, self.app.sheet.model().index(0, column))
        painter.end()
        rendered = canvas.toImage()
        self.assertEqual(rendered.pixelColor(10, 10).name(), "#ff00ff")
        painted = [(x, y) for y in range(120) for x in range(180) if rendered.pixelColor(x, y).name() != "#ff00ff"]
        self.assertTrue(painted)
        self.assertTrue(all(option.rect.contains(x, y) for x, y in painted))
        menu = self.app.sheet.create_cover_menu(serial)
        with patch("app.QFileDialog.getOpenFileName", return_value=("", "")) as choose:
            menu.actions()[0].trigger()
            choose.assert_called_once()
        self.assertTrue(menu.actions()[1].isEnabled())
        menu.actions()[1].trigger()
        self.assertEqual(Catalogue(self.temporary.name).books[0]["image"], "")
        menu.deleteLater()

    def test_export_menu_contrast(self):
        from PySide6.QtGui import QPalette
        for dark in (False, True):
            if self.app.dark_mode != dark:
                self.app.toggle_theme()
            self.app.export_menu.ensurePolished()
            self.assertIn("QMenu::item:selected", self.app.styleSheet())
            self.assertEqual(self.app.export_menu.palette().color(QPalette.ColorRole.WindowText).name(), "#e2e8f0" if dark else "#24324b")

    def test_heading_minimum_widths(self):
        header = self.app.sheet.horizontalHeader()
        self.assertEqual(self.app.sheet.horizontalHeaderItem(0).text(), "Sr. No, ⓘ")
        for dark in (False, True):
            if dark != self.app.dark_mode:
                self.app.toggle_theme()
            for column in range(self.app.sheet.columnCount()):
                self.app.sheet.setColumnWidth(column, 10)
                self.application.processEvents()
                self.assertGreaterEqual(self.app.sheet.columnWidth(column), header.sectionSizeHint(column))
                self.app.sheet.setColumnWidth(column, 400)
                self.assertGreaterEqual(self.app.sheet.columnWidth(column), 400)

    def test_any_cell_saves_partial_row_and_exports(self):
        self.assertTrue(self.app.update_cell(self.key, "notes", "First detail"))
        self.assertFalse(self.app.drafts)
        restored = Catalogue(self.temporary.name)
        self.assertEqual(restored.books[0]["name"], "")
        self.assertEqual(restored.books[0]["notes"], "First detail")
        backup = Path(self.temporary.name) / "partial.json"
        restored.export_json(backup)
        imported = Catalogue(Path(self.temporary.name) / "imported")
        imported.import_json(backup)
        self.assertEqual(imported.books[0]["notes"], "First detail")

    def test_focus_loss_autosaves_and_toolbar_is_compact(self):
        from PySide6.QtWidgets import QPushButton
        self.app.edit_cell(self.key, 1)
        self.app.sheet.editor.setText("Auto saved")
        self.app.query.setFocus()
        self.application.processEvents()
        self.application.processEvents()
        self.assertIsNone(self.app.sheet.editor)
        self.assertEqual(Catalogue(self.temporary.name).books[0]["name"], "Auto saved")
        texts = [button.text() for button in self.app.findChildren(QPushButton)]
        for removed in ("Save cell", "Remove cover", "Export JSON", "Export CSV"):
            self.assertNotIn(removed, texts)
        self.assertEqual(len(self.app.export_menu.actions()), 2)

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
        self.app.edit_cell(serial, 1)
        self.app.sheet.editor.setText("Cannot save")
        with patch("app.QMessageBox.warning"), patch.object(self.catalogue, "save", side_effect=OSError("disk full")):
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
        self.assertTrue(self.catalogue.image_path(self.catalogue.books[0]).exists())
        self.assertEqual(self.catalogue.books[0]["name"], "")

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
        self.assertEqual(self.app.theme_button.text(), "☀")
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

    def test_symbols_and_contextual_help(self):
        self.assertEqual(self.app.theme_button.text(), "☾")
        self.assertEqual(self.app.help_info.text(), "ⓘ")
        self.assertIn("Quick guide", self.app.help_info.toolTip())
        for column in range(self.app.sheet.columnCount()):
            header = self.app.sheet.horizontalHeaderItem(column)
            self.assertIn("ⓘ", header.text())
            self.assertTrue(header.toolTip())
        self.assertIn("Ctrl+Enter", self.app.sheet.horizontalHeaderItem(6).toolTip())
        self.assertTrue(self.app.query.toolTip())
        picker = DateDropdown(self.app, "", lambda _: True)
        self.assertEqual(picker.help_info.text(), "ⓘ")
        self.assertIn("DD-MM-YYYY", picker.help_info.toolTip())
        self.assertTrue(picker.month.toolTip())
        self.assertTrue(picker.year.toolTip())
        self.app.toggle_theme()
        self.assertEqual(self.app.theme_button.text(), "☀")
        self.assertEqual(self.app.theme_button.toolTip(), "Switch to light mode")
        picker.deleteLater()

    def test_jpeg_cover_selection_and_json_actions(self):
        serial = self.create_book()
        for extension in (".jpg", ".jpeg", ".JPEG"):
            path = Path(self.temporary.name) / ("cover" + extension)
            image = QImage(20, 30, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.red)
            self.assertTrue(image.save(str(path), "JPEG"))
            with patch("app.QFileDialog.getOpenFileName", return_value=(str(path), "")):
                self.app.choose_image(serial)
            self.assertIsNotNone(self.app.load_image(serial, self.catalogue.books[0]))
        backup = Path(self.temporary.name) / "backup.json"
        with patch("app.QFileDialog.getSaveFileName", return_value=(str(backup), "")), patch("app.QMessageBox.information"):
            self.app.export_json()
        with patch("app.QFileDialog.getOpenFileName", return_value=(str(backup), "")), patch.object(self.app, "confirm", return_value=True), patch("app.QMessageBox.information"):
            self.app.import_json()
        self.assertEqual(len(self.catalogue.books), 2)
        self.assertIsNotNone(self.app.load_image(2, self.catalogue.books[1]))

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
