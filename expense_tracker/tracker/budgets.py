from .validation import amount_to_paise, valid_month


class BudgetManager:
    def __init__(self, db):
        self.db = db

    def set(self, month, amount, category_id=None):
        month, paise = valid_month(month), amount_to_paise(amount)
        if category_id is not None:
            row = self.db.connection.execute('SELECT type FROM categories WHERE id=?', (category_id,)).fetchone()
            if row is None or row['type'] != 'expense':
                raise ValueError('Category budgets must use an expense category.')
        with self.db.connection:
            row = self.db.connection.execute('SELECT id FROM budgets WHERE month=? AND category_id IS ?',
                                              (month, category_id)).fetchone()
            if row:
                self.db.connection.execute('UPDATE budgets SET amount_paise=? WHERE id=?', (paise, row['id']))
            else:
                self.db.connection.execute('INSERT INTO budgets(month,category_id,amount_paise) VALUES (?,?,?)',
                                           (month, category_id, paise))

    def delete(self, budget_id):
        with self.db.connection:
            if not self.db.connection.execute('DELETE FROM budgets WHERE id=?', (budget_id,)).rowcount:
                raise ValueError('Budget no longer exists.')

    def status(self, month):
        month = valid_month(month)
        rows = self.db.connection.execute(
            "SELECT b.*,COALESCE(c.name,'Overall monthly budget') AS category FROM budgets b "
            'LEFT JOIN categories c ON c.id=b.category_id WHERE month=? ORDER BY b.category_id', (month,))
        result = []
        for row in rows.fetchall():
            item = dict(row)
            sql = "SELECT COALESCE(SUM(amount_paise),0) FROM transactions WHERE type='expense' AND substr(date,1,7)=?"
            args = [month]
            if item['category_id'] is not None:
                sql += ' AND category_id=?'
                args.append(item['category_id'])
            spent = self.db.connection.execute(sql, args).fetchone()[0]
            percent = spent / item['amount_paise'] * 100
            item.update(spent=spent, remaining=item['amount_paise'] - spent, percent=percent,
                        warning='OVER BUDGET' if percent > 100 else 'Warning: 80% or more used' if percent >= 80 else 'Within budget')
            result.append(item)
        return result
