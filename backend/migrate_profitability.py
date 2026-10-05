"""
DukaSmart - migrate_profitability.py

EXACT LOCATION: save this file in your `backend` folder — the SAME folder
that contains dukasmart.db.

HOW TO RUN IT (pick one):
  Option A - double-click it in File Explorer, if .py files are set to
  open with Python on your computer.
  Option B (more reliable) - open a terminal in VS Code, make sure you're
  in the backend folder, and run:
      python migrate_profitability.py

WHY YOUR .bat FILE FAILED: when a batch file is run as Administrator (or
launched some other ways), Windows can start it in C:\\Windows\\System32
instead of the folder the file is actually saved in. This script avoids
that whole problem — it doesn't care what folder you're "in" when you run
it, because it looks for dukasmart.db based on where THIS FILE is saved
on disk, not based on the current working directory.

WHAT IT DOES, IN ORDER:
  1. Finds dukasmart.db next to this script.
  2. Backs it up to dukasmart_backup_YYYYMMDD_HHMMSS.db (same folder).
  3. Adds these 4 columns to the "recommendations" table, skipping any
     that already exist (safe to run more than once):
       - gross_profit_per_unit  (REAL)
       - expected_gross_profit  (REAL)
       - priority_score         (REAL)
       - priority_reason        (TEXT)
  4. Prints a clear SUCCESS or FAILED message.
  5. Waits for you to press Enter before closing, so you can read
     everything even if you double-clicked this file and a window
     popped up and would otherwise vanish immediately.

Uses only Python's built-in sqlite3, os, shutil, sys, and datetime
modules - nothing extra to install.
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime

# ----------------------------------------------------------------------
# If your Recommendation model's __tablename__ is something other than
# "recommendations", change it here. (Check backend/app/models/ for the
# Recommendation class to confirm.)
# ----------------------------------------------------------------------
TABLE_NAME = "recommendations"

NEW_COLUMNS = [
    ("gross_profit_per_unit", "REAL"),
    ("expected_gross_profit", "REAL"),
    ("priority_score", "REAL"),
    ("priority_reason", "TEXT"),
]


def get_script_folder():
    return os.path.dirname(os.path.abspath(__file__))


def get_db_path():
    return os.path.join(get_script_folder(), "dukasmart.db")


def backup_database(db_path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(get_script_folder(), f"dukasmart_backup_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    return backup_path


def table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run():
    print("=" * 60)
    print("DukaSmart Profitability Migration")
    print("=" * 60)

    db_path = get_db_path()
    print(f"Looking for database at:\n  {db_path}\n")

    if not os.path.exists(db_path):
        print("ERROR: dukasmart.db was not found in this script's folder.")
        print("Make sure migrate_profitability.py is saved in the same")
        print("folder as dukasmart.db, then run it again.")
        return False

    try:
        backup_path = backup_database(db_path)
        print(f"Backup created:\n  {backup_path}\n")
    except Exception as e:
        print(f"ERROR: could not create a backup - migration was NOT run.")
        print(f"Details: {e}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if not table_exists(cursor, TABLE_NAME):
            print(f"ERROR: no table named '{TABLE_NAME}' was found in dukasmart.db.")
            print("Open backend/app/models/, find your Recommendation class, and")
            print("check its __tablename__. Then update TABLE_NAME near the top")
            print("of this script to match, and run it again.")
            conn.close()
            return False

        print("Checking existing columns...")
        added_any = False
        for column_name, column_type in NEW_COLUMNS:
            if column_exists(cursor, TABLE_NAME, column_name):
                print(f"  - '{column_name}' already exists, skipping.")
                continue
            sql = f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column_name} {column_type};"
            print(f"  - Adding '{column_name}'...")
            cursor.execute(sql)
            added_any = True

        conn.commit()
        conn.close()

        if added_any:
            print("\nNew columns added successfully.")
        else:
            print("\nAll columns already existed - nothing needed to change.")

        return True

    except Exception as e:
        print(f"\nERROR while updating the database: {e}")
        print("Your backup file above is untouched and safe to restore from")
        print("if needed (just rename it back to dukasmart.db).")
        return False


def main():
    success = run()

    print("\n" + "=" * 60)
    if success:
        print("RESULT: SUCCESS - your database is ready.")
    else:
        print("RESULT: FAILED - see the messages above for what went wrong.")
    print("=" * 60)

    input("\nPress Enter to close this window...")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
