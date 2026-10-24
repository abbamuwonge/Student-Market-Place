"""
Database check: compares the REAL database with the ERD and data dictionary in the design document.

Use it before the demo ("show the ERD next to the real database tables") and after every change to models.py.

    python check_database.py            check the database the API uses (campusmart.db)
    python check_database.py --show     also print every real table, column by column
    python check_database.py --url sqlite:///other.db

Exit code 0 = everything matches, 1 = something does not match, 2 = the database could not be opened.
Start the API once first so that it creates the database and the tables.
"""
import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# --------------------------------------------------------------------------------------
# The ERD, written as data. This mirrors section 6 and 7 of the design document.
#   columns: name -> (type, nullable)     pk: primary key columns in order
#   fks: (columns, parent table, parent columns)     unique: sets of columns that must be unique
# --------------------------------------------------------------------------------------
SPEC = {
    "users": {
        "columns": {
            "user_id": ("INTEGER", False),
            "full_name": ("VARCHAR(100)", False),
            "email": ("VARCHAR(150)", False),
            "password_hash": ("VARCHAR(255)", False),
            "phone": ("VARCHAR(15)", False),
            "campus": ("VARCHAR(80)", False),
            "role": ("VARCHAR(10)", False),
            "created_at": ("DATETIME", False),
        },
        "pk": ["user_id"],
        "fks": [],
        "unique": [["email"]],
    },
    "categories": {
        "columns": {
            "category_id": ("INTEGER", False),
            "name": ("VARCHAR(60)", False),
            "icon": ("VARCHAR(10)", True),
        },
        "pk": ["category_id"],
        "fks": [],
        "unique": [["name"]],
    },
    "items": {
        "columns": {
            "item_id": ("INTEGER", False),
            "seller_id": ("INTEGER", False),
            "category_id": ("INTEGER", False),
            "title": ("VARCHAR(80)", False),
            "description": ("VARCHAR(500)", False),
            "price": ("DECIMAL(12,0)", False),
            "item_condition": ("VARCHAR(20)", False),
            "pickup_location": ("VARCHAR(100)", True),
            "image_url": ("VARCHAR(255)", True),
            "status": ("VARCHAR(10)", False),
            "created_at": ("DATETIME", False),
            "updated_at": ("DATETIME", True),
        },
        "pk": ["item_id"],
        "fks": [
            (["seller_id"], "users", ["user_id"]),
            (["category_id"], "categories", ["category_id"]),
        ],
        "unique": [],
    },
    "orders": {
        "columns": {
            "order_id": ("INTEGER", False),
            "buyer_id": ("INTEGER", False),
            "item_id": ("INTEGER", False),
            "price_at_order": ("DECIMAL(12,0)", False),
            "note": ("VARCHAR(200)", True),
            "status": ("VARCHAR(12)", False),
            "created_at": ("DATETIME", False),
        },
        "pk": ["order_id"],
        "fks": [
            (["buyer_id"], "users", ["user_id"]),
            (["item_id"], "items", ["item_id"]),
        ],
        "unique": [],
    },
    "favorites": {
        "columns": {
            "user_id": ("INTEGER", False),
            "item_id": ("INTEGER", False),
            "saved_at": ("DATETIME", False),
        },
        "pk": ["user_id", "item_id"],
        "fks": [
            (["user_id"], "users", ["user_id"]),
            (["item_id"], "items", ["item_id"]),
        ],
        "unique": [],
    },
    "messages": {
        "columns": {
            "message_id": ("INTEGER", False),
            "sender_id": ("INTEGER", False),
            "receiver_id": ("INTEGER", False),
            "item_id": ("INTEGER", True),
            "body": ("VARCHAR(1000)", False),
            "sent_at": ("DATETIME", False),
            "is_read": ("BOOLEAN", False),
        },
        "pk": ["message_id"],
        "fks": [
            (["sender_id"], "users", ["user_id"]),
            (["receiver_id"], "users", ["user_id"]),
            (["item_id"], "items", ["item_id"]),
        ],
        "unique": [],
    },
}

IGNORED_TABLES = {"alembic_version", "sqlite_sequence"}


class Report:
    def __init__(self):
        self.rows = []  # (level, message) with level OK, FAIL, WARN or INFO

    def add(self, level, message):
        self.rows.append((level, message))

    @property
    def failures(self):
        return [m for level, m in self.rows if level == "FAIL"]

    @property
    def warnings(self):
        return [m for level, m in self.rows if level == "WARN"]


