import sqlite3
from .validation import amount_to_paise, valid_date, date_range, PAYMENTS


class TransactionManager:
    def __init__(self, db):
        self.db = db

    def categories(self, kind=None):
        sql = 'SELECT * FROM categories'
        args = []
        if kind:
            sql += ' WHERE type=?'
            args.append(kind)
        return [dict(r) for r in self.db.connection.execute(sql + ' ORDER BY name,type', args)]

    def add_category(self, name, kind):
        name = name.strip()
        if not 1 <= len(name) <= 60 or kind not in ('income', 'expense'):
            raise ValueError('Provide a category name (1–60 characters) and income/expense type.')
        try:
            with self.db.connection:
                return self.db.connection.execute(
                    'INSERT INTO categories(name,type) VALUES (?,?)', (name, kind)).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError('That category already exists for this type.') from None

    def validate(self, kind, amount, category_id, day, description, payment):
        if kind not in ('income', 'expense'):
            raise ValueError('Choose income or expense.')
        paise = amount_to_paise(amount)
        day = valid_date(day)
        description = description.strip()
        if not 1 <= len(description) <= 500:
            raise ValueError('Description must contain 1–500 characters.')
        if payment not in PAYMENTS:
            raise ValueError('Choose a valid payment method.')
        if not self.db.connection.execute('SELECT 1 FROM categories WHERE id=? AND type=?',
                                          (category_id, kind)).fetchone():
            raise ValueError('Choose a category belonging to the transaction type.')
        return kind, paise, category_id, day, description, payment

    def add(self, kind, amount, category_id, day, description, payment):
        values = self.validate(kind, amount, category_id, day, description, payment)
        with self.db.connection:
            return self.db.connection.execute(
                'INSERT INTO transactions(type,amount_paise,category_id,date,description,payment_method) '
                'VALUES (?,?,?,?,?,?)', values).lastrowid

    def update(self, transaction_id, kind, amount, category_id, day, description, payment):
        values = self.validate(kind, amount, category_id, day, description, payment)
        with self.db.connection:
            cursor = self.db.connection.execute(
                'UPDATE transactions SET type=?,amount_paise=?,category_id=?,date=?,description=?,payment_method=? WHERE id=?',
                (*values, transaction_id))
            if cursor.rowcount == 0:
                raise ValueError('Transaction no longer exists.')

    def delete(self, transaction_id):
        with self.db.connection:
            if self.db.connection.execute('DELETE FROM transactions WHERE id=?', (transaction_id,)).rowcount == 0:
                raise ValueError('Transaction no longer exists.')

    def get(self, transaction_id):
        row = self.db.connection.execute('SELECT * FROM transactions WHERE id=?', (transaction_id,)).fetchone()
        if row is None:
            raise ValueError('Transaction no longer exists.')
        return dict(row)

    def list(self, start='', end='', kind='', category_id=None, search='', sort='date_desc'):
        start, end = date_range(start, end)
        orders = {'date_desc': 't.date DESC,t.id DESC', 'date_asc': 't.date,t.id',
                  'amount_desc': 't.amount_paise DESC,t.id DESC', 'amount_asc': 't.amount_paise,t.id'}
        if sort not in orders:
            raise ValueError('Invalid sorting option.')
        sql = 'SELECT t.*,c.name AS category FROM transactions t JOIN categories c ON t.category_id=c.id WHERE 1=1'
        args = []
        for clause, value in [('t.date>=?', start), ('t.date<=?', end), ('t.type=?', kind),
                              ('t.category_id=?', category_id)]:
            if value:
                sql += ' AND ' + clause
                args.append(value)
        if search:
            sql += ' AND instr(lower(t.description),lower(?))>0'
            args.append(search.strip())
        # Only an allowlisted SQL fragment is interpolated; user values are bound.
        return [dict(r) for r in self.db.connection.execute(sql + ' ORDER BY ' + orders[sort], args)]
