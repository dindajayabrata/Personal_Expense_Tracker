from pathlib import Path
import sqlite3

DEFAULTS = {
    'expense': ['Food', 'Rent', 'Transport', 'Shopping', 'Education',
                'Entertainment', 'Healthcare', 'Utilities', 'Other'],
    'income': ['Salary', 'Freelance', 'Other'],
}


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.executescript(Path(__file__).with_name('schema.sql').read_text())
        with self.connection:
            for kind, names in DEFAULTS.items():
                self.connection.executemany(
                    'INSERT OR IGNORE INTO categories(name,type) VALUES (?,?)',
                    [(name, kind) for name in names])

    def close(self):
        self.connection.close()
