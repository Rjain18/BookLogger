import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from app import BookLogger
from catalogue import Catalogue
from sheet import DateDropdown


class SheetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.catalogue = Catalogue(self.temporary.name)
        try:
            self.app = BookLogger(self.catalogue)
        except tk.TclError as error:
            self.skipTest(f"Desktop display unavailable: {error}")
        self.addCleanup(self.app.destroy)
        self.app.withdraw()
        self.app.update()
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
        self.app.sheet.editor.delete("1.0", "end")
        self.app.sheet.editor.insert("1.0", "Revised")
        self.assertTrue(self.app.sheet.finish_edit())
        self.assertEqual(self.catalogue.books[0]["name"], "Revised")
        self.app.edit_cell(serial, 1)
        self.app.sheet.editor.delete("1.0", "end")
        self.app.sheet.cancel_edit()
        self.assertEqual(self.catalogue.books[0]["name"], "Revised")

    def test_invalid_edit_keeps_editor_and_saved_value(self):
        serial = self.create_book()
        self.app.edit_cell(serial, 3)
        self.app.sheet.editor.delete("1.0", "end")
        with patch("app.messagebox.showerror"):
            self.assertFalse(self.app.sheet.finish_edit())
        self.assertIsNotNone(self.app.sheet.editor)
        self.assertEqual(self.catalogue.books[0]["author"], "Test author")

    def test_dates_are_dropdown_only_and_handle_leap_years(self):
        selected = []
        picker = DateDropdown(self.app, "2024-01-31", lambda value: selected.append(value) or True)
        try:
            self.assertTrue(all(str(box.cget("state")) == "readonly" for box in picker.selectors))
            picker.month.set("02")
            picker.update_days()
            self.assertEqual(picker.day.get(), "29")
            picker.submit()
            self.assertEqual(selected, ["2024-02-29"])
        finally:
            if picker.winfo_exists():
                picker.destroy()
        serial = self.create_book()
        self.app.edit_cell(serial, 4)
        self.assertIsNone(self.app.sheet.editor)
        dialogs = [child for child in self.app.winfo_children() if isinstance(child, DateDropdown)]
        self.assertEqual(len(dialogs), 1)
        dialogs[0].destroy()

    def test_invalid_date_does_not_modify_saved_book(self):
        serial = self.create_book()
        self.assertTrue(self.app.update_cell(serial, "start_date", "2026-03-01"))
        with patch("app.messagebox.showerror"):
            self.assertFalse(self.app.update_cell(serial, "end_date", "2026-02-28"))
        self.assertEqual(self.catalogue.books[0]["end_date"], "")

    def test_draft_image_survives_row_completion(self):
        path = Path(self.temporary.name) / "cover.png"
        image = tk.PhotoImage(master=self.app, width=2, height=2)
        image.write(str(path), format="png")
        self.assertTrue(self.app.update_cell(self.key, "image", "", image_source=str(path)))
        self.create_book()
        self.assertTrue(self.catalogue.image_path(self.catalogue.books[0]).exists())

    def test_notes_search_export_and_delete(self):
        serial = self.create_book()
        self.app.update_cell(serial, "notes", "Line one\nLine two")
        self.app.query.set("missing")
        self.assertEqual(self.app.sheet.rows, [])
        self.app.query.set("line two")
        self.assertEqual(len(self.app.sheet.rows), 1)
        path = Path(self.temporary.name) / "books.csv"
        with patch("app.filedialog.asksaveasfilename", return_value=str(path)), patch("app.messagebox.showinfo"):
            self.app.export()
        self.assertIn("Line one\nLine two", path.read_text(encoding="utf-8-sig"))
        self.app.sheet.select(serial)
        with patch("app.messagebox.askyesno", return_value=True):
            self.app.delete_book()
        self.assertEqual(self.catalogue.books, [])


if __name__ == "__main__":
    unittest.main()
