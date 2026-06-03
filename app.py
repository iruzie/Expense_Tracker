"""
Expense Tracker - Python/Flask Backend
SQLite database, REST API for the frontend
"""

import sqlite3
import os
import re
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")

CATEGORIES = ["food", "transport", "shopping", "bills", "entertainment", "other"]


# ─── Database ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                title     TEXT    NOT NULL CHECK(length(trim(title)) > 0),
                amount    REAL    NOT NULL CHECK(amount > 0),
                category  TEXT    NOT NULL,
                date      TEXT    NOT NULL,
                note      TEXT    DEFAULT '',
                created_at TEXT   DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


# ─── Validation ──────────────────────────────────────────────────────────────

def validate_expense(data, require_all=True):
    errors = []

    title = data.get("title", "").strip() if require_all else data.get("title", None)
    if require_all and (title is None or len(title) == 0):
        errors.append("Title is required and cannot be empty.")
    elif title is not None and len(title) > 120:
        errors.append("Title must be 120 characters or fewer.")

    amount = data.get("amount", None)
    if require_all and amount is None:
        errors.append("Amount is required.")
    elif amount is not None:
        try:
            amount = float(amount)
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
            if amount > 1_000_000_000:
                errors.append("Amount is unrealistically large (max 1,000,000,000).")
        except (ValueError, TypeError):
            errors.append("Amount must be a valid number.")

    category = data.get("category", None)
    if require_all and category is None:
        errors.append("Category is required.")
    elif category is not None and category not in CATEGORIES:
        errors.append(f"Category must be one of: {', '.join(CATEGORIES)}.")

    exp_date = data.get("date", None)
    if require_all and exp_date is None:
        errors.append("Date is required.")
    elif exp_date is not None:
        try:
            parsed = datetime.strptime(exp_date, "%Y-%m-%d").date()
            if parsed.year < 1900:
                errors.append("Date must be after 1900.")
            if parsed > date.today():
                errors.append("Date cannot be in the future.")
        except ValueError:
            errors.append("Date must be in YYYY-MM-DD format.")

    note = data.get("note", "")
    if note and len(note) > 1000:
        errors.append("Note must be 1000 characters or fewer.")

    return errors


def row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "amount": round(row["amount"], 2),
        "category": row["category"],
        "date": row["date"],
        "note": row["note"] or "",
        "created_at": row["created_at"],
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/categories", methods=["GET"])
def get_categories():
    return jsonify(CATEGORIES)


