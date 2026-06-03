# 💸 Spent — Personal Expense Tracker

A fully local expense tracker. No cloud, no account, no telemetry. Add expenses, filter them, and see a monthly breakdown — all running on your machine.

---

## Quick Start

```bash
# 1. Clone or unzip the project, then enter the folder
cd Expense_Tracker

# 2. Install dependencies (only two packages)
pip install flask flask-cors
# or
pip install -r requirements.txt

# 3. Start the server
python app.py

# 4. Open in your browser
# http://localhost:5000
```

The SQLite database (`expenses.db`) is created automatically on first run. Nothing else to configure.

---

## Exact Commands — Copy-Paste Ready

### First time setup
```bash
cd Expense_Tracker
pip install flask flask-cors
python app.py
```

### Every subsequent run
```bash
cd Expense_Tracker
python app.py
```

### If pip install fails (externally managed Python env, e.g. Ubuntu 23+)
```bash
pip install flask flask-cors --break-system-packages
# or use a virtualenv:
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install flask flask-cors
python app.py
```

### Run on a different port
```bash
# Edit the last line of app.py:
# app.run(debug=True, port=8080)
python app.py
# then open http://localhost:8080
```

### Back up your data
```bash
cp expenses.db expenses_backup.db
```

---

## Project Structure

```
Expense_Tracker/
├── app.py              ← Flask backend + all API endpoints
├── requirements.txt    ← pip dependencies
├── expenses.db         ← SQLite database (auto-created, do not commit)
├── README.md
└── static/
    └── index.html      ← Entire frontend: HTML + CSS + JS, one file
```

---

## Stack Choices and Tradeoffs

### Python + Flask (backend)
**Chosen because:** lightweight, no boilerplate, easy to read and modify, runs anywhere Python runs. The whole backend is one file (~250 lines).

**Tradeoff:** Flask's built-in server is single-threaded and not production-grade. Fine for one person running locally; not suitable for serving multiple concurrent users.

**Alternatives considered:**
- FastAPI — would add async and automatic docs, but overkill for a personal tool with no concurrency needs
- Django — far too heavy for this scope

### SQLite (database)
**Chosen because:** zero setup, single file on disk, no server process, ships with Python's standard library. The entire database is `expenses.db` — you can copy it, email it, or delete it.

**Tradeoff:** Not suitable for concurrent writes from multiple users. For one person on one machine, this is never a problem.

**Alternatives considered:**
- PostgreSQL / MySQL — require a running server process; massive overkill
- JSON file — no querying, no transactions, breaks on concurrent writes

### Vanilla HTML/CSS/JS (frontend)
**Chosen because:** no build step, no Node.js, no npm, no bundler. Open the browser and it works. The entire UI is `static/index.html`.

**Tradeoff:** As the app grows, a single large HTML file becomes harder to maintain. For this scope it's fine.

**Why not Streamlit?**
Streamlit re-executes the entire Python script on every widget interaction. For a CRUD app with modals, live filtering, and inline editing, this creates visible lag and makes the UI feel sluggish. A REST API + plain HTML gives instant responses, real modal dialogs, and debounced search — with no extra complexity.

**Why not React/Vue?**
Would require Node.js, npm, a build step, and a bundler just to run locally. The added complexity is not justified for a personal tool with a single user.

---

## What's Built

| Feature | Details |
|---|---|
| Add expense | Title, amount, category, date (default today), optional note |
| View all expenses | Table sorted by date descending, shows all fields |
| Edit expense | Modal with pre-filled fields, same validation as add |
| Delete expense | Confirmation modal, cannot be undone |
| Monthly summary | Total spent, transaction count, avg per transaction, category breakdown with bar chart |
| Filters | By title (partial match), category, date range (from/to) |
| Sidebar total | Shows current month's spend at a glance |

---

## What's Skipped and Why

