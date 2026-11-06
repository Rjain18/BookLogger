import base64
import binascii
import json
import os
import shutil
import tempfile
import uuid
from datetime import date, datetime
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
            if not isinstance(fields.get(key, ""), str):
                raise ValueError(f"{label} must be text.")
        rating = fields.get("rating", "")
        if rating not in ("", None):
            try:
                number = float(rating)
                if isinstance(rating, bool) or not 1 <= number <= 5 or number * 2 != int(number * 2):
                    raise ValueError()
            except (ValueError, TypeError, OverflowError):
                raise ValueError("Rating must be from 1 to 5 in steps of 0.5.") from None
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
        self.validate(fields)
        rating = fields.get("rating", "")
        fields = {key: fields.get(key, "").strip() for key in
                  ("name", "author", "start_date", "end_date", "notes", "image")}
        fields["rating"] = rating
        self.validate(fields)
        fields["rating"] = float(rating) if rating not in ("", None) else ""
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

    def export_json(self, path):
        path = Path(path)
        if path.resolve() == self.path.resolve():
            raise ValueError("Choose a backup location other than the live books.json file.")
        books = []
        for existing in self.books:
            book = existing.copy()
            image = self.image_path(book)
            if image:
                book["image_data"] = base64.b64encode(image.read_bytes()).decode("ascii")
                book["image_extension"] = image.suffix.lower()
            for key in ("start_date", "end_date"):
                if book.get(key):
                    book[key] = date.fromisoformat(book[key]).strftime("%d-%m-%Y")
            book["image"] = ""
            books.append(book)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                json.dump({"format": "BookLogger", "version": 1, "books": books}, handle,
                          ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def import_json(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        entries = data.get("books") if isinstance(data, dict) else data
        if not isinstance(entries, list):
            raise ValueError("JSON must contain a books list.")
        if isinstance(data, dict) and "version" in data and data["version"] != 1:
            raise ValueError("Unsupported JSON backup version.")
        prepared = []
        for index, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                raise ValueError(f"Book {index} must be an object.")
            book = {}
            for key in ("name", "author", "start_date", "end_date", "notes", "image"):
                value = entry.get(key, "")
                if not isinstance(value, str):
                    raise ValueError(f"Book {index}: {key} must be text.")
                book[key] = value.strip()
            for key in ("start_date", "end_date"):
                value = book[key]
                if value and len(value) == 10 and value[2] == "-" and value[5] == "-":
                    try:
                        book[key] = datetime.strptime(value, "%d-%m-%Y").date().isoformat()
                    except ValueError:
                        raise ValueError(f"Book {index}: invalid date.") from None
            book["rating"] = entry.get("rating", "")
            self.validate(book)
            book["rating"] = float(book["rating"]) if book["rating"] not in ("", None) else ""
            payload = None
            extension = entry.get("image_extension", "")
            if "image_data" in entry:
                if not isinstance(entry["image_data"], str) or extension not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
                    raise ValueError(f"Book {index}: invalid embedded image.")
                try:
                    payload = base64.b64decode(entry["image_data"], validate=True)
                except (ValueError, binascii.Error):
                    raise ValueError(f"Book {index}: invalid image encoding.") from None
                if not payload:
                    raise ValueError(f"Book {index}: empty image.")
            elif book["image"]:
                raise ValueError("Import covers using an Export JSON backup with embedded images, not external file paths.")
            book["image"] = ""
            prepared.append((book, payload, extension))
        created = []
        books = [book.copy() for book in self.books]
        try:
            for book, payload, extension in prepared:
                if payload is not None:
                    images = self.directory / "images"
                    images.mkdir(parents=True, exist_ok=True)
                    destination = images / (uuid.uuid4().hex + extension)
                    created.append(destination)
                    destination.write_bytes(payload)
                    book["image"] = str(destination.relative_to(self.directory))
                book["serial"] = self.next_serial + len(books) - len(self.books)
                books.append(book)
            if prepared:
                self._write(books, self.next_serial + len(prepared))
        except OSError:
            for destination in created:
                destination.unlink(missing_ok=True)
            raise
        return len(prepared)

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
