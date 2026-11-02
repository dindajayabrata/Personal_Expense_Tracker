import csv
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
from .validation import money

FIELDS = ['type', 'amount', 'category', 'date', 'description', 'payment_method']


class ReportManager:
    def __init__(self, transactions, analytics):
        self.transactions = transactions
        self.analytics = analytics

    def import_csv(self, path):
        prepared = []
        with open(path, newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                raise ValueError('CSV headers must be exactly: ' + ','.join(FIELDS))
            categories = {(c['name'].casefold(), c['type']): c['id'] for c in self.transactions.categories()}
            for number, row in enumerate(reader, 2):
                try:
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError('Wrong number of columns.')
                    kind = row['type'].strip().lower()
                    category_id = categories.get((row['category'].strip().casefold(), kind))
                    prepared.append(self.transactions.validate(kind, row['amount'], category_id, row['date'],
                                                               row['description'], row['payment_method'].strip()))
                except ValueError as exc:
                    raise ValueError(f'CSV row {number}: {exc} No rows were imported.') from exc
        if not prepared:
            raise ValueError('CSV contains no transactions.')
        # One transaction: either every row is committed or none is.
        with self.transactions.db.connection:
            self.transactions.db.connection.executemany(
                'INSERT INTO transactions(type,amount_paise,category_id,date,description,payment_method) VALUES (?,?,?,?,?,?)', prepared)
        return len(prepared)

    def _temporary(self, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = NamedTemporaryFile(dir=target.parent, suffix=target.suffix, delete=False)
        handle.close()
        return Path(handle.name)

    def export_csv(self, path, start='', end=''):
        rows = self.transactions.list(start=start, end=end)
        temp = self._temporary(path)
        try:
            with temp.open('w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: f"{row['amount_paise']/100:.2f}" if key == 'amount' else row[key] for key in FIELDS})
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        return len(rows)

    def text(self, start='', end=''):
        data = self.analytics.summary(start, end)
        df = self.analytics.frame(start, end)
        lines = [f'Period: {start or "All dates"} to {end or "All dates"}',
                 f'Income: {money(data["income"])}', f'Expenses: {money(data["expense"])}',
                 f'Net balance: {money(data["balance"])}', f'Transactions: {data["count"]}',
                 '', 'MONTHLY SUMMARY']
        for month, row in self.analytics.monthly(df).iterrows():
            lines.append(f'{month} | Income {money(row.income)} | Expenses {money(row.expense)} | Net {money(row.income-row.expense)}')
        lines += ['', 'CATEGORY EXPENSE SUMMARY']
        for category, total in self.analytics.categories(df).items():
            lines.append(f'{category}: {money(total)}')
        return '\n'.join(lines)

    def pdf(self, path, start='', end=''):
        rows = self.transactions.list(start=start, end=end)
        styles = getSampleStyleSheet()
        # INR avoids missing rupee glyphs in built-in PDF fonts.
        def para(value, style='BodyText'):
            return Paragraph(escape(str(value)).replace('\n', '<br/>'), styles[style])
        story = [para('Personal Expense Tracker', 'Title'), Spacer(1, 12),
                 para(self.text(start, end).replace('₹', 'INR ')), Spacer(1, 18),
                 para('Transaction details', 'Heading2')]
        table = [['ID', 'Date', 'Type', 'Category', 'Amount (INR)', 'Description', 'Payment']]
        for row in rows:
            table.append([para(row[k]) for k in ('id', 'date', 'type', 'category')] +
                         [para(f"{row['amount_paise']/100:,.2f}"), para(row['description']), para(row['payment_method'])])
        if not rows:
            story.append(para('No transactions in this period.'))
        else:
            grid = LongTable(table, colWidths=[30, 65, 52, 80, 85, 280, 85], repeatRows=1)
            grid.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563eb')),
                                     ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                                     ('VALIGN', (0,0), (-1,-1), 'TOP'),
                                     ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#eff6ff')]),
                                     ('BOTTOMPADDING', (0,0), (-1,-1), 7)]))
            story.append(grid)
        def footer(canvas, document):
            canvas.setFont('Helvetica', 9)
            canvas.drawRightString(805, 20, f'Page {document.page}')
        temp = self._temporary(path)
        try:
            SimpleDocTemplate(str(temp), pagesize=landscape(A4), leftMargin=30, rightMargin=30,
                              topMargin=30, bottomMargin=35).build(story, onFirstPage=footer, onLaterPages=footer)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
