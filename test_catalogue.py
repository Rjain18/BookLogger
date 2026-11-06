import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from catalogue import Catalogue


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.catalogue = Catalogue(self.directory)
        self.fields = dict(name="A Book", author="An Author", start_date="2026-01-01",
                           end_date="2026-01-05", notes="Thoughts", image="")

    def test_persistence_edit_and_search(self):
        book = self.catalogue.save(self.fields)
        self.assertEqual(book["serial"], 1)
        changed = dict(self.fields, name="Revised Book")
        self.catalogue.save(changed, book["serial"])
        restored = Catalogue(self.directory)
        self.assertEqual(restored.search("revised")[0]["name"], "Revised Book")
        self.assertEqual(len(restored.search("AUTHOR")), 1)
        self.assertEqual(len(restored.search("thoughts")), 1)
        self.assertEqual(restored.search("missing"), [])
        self.assertEqual(restored.next_serial, 2)

    def test_delete_does_not_reuse_serial(self):
        book = self.catalogue.save(self.fields)
        self.catalogue.delete(book["serial"])
        self.assertEqual(Catalogue(self.directory).books, [])
        self.assertEqual(self.catalogue.save(self.fields)["serial"], 2)

    def test_invalid_fields(self):
        for fields in (dict(self.fields, name=" "), dict(self.fields, author=""),
                       dict(self.fields, start_date="2026-02-30"),
                       dict(self.fields, start_date="20260101"),
                       dict(self.fields, end_date="2025-12-31"),
                       dict(self.fields, start_date="")):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.catalogue.save(fields)
        self.assertEqual(self.catalogue.books, [])

    def test_optional_dates(self):
        self.catalogue.save(dict(self.fields, start_date="", end_date=""))
        self.assertEqual(len(self.catalogue.books), 1)

    def test_cover_is_copied(self):
        source = self.directory / "source.png"
        source.write_bytes(b"test cover bytes")
        book = self.catalogue.save(self.fields, image_source=source)
        source.unlink()
        self.assertEqual(self.catalogue.image_path(book).read_bytes(), b"test cover bytes")

    def test_failed_write_preserves_catalogue(self):
        self.catalogue.save(self.fields)
        before = self.catalogue.path.read_bytes()
        with patch("catalogue.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.catalogue.save(dict(self.fields, name="Another"))
        self.assertEqual(self.catalogue.path.read_bytes(), before)
        self.assertEqual(len(self.catalogue.books), 1)
        self.assertEqual(self.catalogue.next_serial, 2)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_json_round_trip_appends_and_embeds_cover(self):
        import json
        source = self.directory / "cover.jpeg"
        source.write_bytes(b"cover contents")
        self.catalogue.save(self.fields, image_source=source)
        backup = self.directory / "backup.json"
        self.catalogue.export_json(backup)
        data = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual(data["books"][0]["start_date"], "01-01-2026")
        self.assertIn("image_data", data["books"][0])
        self.assertEqual(self.catalogue.import_json(backup), 1)
        self.assertEqual([book["serial"] for book in self.catalogue.books], [1, 2])
        self.assertEqual(self.catalogue.books[1]["start_date"], "2026-01-01")
        self.assertEqual(self.catalogue.image_path(self.catalogue.books[1]).read_bytes(), b"cover contents")

    def test_json_invalid_batch_and_failed_write_are_atomic(self):
        import json
        backup = self.directory / "backup.json"
        self.catalogue.save(self.fields)
        before = self.catalogue.path.read_bytes()
        for entry in (dict(self.fields, name=""), dict(self.fields, notes=123),
                      dict(self.fields, image="../../secret.jpg"),
                      dict(self.fields, image_data="!!!", image_extension=".jpg")):
            backup.write_text(json.dumps({"books": [self.fields, entry]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.catalogue.import_json(backup)
            self.assertEqual(self.catalogue.path.read_bytes(), before)
        backup.write_text(json.dumps({"books": [dict(self.fields, image_data="aW1hZ2U=", image_extension=".jpg")]}), encoding="utf-8")
        with patch("catalogue.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.catalogue.import_json(backup)
        self.assertEqual(self.catalogue.path.read_bytes(), before)
        self.assertEqual(list((self.directory / "images").iterdir()), [])
        self.assertEqual(self.catalogue.next_serial, 2)

    def test_json_export_rejects_live_catalogue_path(self):
        self.catalogue.save(self.fields)
        before = self.catalogue.path.read_bytes()
        with self.assertRaises(ValueError):
            self.catalogue.export_json(self.catalogue.path)
        self.assertEqual(self.catalogue.path.read_bytes(), before)

    def test_corrupt_file_is_not_overwritten(self):
        self.catalogue.path.write_text("invalid json", encoding="utf-8")
        with self.assertRaises(ValueError):
            Catalogue(self.directory)
        self.assertEqual(self.catalogue.path.read_text(encoding="utf-8"), "invalid json")


if __name__ == "__main__":
    unittest.main()