@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    """
    Query params:
      category   – exact match (one of the CATEGORIES)
      from_date  – YYYY-MM-DD
      to_date    – YYYY-MM-DD
      title      – partial text match (case-insensitive)
      page       – 1-indexed (default 1)
      per_page   – default 100, max 500
    """
    category  = request.args.get("category", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date   = request.args.get("to_date", "").strip()
    title_q   = request.args.get("title", "").strip()

    # Validate filter params gracefully
    filter_errors = []

    if from_date:
        try:
            datetime.strptime(from_date, "%Y-%m-%d")
        except ValueError:
            filter_errors.append("from_date must be YYYY-MM-DD")
            from_date = ""

    if to_date:
        try:
            datetime.strptime(to_date, "%Y-%m-%d")
        except ValueError:
            filter_errors.append("to_date must be YYYY-MM-DD")
            to_date = ""

    if from_date and to_date and from_date > to_date:
        # Swap silently so users don't have to worry about order
        from_date, to_date = to_date, from_date

    if category and category not in CATEGORIES:
        filter_errors.append(f"Invalid category '{category}' – ignored.")
        category = ""

    query = "SELECT * FROM expenses WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if from_date:
        query += " AND date >= ?"
        params.append(from_date)

    if to_date:
        query += " AND date <= ?"
        params.append(to_date)

    if title_q:
        query += " AND lower(title) LIKE ?"
        params.append(f"%{title_q.lower()}%")

    query += " ORDER BY date DESC, created_at DESC"

    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(500, max(1, int(request.args.get("per_page", 100))))
    except ValueError:
        page, per_page = 1, 100

    count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)

    with get_db() as conn:
        total = conn.execute(count_query, params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute(query + f" LIMIT {per_page} OFFSET {offset}", params).fetchall()

    return jsonify({
        "expenses": [row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "warnings": filter_errors,
    })


@app.route("/api/expenses", methods=["POST"])
def create_expense():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    # Default date to today if missing
    if not data.get("date"):
        data["date"] = date.today().isoformat()

    errors = validate_expense(data, require_all=True)
    if errors:
        return jsonify({"errors": errors}), 422

    title    = data["title"].strip()
    amount   = round(float(data["amount"]), 2)
    category = data["category"]
    exp_date = data["date"]
    note     = (data.get("note") or "").strip()

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO expenses (title, amount, category, date, note) VALUES (?,?,?,?,?)",
            (title, amount, category, exp_date, note),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (cursor.lastrowid,)).fetchone()

    return jsonify(row_to_dict(row)), 201


@app.route("/api/expenses/<int:expense_id>", methods=["GET"])
def get_expense(expense_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
    if not row:
        return jsonify({"error": "Expense not found."}), 404
    return jsonify(row_to_dict(row))


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def update_expense(expense_id):
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
    if not existing:
        return jsonify({"error": "Expense not found."}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    # Merge with existing values – only validate fields that are provided
    merged = {
        "title":    data.get("title",    existing["title"]),
        "amount":   data.get("amount",   existing["amount"]),
        "category": data.get("category", existing["category"]),
        "date":     data.get("date",     existing["date"]),
        "note":     data.get("note",     existing["note"] or ""),
    }

    errors = validate_expense(merged, require_all=True)
    if errors:
        return jsonify({"errors": errors}), 422

    with get_db() as conn:
        conn.execute(
            """UPDATE expenses SET title=?, amount=?, category=?, date=?, note=?
               WHERE id=?""",
            (
                merged["title"].strip(),
                round(float(merged["amount"]), 2),
                merged["category"],
                merged["date"],
                (merged["note"] or "").strip(),
                expense_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()

    return jsonify(row_to_dict(row))


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone()
        if not row:
            return jsonify({"error": "Expense not found."}), 404
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        conn.commit()
    return jsonify({"message": "Deleted successfully.", "id": expense_id})


@app.route("/api/summary/monthly", methods=["GET"])
def monthly_summary():
    """
    Returns summary for a given month.
    Query params: year (int), month (1-12). Defaults to current month.
    """
    today = date.today()
    try:
        year  = int(request.args.get("year",  today.year))
        month = int(request.args.get("month", today.month))
    except ValueError:
        return jsonify({"error": "year and month must be integers."}), 400

    if not (1 <= month <= 12):
        return jsonify({"error": "month must be between 1 and 12."}), 400
    if year < 1900 or year > today.year + 1:
        return jsonify({"error": f"year must be between 1900 and {today.year + 1}."}), 400

    period = f"{year:04d}-{month:02d}"

    with get_db() as conn:
        rows = conn.execute(
            "SELECT category, amount FROM expenses WHERE strftime('%Y-%m', date) = ?",
            (period,),
        ).fetchall()

    total = 0.0
    breakdown = {cat: 0.0 for cat in CATEGORIES}

    for row in rows:
        total += row["amount"]
        breakdown[row["category"]] = round(breakdown[row["category"]] + row["amount"], 2)

    # Remove zero categories from breakdown for cleanliness, but keep in response
    return jsonify({
        "year":      year,
        "month":     month,
        "period":    period,
        "total":     round(total, 2),
        "breakdown": breakdown,
        "count":     len(rows),
    })


@app.route("/api/summary/recent_months", methods=["GET"])
def recent_months_summary():
    """Returns monthly totals for the past N months (default 6)."""
    try:
        n = min(24, max(1, int(request.args.get("n", 6))))
    except ValueError:
        n = 6

    with get_db() as conn:
        rows = conn.execute("""
            SELECT strftime('%Y-%m', date) as period, SUM(amount) as total, COUNT(*) as count
            FROM expenses
            GROUP BY period
            ORDER BY period DESC
            LIMIT ?
        """, (n,)).fetchall()

    return jsonify([{"period": r["period"], "total": round(r["total"], 2), "count": r["count"]} for r in rows])


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("\n✅  Expense Tracker running at http://localhost:5000\n")
    app.run(debug=True, port=5000)