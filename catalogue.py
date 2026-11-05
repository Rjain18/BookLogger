import json
import os
import shutil
import tempfile
import uuid
from datetime import date
from pathlib import Path


class Catalogue:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "books.json"
        self.books = []
        self.next_serial = 1
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.books = data["books"]
            self.next_serial = data["next_serial"]
            if not isinstance(self.books, list) or not isinstance(self.next_serial, int):
                raise ValueError("Invalid catalogue file")
            for book in self.books:
                self.validate(book)
                if not isinstance(book.get("serial"), int):
                    raise ValueError("Invalid book serial number")
            serials = [book["serial"] for book in self.books]
            if len(set(serials)) != len(serials) or self.next_serial <= max(serials, default=0):
                raise ValueError("Invalid catalogue serial numbers")

    @staticmethod
    def validate(fields):
        for key, label in (("name", "Book name"), ("author", "Author")):
            if not isinstance(fields.get(key), str) or not fields[key].strip():
                raise ValueError(f"{label} is required.")
        dates = {}
        for key, label in (("start_date", "Start date"), ("end_date", "End date")):
            value = fields.get(key, "")
            if value:
                try:
                    parsed = date.fromisoformat(value)
                    if parsed.isoformat() != value:
                        raise ValueError()
                    dates[key] = parsed
                except (ValueError, TypeError):
                    raise ValueError(f"{label} must be YYYY-MM-DD.") from None
        if "end_date" in dates and "start_date" not in dates:
            raise ValueError("Enter a start date before an end date.")
        if len(dates) == 2 and dates["end_date"] < dates["start_date"]:
            raise ValueError("End date cannot be earlier than start date.")

    def _write(self, books, next_serial):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                             suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                json.dump({"next_serial": next_serial, "books": books}, handle,
                          ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        self.books = books
        self.next_serial = next_serial

    def save(self, fields, serial=None, image_source=None):
        fields = {key: fields.get(key, "").strip() for key in
                  ("name", "author", "start_date", "end_date", "notes", "image")}
        self.validate(fields)
        if serial is not None and not any(book["serial"] == serial for book in self.books):
            raise ValueError("Book no longer exists.")
        if image_source:
            source = Path(image_source)
            images = self.directory / "images"
            images.mkdir(parents=True, exist_ok=True)
            destination = images / (uuid.uuid4().hex + source.suffix.lower())
            shutil.copyfile(source, destination)
            fields["image"] = str(destination.relative_to(self.directory))
        assigned = self.next_serial if serial is None else serial
        book = dict(fields, serial=assigned)
        books = [book if existing["serial"] == assigned else existing for existing in self.books]
        if serial is None:
            books.append(book)
        self._write(books, self.next_serial + (serial is None))
        return book

    def delete(self, serial):
        if not any(book["serial"] == serial for book in self.books):
            raise ValueError("Book no longer exists.")
        self._write([book for book in self.books if book["serial"] != serial], self.next_serial)

    def search(self, query=""):
        query = query.strip().casefold()
        return [book.copy() for book in self.books if not query or any(
            query in str(book.get(key, "")).casefold()
            for key in ("serial", "name", "author", "notes"))]

    def image_path(self, book):
        value = book.get("image", "")
        return self.directory / value if value else None
