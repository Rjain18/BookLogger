import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk


class DateDropdown(tk.Toplevel):
    def __init__(self, parent, value, apply):
        super().__init__(parent)
        self.withdraw()
        self.title("Choose date")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.apply = apply
        initial = date.fromisoformat(value) if value else date.today()
        self.year = tk.StringVar(value=str(initial.year))
        self.month = tk.StringVar(value=f"{initial.month:02d}")
        self.day = tk.StringVar(value=f"{initial.day:02d}")
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        self.selectors = []
        for column, (label, variable, values, width) in enumerate((
                ("Year", self.year, tuple(range(min(1900, initial.year), max(2100, initial.year) + 1)), 7),
                ("Month", self.month, tuple(f"{month:02d}" for month in range(1, 13)), 5),
                ("Day", self.day, (), 5))):
            ttk.Label(body, text=label).grid(row=0, column=column, sticky="w", padx=4)
            selector = ttk.Combobox(body, textvariable=variable, values=values,
                                    state="readonly", width=width)
            selector.grid(row=1, column=column, padx=4, pady=(4, 12))
            selector.bind("<<ComboboxSelected>>", lambda _: self.update_days())
            self.selectors.append(selector)
        self.update_days()
        actions = ttk.Frame(body)
        actions.grid(row=2, column=0, columnspan=3)
        ttk.Button(actions, text="Apply", command=self.submit).pack(side="left", padx=3)
        ttk.Button(actions, text="Clear date", command=lambda: self.submit("")).pack(side="left", padx=3)
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side="left", padx=3)
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Return>", lambda _: self.submit())
        self.deiconify()
        self.grab_set()
        self.selectors[0].focus_set()

    def update_days(self):
        count = calendar.monthrange(int(self.year.get()), int(self.month.get()))[1]
        self.selectors[2].configure(values=tuple(f"{day:02d}" for day in range(1, count + 1)))
        if int(self.day.get()) > count:
            self.day.set(f"{count:02d}")

    def submit(self, value=None):
        if value is None:
            value = date(int(self.year.get()), int(self.month.get()), int(self.day.get())).isoformat()
        if self.apply(value):
            self.destroy()


