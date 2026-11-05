# BookLogger

A Python desktop book catalogue built with **Qt (PySide6)**. Track your reading in an editable, spreadsheet-style interface with light and dark themes.

## Features

- Book entries with automatic serial numbers, book name, cover image, author, start date, end date, and notes.
- Edit cells directly and add books using **+ New book** or the **+ Add a new book** row.
- Selection-only calendar with month/year dropdowns; dates display and export as **DD-MM-YYYY**.
- Light/dark mode toggle in the top-right corner, including themed date controls.
- Search by serial number, book name, author, or notes.
- Cover thumbnails, cover replacement/removal, and confirmed row deletion.
- CSV export of the entire saved catalogue.
- Local JSON storage with atomic saves; no database server or online account required.

## Requirements

- Python 3.10 or later, compatible with the PySide6 version installed.
- A graphical desktop session on Windows or Linux.
- Dependencies listed in `requirements.txt`.

The current version has been tested on Windows with Python 3.14.2. Linux uses the same Qt interface but has not been tested yet. Tkinter and Pillow are not required by the current app.

## Setup and launch

Run these commands from the project folder.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If `.venv` already exists, skip the creation command and update its dependencies with the installation command.

### Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

On Debian/Ubuntu, install `python3-venv` if environment creation reports that it is missing. Qt may also require distribution-specific desktop/XCB libraries. Recreate the virtual environment on each operating system; do not copy a Windows `.venv` to Linux.

## Using the catalogue

1. Click **+ New book**, or click the highlighted **+ Add a new book** row.
2. Enter the book name and author. The row is saved and assigned a serial number once both are provided.
3. Double-click a text cell to edit it. Press **Enter**, **Tab**, or **Save cell** to confirm changes.
4. Click a date cell, select a day from the calendar, and click **Apply date**. Use **Clear date** to remove it. Dates cannot be typed.
5. Double-click a cover cell to select an image, or use **Remove cover** for the selected book.
6. Use the corner theme button to switch appearance without discarding the active cell edit. The app starts in light mode; the theme choice is not persisted.

Notes support multiple lines: **Enter** inserts a line break and **Ctrl+Enter** saves. **Esc** cancels an active edit. **Ctrl+S** saves the active cell and **Ctrl+N** adds a new book row. Arrow keys navigate the table; **F2** or **Enter** opens the selected cell for editing.

Start/end dates are optional. An end date requires a start date and cannot be earlier than it. Serial numbers are read-only and are not reused after deletion.

Incomplete rows remain unsaved until they contain both a book name and author. Closing the app asks before discarding them; export asks before excluding them. Export includes all saved books, not just search results, and writes cover paths rather than embedding images.

## Storage and backups

Data is stored outside the repository:

- **Windows:** `%LOCALAPPDATA%\BookLogger`
- **Linux:** `~/BookLogger` (when `LOCALAPPDATA` is unset)

`books.json` contains the catalogue, and `images/` contains copied cover files. Dates remain in ISO `YYYY-MM-DD` format internally for compatibility with previous versions; the interface and CSV use `DD-MM-YYYY`.

Back up the entire data directory, including `books.json` and `images/`. Existing catalogues are loaded automatically. Local data, virtual environments, and Python caches are excluded by `.gitignore`.

## Tests

### Windows

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

### Linux

```bash
.venv/bin/python -m unittest -v
```

The 19 tests cover persistence, validation, cell editing, keyboard shortcuts, new rows, images, search, export, dates, and theme/calendar contrast. Qt interface tests use the offscreen platform and do not require opening application windows.

## Project files

- `app.py`: Qt application, themes, catalogue actions, and CSV export.
- `qt_sheet.py`: spreadsheet widget and selection-only calendar dialog.
- `catalogue.py`: JSON persistence, serial numbers, image copying, and validation.
- `test_catalogue.py`, `test_sheet.py`: automated regression tests.
- `sheet.py`: legacy Tkinter spreadsheet implementation; not used by the Qt app.
