# Tech Stack

| Area       | Choice                     | Notes                                                                                      |
| ---------- | -------------------------- | ------------------------------------------------------------------------------------------ |
| Language   | **Python 3.11 or 3.12**    |                                                                                            |
| GUI        | **Tkinter + ttkbootstrap** | Blue `cosmo` theme; `ttkbootstrap.Treeview`/`Tableview`, `ScrolledFrame` for the card grid |
| Images     | **Pillow**                 | Thumbnails; `ImageTk.PhotoImage` (keep references to avoid garbage collection)             |
| Charts     | **Matplotlib**             | Embedded with `FigureCanvasTkAgg`, `Agg` backend safe; style to match blue                 |
| ORM        | **SQLAlchemy 2.x**         | Declarative models, `Mapped[]` typing, `Session` via context manager                       |
| Database   | **MySQL 8** (local)        | Driver **PyMySQL**: `mysql+pymysql://user:pass@localhost:3306/pawpos?charset=utf8mb4`      |
| Passwords  | **bcrypt**                 | Hash on create/reset; verify on login                                                      |
| Receipts   | **ReportLab**              | 80 mm wide PDF (`80 * mm` width, height computed from line count)                          |
| Config     | **python-dotenv**          | Reads `.env`                                                                               |
| Tests      | **pytest**                 | In-memory SQLite for service tests                                                         |
| Lint/format | **Ruff**                  | Python 3.11 target, 88-character lines, standard checks and import sorting                   |
| Packaging  | none                       | Run `python main.py`                                                                       |
| Migrations | none                       | `create_all()` on startup                                                                  |

## requirements.txt

```
ttkbootstrap>=1.10
SQLAlchemy>=2.0
PyMySQL>=1.1
cryptography>=42      # required by PyMySQL for MySQL 8 default auth (caching_sha2_password)
Pillow>=10
matplotlib>=3.8
reportlab>=4.0
bcrypt>=4.1
python-dotenv>=1.0
pytest>=8.0
ruff>=0.14,<1
```

## Setup steps (document in the project README)

1. Install Python 3.11/3.12 and MySQL 8.
2. In MySQL: `CREATE DATABASE pawpos CHARACTER SET utf8mb4;` and create a user with privileges on it.
3. `python -m venv .venv` and activate it; `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in the DB values.
5. `python main.py` (tables and seed data are created on first run).
6. `pytest` to run the tests.
7. `python -m ruff check .` and `python -m ruff format --check .` to check code;
   `python -m ruff format .` to apply formatting.

## Coding standards

- Type hints on all service functions; short docstrings.
- Use `Decimal` for money and quantities; construct from `str`, never from `float`.
- `snake_case` names, one class per UI screen/dialog, small methods.
- No global mutable state except the current user in `core/session.py`.
- No raw SQL in UI code. Prefer SQLAlchemy 2.0 `select()` style in services.
- Use `logging`, not `print`.
- Keep Tk image references on the owning widget (`widget.image = photo`).

## Windows notes

- Printing: `os.startfile(pdf_path)` opens the default PDF viewer; the user prints from the system print dialog.
- Fallback for other OSs: `open` (macOS), `xdg-open` (Linux).