| Feature | Why skipped |
|---|---|
| User accounts / login | Single-user local tool; auth adds complexity with no benefit |
| Multiple currencies | Scope kept simple; currency symbol is a one-line config change |
| Export to CSV/Excel | Out of scope for v1; the SQLite file itself is portable |
| Charts / graphs over time | Summary view covers the main need; charting adds JS library dependencies |
| Recurring expenses | Significant added complexity; out of scope |
| Budget limits / alerts | Useful but out of scope for v1 |
| Soft delete / undo | Delete is permanent; a confirmation modal is the safety net |
| Full-text search on notes | Notes are visible in the list; title search covers the primary use case |
| Pagination UI | API supports pagination (page/per_page params); the UI loads up to 100 by default which covers most personal use |
| Dark/light mode toggle | Dark mode only; changing this is a CSS variable edit |

---

## Edge Cases Handled

| Scenario | What happens |
|---|---|
| Empty or whitespace-only title | Rejected with validation error |
| Zero or negative amount | Rejected with validation error |
| Amount over 1 billion | Rejected — likely a data entry mistake |
| Future date on an expense | Rejected — you can't have spent money tomorrow |
| Date before 1900 | Rejected |
| Missing required fields | Each field gets its own inline error message |
| Unknown category value | Rejected server-side even if sent via API directly |
| `from_date` after `to_date` in filter | Server silently swaps them — no error thrown |
| Invalid date format in filter | Filter param ignored, warning returned in response |
| Invalid category in filter | Filter param ignored, warning returned in response |
| Edit or delete a non-existent ID | 404 with a clear message |
| Malformed or missing JSON body | 400 with explanation |
| Note longer than 1000 chars | Rejected server-side |
| No expenses in the list | Empty state with guidance text, no blank table |
| No spending in selected month | Summary shows zeroes, breakdown shows empty state |
| Navigating to a future month in summary | Next button is disabled |
| Database file missing on startup | Auto-created with correct schema |

### Rough known edge cases (not handled)

- **Amount precision beyond 2 decimal places** — values like `10.999` are silently rounded to `11.00` on save. This is intentional but not surfaced to the user.
- **Very long titles** — capped at 120 chars server-side, but the input field allows typing beyond that before submission; the server will reject it but the frontend doesn't show a live counter.
- **Concurrent edits** — if you open the app in two tabs and edit the same expense simultaneously, last write wins with no conflict warning.
- **Timezone handling** — dates are stored as plain `YYYY-MM-DD` strings with no timezone. If your system clock is near midnight and crosses a date boundary, the "default today" might be off by one.
- **Large datasets** — the UI loads 100 expenses per page. If you have thousands of entries, older ones require using the API's `page` param directly; there's no pagination UI.
- **Browser back button** — the app is a single-page UI with no URL routing. The browser back button does nothing useful.

---

## API Reference

All endpoints accept and return JSON.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/expenses` | List expenses (filterable, paginated) |
| POST | `/api/expenses` | Create a new expense |
| GET | `/api/expenses/:id` | Get one expense |
| PUT | `/api/expenses/:id` | Update an expense |
| DELETE | `/api/expenses/:id` | Delete an expense |
| GET | `/api/summary/monthly` | Monthly total + category breakdown |
| GET | `/api/summary/recent_months` | Totals for past N months |
| GET | `/api/categories` | List valid categories |

### Filter params for `GET /api/expenses`
| Param | Type | Notes |
|-------|------|-------|
| `title` | string | Partial, case-insensitive |
| `category` | string | Exact match |
| `from_date` | YYYY-MM-DD | Start of range |
| `to_date` | YYYY-MM-DD | End of range |
| `page` | int | Default 1 |
| `per_page` | int | Default 100, max 500 |

---

## Customisation

**Change currency symbol** — one line in `static/index.html`:
```js
const CURRENCY = '₹';  // change to $, €, £, or anything
```

**Change port:**
```python
# bottom of app.py
app.run(debug=True, port=8080)
```

**Move the database:**
```python
# top of app.py
DB_PATH = '/your/custom/path/expenses.db'
```

---

## Notes

- `debug=True` is on by default — fine for local use, turn it off if you expose this to a network.
- All data stays on your machine. Nothing is sent anywhere.
- The `expenses.db` file is your entire dataset. Back it up like any important file.
