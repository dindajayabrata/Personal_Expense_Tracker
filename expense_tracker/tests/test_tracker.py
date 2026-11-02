"""Run from the project root: python -m unittest discover -s tests -v."""
import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from tracker.database import Database
from tracker.transactions import TransactionManager
from tracker.budgets import BudgetManager
from tracker.analytics import Analytics, CHARTS
from tracker.reports import ReportManager, FIELDS
from tracker.validation import amount_to_paise, valid_date
from matplotlib.backends.backend_agg import FigureCanvasAgg


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(self.root / 'test.db')
        self.tx = TransactionManager(self.db)
        self.budget = BudgetManager(self.db)
        self.analytics = Analytics(self.tx)
        self.reports = ReportManager(self.tx, self.analytics)
        self.food = next(c['id'] for c in self.tx.categories('expense') if c['name'] == 'Food')
        self.salary = next(c['id'] for c in self.tx.categories('income') if c['name'] == 'Salary')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def expense(self, amount='80.10', day='2026-10-10', description='Lunch'):
        return self.tx.add('expense', amount, self.food, day, description, 'UPI')

    def test_exact_amount_validation(self):
        self.assertEqual(amount_to_paise('0.29'), 29)
        for value in ['0','-1','nan','Infinity','abc','1.001','1000000001','']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                amount_to_paise(value)

    def test_calendar_validation(self):
        self.assertEqual(valid_date('2024-02-29'), '2024-02-29')
        for value in ['2025-02-29','2026-13-01','2026-1-01','2026-04-31']:
            with self.assertRaises(ValueError):
                valid_date(value)

    def test_crud_and_missing(self):
        tid = self.expense()
        self.tx.update(tid, 'expense', '99.99', self.food, '2026-10-11', 'Dinner', 'Cash')
        self.assertEqual(self.tx.get(tid)['amount_paise'], 9999)
        self.tx.delete(tid)
        for action in [lambda: self.tx.get(tid), lambda: self.tx.delete(tid),
                       lambda: self.tx.update(tid,'expense',1,self.food,'2026-10-01','x','Cash')]:
            with self.assertRaises(ValueError):
                action()

    def test_category_types_and_duplicates(self):
        self.tx.add_category('Travel', 'expense')
        with self.assertRaises(ValueError):
            self.tx.add_category('travel', 'expense')
        with self.assertRaises(ValueError):
            self.tx.add('income', '100', self.food, '2026-10-01', 'Wrong', 'Cash')
        with self.assertRaises(ValueError):
            self.budget.set('2026-10','100',self.salary)

    def test_sql_constraints(self):
        with self.assertRaises(sqlite3.IntegrityError), self.db.connection:
            self.db.connection.execute("INSERT INTO transactions(type,amount_paise,category_id,date,description,payment_method) VALUES ('income',100,?,'2026-10-01','Wrong','Cash')", (self.food,))
        with self.assertRaises(sqlite3.IntegrityError), self.db.connection:
            self.db.connection.execute("INSERT INTO budgets(month,category_id,amount_paise) VALUES ('2026-10',?,100)", (self.salary,))

    def test_filters_and_sort(self):
        self.expense('50', '2026-09-01', "Cafe's meal")
        self.expense('20', '2026-10-02', 'Lunch')
        self.tx.add('income','100',self.salary,'2026-10-03','Salary','Bank Transfer')
        self.assertEqual(len(self.tx.list(start='2026-10-01',end='2026-10-31',kind='expense',category_id=self.food)), 1)
        self.assertEqual(len(self.tx.list(search="Cafe's")), 1)
        self.assertEqual(self.tx.list(sort='amount_asc')[0]['amount_paise'], 2000)
        self.assertEqual(self.tx.list(search="' OR 1=1 --"), [])
        with self.assertRaises(ValueError):
            self.tx.list(start='2026-12-01',end='2026-01-01')

    def test_budget_thresholds_and_upsert(self):
        self.budget.set('2026-10','100')
        self.budget.set('2026-10','100',self.food)
        self.expense('80')
        self.assertEqual(self.budget.status('2026-10')[0]['percent'],80)
        self.assertIn('Warning',self.budget.status('2026-10')[0]['warning'])
        self.expense('20')
        self.assertEqual(self.budget.status('2026-10')[0]['remaining'],0)
        self.expense('0.01')
        self.assertEqual(self.budget.status('2026-10')[0]['warning'],'OVER BUDGET')
        self.budget.set('2026-10','200')
        self.assertEqual(len(self.budget.status('2026-10')),2)
        self.assertEqual(self.budget.status('2026-10')[0]['amount_paise'],20000)
        self.assertEqual(self.budget.status('2026-09'),[])

    def test_persistence_and_idempotent_init(self):
        self.expense()
        second = Database(self.db.path)
        try:
            self.assertEqual(len(TransactionManager(second).list()),1)
            self.assertEqual(len(TransactionManager(second).categories()),12)
        finally:
            second.close()

    def test_analytics_and_month_gaps(self):
        self.expense('10','2026-08-01')
        self.expense('20','2026-10-01')
        self.tx.add('income','100',self.salary,'2026-10-01','Pay','Cash')
        self.assertEqual(self.analytics.summary(),dict(income=10000,expense=3000,balance=7000,count=3))
        monthly = self.analytics.monthly(self.analytics.frame())
        self.assertEqual(monthly.loc['2026-09','expense'],0)
        self.assertEqual(self.analytics.categories(self.analytics.frame()).loc['Food'],3000)

    def test_csv_roundtrip(self):
        self.expense(description='Lunch, tea & "coffee"')
        path = self.root / 'roundtrip.csv'
        self.reports.export_csv(path)
        self.assertEqual(self.reports.import_csv(path),1)
        self.assertEqual(self.tx.list()[0]['description'],'Lunch, tea & "coffee"')

    def test_csv_invalid_row_atomic(self):
        path = self.root / 'invalid.csv'
        with path.open('w',newline='') as f:
            writer = csv.writer(f)
            writer.writerow(FIELDS)
            writer.writerow(['expense','100','Food','2026-10-01','Lunch','Cash'])
            writer.writerow(['expense','-1','Food','2026-10-01','Bad','Cash'])
        with self.assertRaisesRegex(ValueError,'row 3'):
            self.reports.import_csv(path)
        self.assertEqual(self.tx.list(),[])

    def test_csv_headers_and_unknown_category(self):
        path = self.root / 'bad.csv'
        path.write_text('x,y\n1,2\n')
        with self.assertRaises(ValueError):
            self.reports.import_csv(path)
        path.write_text(','.join(FIELDS)+'\nexpense,10,Unknown,2026-10-01,Test,Cash\n')
        with self.assertRaises(ValueError):
            self.reports.import_csv(path)

    def test_all_charts_empty_and_populated(self):
        for populated in [False, True]:
            if populated:
                self.expense()
                self.tx.add('income','1000',self.salary,'2026-10-01','Pay','Cash')
            for chart in CHARTS:
                fig = self.analytics.figure(chart)
                FigureCanvasAgg(fig).draw()
                fig.clear()

    def test_pdf_empty_and_multipage(self):
        path = self.root / 'report.pdf'
        self.reports.pdf(path)
        self.assertTrue(path.read_bytes().startswith(b'%PDF'))
        for i in range(50):
            self.expense(description=f'Example {i}: <expense> & details')
        self.reports.pdf(path)
        self.assertGreater(path.stat().st_size,4000)
        self.assertIn('CATEGORY EXPENSE SUMMARY',self.reports.text())


if __name__ == '__main__':
    unittest.main()