class BookSheet(ttk.Frame):
    columns = ("serial", "name", "image", "author", "start_date", "end_date", "notes")
    headings = ("Serial no.", "Book name", "Book image", "Author", "Start date ▾", "End date ▾", "Notes")
    widths = (80, 240, 120, 200, 140, 140, 320)
    row_height = 76
    header_height = 36

    def __init__(self, parent, edit, image_loader):
        super().__init__(parent)
        self.edit_callback = edit
        self.image_loader = image_loader
        self.rows = []
        self.active = None
        self.editor = None
        self.editor_cell = None
        self.on_commit = None
        self.photos = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.header = tk.Canvas(self, height=self.header_height, bg="#e4ebf3", highlightthickness=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0, takefocus=True)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.scroll_y)
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.scroll_x)
        horizontal.grid(row=2, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<Double-1>", self.double_click)
        self.canvas.bind("<Return>", self.edit_active)
        self.canvas.bind("<F2>", self.edit_active)
        self.canvas.bind("<Tab>", lambda _: self.move(0, 1))
        self.canvas.bind("<Shift-Tab>", lambda _: self.move(0, -1))
        for key, delta in (("Up", (-1, 0)), ("Down", (1, 0)), ("Left", (0, -1)), ("Right", (0, 1))):
            self.canvas.bind(f"<{key}>", lambda _, delta=delta: self.move(*delta))
        self.canvas.bind("<MouseWheel>", self.mousewheel)
        self.canvas.bind("<Button-4>", lambda _: self.scroll_y("scroll", -1, "units"))
        self.canvas.bind("<Button-5>", lambda _: self.scroll_y("scroll", 1, "units"))
        x = 0
        for title, width in zip(self.headings, self.widths):
            self.header.create_rectangle(x, 0, x + width, self.header_height, outline="#b9c7d6", fill="#e4ebf3")
            self.header.create_text(x + 10, 18, text=title, anchor="w", font=("Segoe UI", 10, "bold"), fill="#223247")
            x += width
        self.header.configure(scrollregion=(0, 0, x, self.header_height))

    def scroll_x(self, *args):
        if not self.finish_edit():
            return
        self.canvas.xview(*args)
        self.header.xview_moveto(self.canvas.xview()[0])

    def scroll_y(self, *args):
        if self.finish_edit():
            self.canvas.yview(*args)

    def mousewheel(self, event):
        self.scroll_y("scroll", -1 if event.delta > 0 else 1, "units")
        return "break"

    def set_rows(self, rows):
        self.rows = rows
        self.canvas.delete("all")
        self.photos.clear()
        if self.active and not any(key == self.active[0] for key, _ in rows):
            self.active = None
        for row_index, (key, book) in enumerate(rows):
            y = row_index * self.row_height
            x = 0
            for column, width in zip(self.columns, self.widths):
                fill = "#fff9e9" if str(key).startswith("draft") else ("white" if row_index % 2 == 0 else "#f7fafc")
                self.canvas.create_rectangle(x, y, x + width, y + self.row_height, outline="#d0d9e3", fill=fill)
                if column == "image":
                    photo = self.image_loader(key, book)
                    if photo:
                        self.photos.append(photo)
                        self.canvas.create_image(x + width // 2, y + self.row_height // 2, image=photo)
                    else:
                        self.canvas.create_text(x + 8, y + self.row_height // 2, anchor="w", text="Choose image…", fill="#52749b", font=("Segoe UI", 9))
                else:
                    text = str(book.get(column, ""))
                    limit = max(12, (width - 16) // 8) * 3
                    text = text.replace("\n", " ")
                    if len(text) > limit:
                        text = text[:limit - 1] + "…"
                    if column == "serial" and not text:
                        text = "New"
                    self.canvas.create_text(x + 8, y + self.row_height // 2, anchor="w", text=text,
                                            width=width - 16, font=("Segoe UI", 10), fill="#223247")
                x += width
        self.canvas.configure(scrollregion=(0, 0, sum(self.widths), max(1, len(rows) * self.row_height)))
        self.draw_selection()

    def cell_bounds(self, key, column):
        row = next((index for index, (row_key, _) in enumerate(self.rows) if key == row_key), None)
        if row is None:
            return None
        x = sum(self.widths[:column])
        return x, row * self.row_height, self.widths[column], self.row_height

    def select(self, key, column=1):
        self.active = (key, column)
        bounds = self.cell_bounds(key, column)
        if bounds:
            x, y, width, height = bounds
            top = self.canvas.canvasy(0)
            if y < top or y + height > top + self.canvas.winfo_height():
                self.canvas.yview_moveto(y / max(1, len(self.rows) * self.row_height))
            left = self.canvas.canvasx(0)
            if x < left or x + width > left + self.canvas.winfo_width():
                self.canvas.xview_moveto(x / sum(self.widths))
                self.header.xview_moveto(self.canvas.xview()[0])
        self.draw_selection()
        self.canvas.focus_set()

    def draw_selection(self):
        self.canvas.delete("selection")
        if self.active:
            bounds = self.cell_bounds(*self.active)
            if bounds:
                x, y, width, height = bounds
                self.canvas.create_rectangle(x + 1, y + 1, x + width - 1, y + height - 1,
                                             outline="#28734d", width=2, tags="selection")

    def locate(self, event):
        row = int(self.canvas.canvasy(event.y) // self.row_height)
        x = self.canvas.canvasx(event.x)
        if row < 0 or row >= len(self.rows) or x < 0:
            return None
        for column, width in enumerate(self.widths):
            if x < width:
                return self.rows[row][0], column
            x -= width
        return None

    def click(self, event):
        if not self.finish_edit():
            return "break"
        cell = self.locate(event)
        if cell:
            self.select(*cell)
            if self.columns[cell[1]] in ("start_date", "end_date"):
                self.edit_callback(*cell)

    def double_click(self, event):
        if not self.finish_edit():
            return "break"
        cell = self.locate(event)
        if cell:
            self.select(*cell)
            if self.columns[cell[1]] not in ("start_date", "end_date"):
                self.edit_callback(*cell)
        return "break"

    def edit_active(self, _=None):
        if self.active and self.finish_edit():
            self.edit_callback(*self.active)
        return "break"

    def move(self, row_delta, column_delta):
        if not self.rows or not self.finish_edit():
            return "break"
        if self.active:
            row = next((index for index, (key, _) in enumerate(self.rows) if key == self.active[0]), 0)
            column = self.active[1] + column_delta
        else:
            row, column = 0, 1
        if column >= len(self.columns):
            row, column = row + 1, 1
        elif column < 0:
            row, column = row - 1, len(self.columns) - 1
        row = max(0, min(len(self.rows) - 1, row + row_delta))
        self.select(self.rows[row][0], column)
        return "break"

    def begin_edit(self, key, column, value, commit):
        if not self.finish_edit():
            return
        bounds = self.cell_bounds(key, column)
        if not bounds:
            return
        x, y, width, height = bounds
        self.editor_cell = (key, column)
        self.on_commit = commit
        self.editor = tk.Text(self.canvas, font=("Segoe UI", 10), wrap="word", relief="solid", borderwidth=1)
        self.editor.insert("1.0", value)
        self.editor.place(x=x - self.canvas.canvasx(0) + 2, y=y - self.canvas.canvasy(0) + 2,
                          width=width - 4, height=height - 4)
        self.editor.tag_add("sel", "1.0", "end-1c")
        self.editor.focus_set()
        self.editor.bind("<Escape>", self.cancel_edit)
        self.editor.bind("<Control-Return>", self.commit_event)
        if self.columns[column] != "notes":
            self.editor.bind("<Return>", self.commit_event)
        self.editor.bind("<Tab>", lambda _: self.move(0, 1))
        self.editor.bind("<Shift-Tab>", lambda _: self.move(0, -1))

    def commit_event(self, _=None):
        if self.finish_edit():
            self.canvas.focus_set()
        return "break"

    def finish_edit(self):
        if self.editor is None:
            return True
        editor, callback = self.editor, self.on_commit
        value = editor.get("1.0", "end-1c")
        if not callback(value):
            editor.focus_set()
            return False
        self.editor = None
        self.editor_cell = None
        self.on_commit = None
        editor.destroy()
        return True

    def cancel_edit(self, _=None):
        if self.editor:
            self.editor.destroy()
        self.editor = None
        self.editor_cell = None
        self.on_commit = None
        self.canvas.focus_set()
        return "break"