def normalise_type(sql_type) -> str:
    """Make INT/INTEGER, NUMERIC/DECIMAL and TIMESTAMP/DATETIME comparable."""
    value = str(sql_type).upper().replace(" ", "")
    match = re.match(r"^([A-Z]+)(\(.*\))?", value)
    if not match:
        return value
    base, args = match.group(1), match.group(2) or ""
    base = {"INT": "INTEGER", "NUMERIC": "DECIMAL", "TIMESTAMP": "DATETIME"}.get(base, base)
    return base + args


def _scalar(conn, sql: str) -> int:
    return int(conn.execute(text(sql)).scalar() or 0)


def check_structure(inspector, report: Report) -> None:
    existing = {t for t in inspector.get_table_names() if t not in IGNORED_TABLES}

    for table in SPEC:
        if table not in existing:
            report.add("FAIL", f"Table '{table}' is in the ERD but missing in the database")
    for table in sorted(existing - set(SPEC)):
        report.add("FAIL", f"Table '{table}' is in the database but not in the ERD")

    for table, spec in SPEC.items():
        if table not in existing:
            continue
        problems = 0

        real_cols = {c["name"]: c for c in inspector.get_columns(table)}
        pk_cols = inspector.get_pk_constraint(table).get("constrained_columns") or []

        for name, (expected_type, expected_null) in spec["columns"].items():
            col = real_cols.get(name)
            if col is None:
                report.add("FAIL", f"{table}.{name} is missing")
                problems += 1
                continue
            real_type = normalise_type(col["type"])
            if real_type != normalise_type(expected_type):
                report.add("FAIL", f"{table}.{name} has type {real_type}, the ERD says {expected_type}")
                problems += 1
            if name not in pk_cols and bool(col["nullable"]) != expected_null:
                wanted = "allow NULL" if expected_null else "be NOT NULL"
                report.add("FAIL", f"{table}.{name} should {wanted}")
                problems += 1
        for name in sorted(set(real_cols) - set(spec["columns"])):
            report.add("FAIL", f"{table}.{name} is in the database but not in the ERD")
            problems += 1

        if list(pk_cols) != spec["pk"]:
            report.add("FAIL", f"{table} primary key is {list(pk_cols)}, the ERD says {spec['pk']}")
            problems += 1

        real_fks = {
            (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
            for fk in inspector.get_foreign_keys(table)
        }
        wanted_fks = {(tuple(c), parent, tuple(pc)) for c, parent, pc in spec["fks"]}
        for cols, parent, parent_cols in sorted(wanted_fks - real_fks):
            report.add("FAIL", f"{table}.{','.join(cols)} should be a foreign key to {parent}.{','.join(parent_cols)}")
            problems += 1
        for cols, parent, parent_cols in sorted(real_fks - wanted_fks):
            report.add("FAIL", f"{table}.{','.join(cols)} is a foreign key to {parent} but not in the ERD")
            problems += 1

        real_unique = {tuple(u["column_names"]) for u in inspector.get_unique_constraints(table)}
        real_unique |= {tuple(i["column_names"]) for i in inspector.get_indexes(table) if i.get("unique")}
        for cols in spec["unique"]:
            if tuple(cols) not in real_unique:
                report.add("FAIL", f"{table}.{','.join(cols)} should be UNIQUE")
                problems += 1

        if problems == 0:
            report.add(
                "OK",
                f"{table}: {len(spec['columns'])} columns, primary key, {len(spec['fks'])} foreign key(s) match the ERD",
            )


def check_data(conn, inspector, report: Report) -> None:
    existing = set(inspector.get_table_names())
    if not set(SPEC) <= existing:
        report.add("WARN", "Data checks skipped because some tables are missing")
        return

    # 1. every foreign key value points at a real row (no orphans)
    for table, spec in SPEC.items():
        for cols, parent, parent_cols in spec["fks"]:
            col, parent_col = cols[0], parent_cols[0]
            orphans = _scalar(
                conn,
                f"SELECT COUNT(*) FROM {table} c LEFT JOIN {parent} p ON c.{col} = p.{parent_col} "
                f"WHERE c.{col} IS NOT NULL AND p.{parent_col} IS NULL",
            )
            if orphans:
                report.add("FAIL", f"{orphans} row(s) in {table}.{col} point to a missing {parent} row")
            else:
                report.add("OK", f"No orphan rows in {table}.{col} -> {parent}.{parent_col}")

    # 2. passwords are hashed, never plain text
    unhashed = _scalar(conn, "SELECT COUNT(*) FROM users WHERE password_hash NOT LIKE '$2%'")
    report.add("FAIL" if unhashed else "OK",
               f"{unhashed} user(s) have a password that is not a bcrypt hash" if unhashed
               else "All passwords are stored as bcrypt hashes")

    # 3. emails are unique, also ignoring upper/lower case
    dupes = _scalar(
        conn, "SELECT COUNT(*) FROM (SELECT LOWER(email) FROM users GROUP BY LOWER(email) HAVING COUNT(*) > 1) d"
    )
    report.add("FAIL" if dupes else "OK",
               f"{dupes} email(s) are registered more than once" if dupes else "No duplicate emails")

    # 4. business rules
    own = _scalar(
        conn, "SELECT COUNT(*) FROM orders o JOIN items i ON o.item_id = i.item_id WHERE o.buyer_id = i.seller_id"
    )
    report.add("FAIL" if own else "OK",
               f"{own} order(s) are for the buyer's own item" if own else "No order is for the buyer's own item")

    to_self = _scalar(conn, "SELECT COUNT(*) FROM messages WHERE sender_id = receiver_id")
    report.add("FAIL" if to_self else "OK",
               f"{to_self} message(s) were sent to the sender themselves" if to_self else "No message is sent to oneself")

    bad_price = _scalar(conn, "SELECT COUNT(*) FROM items WHERE price <= 0")
    report.add("FAIL" if bad_price else "OK",
               f"{bad_price} item(s) have a price of 0 or less" if bad_price else "All item prices are above 0")

    reserved = _scalar(
        conn,
        "SELECT COUNT(*) FROM items i WHERE i.status = 'reserved' AND NOT EXISTS "
        "(SELECT 1 FROM orders o WHERE o.item_id = i.item_id AND o.status = 'accepted')",
    )
    if reserved:
        report.add("WARN", f"{reserved} reserved item(s) have no accepted order (fine if the seller reserved them by hand)")
    else:
        report.add("OK", "Every reserved item has an accepted order")

    # 5. row counts, handy for the demo
    counts = ", ".join(f"{t}={_scalar(conn, f'SELECT COUNT(*) FROM {t}')}" for t in SPEC)
    report.add("INFO", f"Row counts: {counts}")


def run_checks(engine) -> Report:
    report = Report()
    inspector = inspect(engine)
    check_structure(inspector, report)
    with engine.connect() as conn:
        check_data(conn, inspector, report)
    return report


def show_tables(engine) -> None:
    """Print the real tables so they can be shown next to the ERD."""
    inspector = inspect(engine)
    for table in SPEC:
        if table not in inspector.get_table_names():
            print(f"\n{table}: MISSING")
            continue
        pk = inspector.get_pk_constraint(table).get("constrained_columns") or []
        fks = {}
        for fk in inspector.get_foreign_keys(table):
            for col, pcol in zip(fk["constrained_columns"], fk["referred_columns"]):
                fks[col] = f"{fk['referred_table']}.{pcol}"
        uniques = {c for u in inspector.get_unique_constraints(table) for c in u["column_names"]}
        print(f"\n{table}")
        print(f"  {'column':<18}{'type':<16}{'null':<6}key")
        for col in inspector.get_columns(table):
            keys = []
            if col["name"] in pk:
                keys.append("PK")
            if col["name"] in fks:
                keys.append("FK -> " + fks[col["name"]])
            if col["name"] in uniques:
                keys.append("UNIQUE")
            null = "yes" if col["nullable"] and col["name"] not in pk else "no"
            print(f"  {col['name']:<18}{normalise_type(col['type']):<16}{null:<6}{', '.join(keys)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the real database against the ERD.")
    parser.add_argument("--url", help="database URL (default: the one the API uses)")
    parser.add_argument("--show", action="store_true", help="also print every real table")
    args = parser.parse_args()

    url = args.url
    if url is None:
        from app.config import DATABASE_URL
        url = DATABASE_URL

    if url.startswith("sqlite:///") and ":memory:" not in url:
        path = Path(url[len("sqlite:///"):])
        if not path.exists():
            print(f"Database file not found: {path}")
            print("Start the API once (uvicorn app.main:app) so it creates the database, then run this again.")
            return 2

    engine = create_engine(url)
    try:
        report = run_checks(engine)
    except Exception as error:  # cannot connect, wrong URL, and so on
        print(f"Could not check the database: {error}")
        return 2

    print(f"Database: {url}\n")
    for level, message in report.rows:
        print(f"[{level:<4}] {message}")
    if args.show:
        show_tables(engine)

    print()
    if report.failures:
        print(f"RESULT: {len(report.failures)} problem(s) found. The database does NOT match the ERD.")
        return 1
    suffix = f" ({len(report.warnings)} warning(s))" if report.warnings else ""
    print(f"RESULT: the database matches the ERD{suffix}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
