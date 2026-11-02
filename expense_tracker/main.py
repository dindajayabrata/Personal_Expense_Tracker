
import argparse
import logging
from pathlib import Path
import sys
from tracker.database import Database

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Personal Expense Tracker')
    parser.add_argument('--db', type=Path, default=ROOT / 'data' / 'expenses.db')
    parser.add_argument('--init-db', action='store_true')
    args = parser.parse_args()
    (ROOT / 'data').mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT / 'data' / 'app.log', level=logging.ERROR)
    db = None
    try:
        db = Database(args.db)
        if args.init_db:
            print(f'Database initialized: {db.path.resolve()}')
            db.close()
            return 0
        from tracker.transactions import TransactionManager
        from tracker.budgets import BudgetManager
        from tracker.analytics import Analytics
        from tracker.reports import ReportManager
        from tracker.gui import ExpenseApp
        tx = TransactionManager(db)
        analytics = Analytics(tx)
        app = ExpenseApp(db, tx, BudgetManager(db), analytics, ReportManager(tx, analytics))
        app.mainloop()
        return 0
    except Exception as exc:
        logging.exception('Startup failed')
        print(f'Could not start Expense Tracker: {exc}', file=sys.stderr)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror('Startup failed', f'{exc}\n\nCheck dependencies and database permissions.')
            root.destroy()
        except Exception:
            pass
        if db:
            db.close()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
