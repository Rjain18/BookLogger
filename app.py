import csv
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from catalogue import Catalogue
from sheet import BookSheet, DateDropdown

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = ImageOps = ImageTk = None


class BookLogger(tk.Tk):
    def __init__(self, catalogue):
        super().__init__()
        self.catalogue = catalogue
        self.drafts = {}
        self.draft_images = {}
        self.draft_counter = 0
        self.photo_cache = {}
        self.title("BookLogger • Your reading catalogue")
        self.geometry("1280x760")
        self.minsize(850, 500)
        self.configure(bg="#eef2f6")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#eef2f6")
        style.configure("TLabel", background="#eef2f6", foreground="#223247", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="BookLogger", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Double-click a cell to edit • Click dates for dropdowns • Tab to move • Ctrl+Enter saves notes").pack(anchor="w", pady=(0, 18))
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 14))
        ttk.Label(toolbar, text="Search").pack(side="left", padx=(0, 8))
        self.query = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.query, width=25).pack(side="left")
        for title, command in (("Export CSV", self.export), ("Delete row", self.delete_book),
                               ("Remove image", self.remove_image), ("Save cell", self.save_book),
                               ("+ New book row", self.new_book)):
            ttk.Button(toolbar, text=title, command=command).pack(side="right", padx=3)
        self.sheet = BookSheet(outer, self.edit_cell, self.load_image)
        self.sheet.pack(fill="both", expand=True)
        self.status = tk.StringVar()
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(14, 0))
        self.query.trace_add("write", self.search_changed)
        self.bind("<Control-s>", lambda _: self.save_book())
        self.bind("<Control-n>", lambda _: self.new_book())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        if not catalogue.books:
            self.new_book()

    def refresh(self):
        books = self.catalogue.search(self.query.get())
        self.sheet.set_rows([(book["serial"], book) for book in books] + list(self.drafts.items()))
        self.status.set(f"{len(books)} / {len(self.catalogue.books)} saved books • {len(self.drafts)} unsaved rows (enter book name and author) • {self.catalogue.directory}")

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
            DateDropdown(self, book.get(field, ""), lambda value: self.update_cell(key, field, value))
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
        try:
            if draft and not (book["name"] and book["author"]):
                Catalogue.validate(dict(book, name=book["name"] or "Draft", author=book["author"] or "Draft"))
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
                        self.sheet.active = (saved["serial"], self.sheet.active[1])
                self.photo_cache.clear()
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot save cell", str(error), parent=self)
            return False
        self.refresh()
        return True

    def load_image(self, key, book):
        path = self.draft_images.get(key) or self.catalogue.image_path(book)
        if not path:
            return None
        cache_key = str(path)
        if cache_key in self.photo_cache:
            return self.photo_cache[cache_key]
        try:
            if Image is not None:
                with Image.open(path) as image:
                    image = ImageOps.exif_transpose(image)
                    image.thumbnail((100, 64))
                    photo = ImageTk.PhotoImage(image.copy())
            else:
                image = tk.PhotoImage(file=str(path))
                ratio = max(1, (image.width() + 99) // 100, (image.height() + 63) // 64)
                photo = image.subsample(ratio, ratio)
            self.photo_cache[cache_key] = photo
            return photo
        except (OSError, ValueError, tk.TclError):
            return None

    def choose_image(self, key):
        path = filedialog.askopenfilename(title="Choose book cover", filetypes=[
            ("Book images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")])
        if path:
            probe = f"probe-{key}"
            self.draft_images[probe] = path
            valid = self.load_image(probe, {})
            self.draft_images.pop(probe, None)
            if valid:
                self.update_cell(key, "image", "", image_source=path)
            else:
                messagebox.showerror("Cannot open image", "Choose a valid image. JPEG, BMP and WebP require Pillow.", parent=self)

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
        if not messagebox.askyesno("Delete row", "Permanently delete this book row?", parent=self):
            return
        try:
            if key in self.drafts:
                del self.drafts[key]
                self.draft_images.pop(key, None)
            else:
                self.catalogue.delete(key)
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot delete book", str(error), parent=self)
            return
        self.photo_cache.clear()
        self.refresh()

    def close(self):
        if not self.sheet.finish_edit():
            return
        if self.drafts and not messagebox.askyesno("Unsaved rows", "Incomplete rows are not saved. Close and discard them?", parent=self):
            return
        self.destroy()

    def export(self):
        if not self.sheet.finish_edit():
            return
        if self.drafts and not messagebox.askyesno("Unsaved rows", "Export saved books only? Incomplete rows will not be included.", parent=self):
            return
        path = filedialog.asksaveasfilename(title="Export entire catalogue", defaultextension=".csv",
                                          initialfile="books.csv", filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        keys = ("serial", "name", "image", "author", "start_date", "end_date", "notes")
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("Serial number", "Book name", "Book image", "Author", "Start date", "End date", "Notes"))
                for book in self.catalogue.books:
                    values = [str(book.get(key, "")) for key in keys]
                    writer.writerow(["'" + value if value.startswith(("=", "+", "-", "@")) else value for value in values])
        except OSError as error:
            messagebox.showerror("Cannot export", str(error))
            return
        messagebox.showinfo("Export complete", f"Exported {len(self.catalogue.books)} books.")


def main():
    directory = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "BookLogger"
    try:
        catalogue = Catalogue(directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Cannot load catalogue", f"Your saved file could not be read and has not been changed.\n\n{error}\n\nLocation: {directory}")
        root.destroy()
        return
    BookLogger(catalogue).mainloop()


if __name__ == "__main__":
    main()
