import logging
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from .validation import PAYMENTS, money
from .analytics import CHARTS


class ExpenseApp(tk.Tk):
    def __init__(self, db, transactions, budgets, analytics, reports):
        super().__init__()
        self.db, self.tx, self.budgets = db, transactions, budgets
        self.analytics, self.reports = analytics, reports
        self.chart_canvas = None
        self.title('Personal Expense Tracker')
        self.geometry('1200x780')
        self.minsize(1000, 700)
        self.configure(bg='#f1f5fb')
        self.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#f1f5fb')
        style.configure('TLabel', background='#f1f5fb', foreground='#183153')
        style.configure('TButton', padding=(12, 8), background='#2563eb', foreground='white')
        style.map('TButton', background=[('active', '#1d4ed8')])
        style.configure('Treeview', rowheight=30, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=8)
        sidebar = tk.Frame(self, bg='#123263', width=210)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='EXPENSE\nTRACKER', font=('Segoe UI', 20, 'bold'),
                 bg='#123263', fg='white', justify='left').pack(padx=22, pady=30, anchor='w')
        for label, handler in [('Dashboard', self.dashboard), ('Add Transaction', self.transaction_form),
                               ('Transaction History', self.history), ('Categories', self.categories_page),
                               ('Budgets', self.budget_page), ('Analytics', self.analytics_page), ('Reports', self.reports_page)]:
            button = tk.Button(sidebar, text=label, command=lambda h=handler: self.safe(h),
                               bg='#123263', fg='white', activebackground='#2563eb', activeforeground='white',
                               relief='flat', anchor='w', padx=22, pady=12, font=('Segoe UI', 11))
            button.pack(fill='x', pady=2)
            button.bind('<Enter>', lambda event: event.widget.configure(bg='#1e4a85'))
            button.bind('<Leave>', lambda event: event.widget.configure(bg='#123263'))
        tk.Label(sidebar, text='Local data • INR\nNo account required', bg='#123263', fg='#bdd2ef',
                 justify='left').pack(side='bottom', padx=22, pady=25, anchor='w')
        self.content = ttk.Frame(self, padding=24)
        self.content.pack(side='left', fill='both', expand=True)
        self.safe(self.dashboard)

    def close(self):
        self.db.close()
        self.destroy()

    def report_callback_exception(self, exception, value, traceback):
        logging.error('GUI error', exc_info=(exception, value, traceback))
        messagebox.showerror('Unable to complete action', str(value), parent=self)

    def safe(self, action):
        try:
            return action()
        except (ValueError, OSError, sqlite3.Error) as exc:
            messagebox.showerror('Please check your input', str(exc), parent=self)
        except Exception:
            logging.exception('Unexpected action failure')
            messagebox.showerror('Action failed', 'The action could not finish. See data/app.log for details.', parent=self)

    def page(self, title, subtitle=''):
        if self.chart_canvas:
            self.chart_canvas.get_tk_widget().destroy()
            self.chart_canvas.figure.clear()
            self.chart_canvas = None
        for widget in self.content.winfo_children():
            widget.destroy()
        ttk.Label(self.content, text=title, font=('Segoe UI', 23, 'bold')).pack(anchor='w', pady=(0, 5))
        if subtitle:
            ttk.Label(self.content, text=subtitle).pack(anchor='w', pady=(0, 18))

    def button(self, parent, label, action):
        button = ttk.Button(parent, text=label, command=lambda: self.safe(action))
        button.pack(side='left', padx=(0, 8), pady=8)
        return button

    def field(self, parent, label, value='', options=None, width=24):
        frame = ttk.Frame(parent)
        frame.pack(side='left', padx=(0, 12), pady=6, fill='x', expand=True)
        ttk.Label(frame, text=label).pack(anchor='w', pady=(0, 5))
        var = tk.StringVar(value=value)
        if options is None:
            widget = ttk.Entry(frame, textvariable=var, width=width)
        else:
            widget = ttk.Combobox(frame, textvariable=var, values=options, state='readonly', width=width)
        widget.pack(fill='x')
        return var, widget

    def row(self):
        frame = ttk.Frame(self.content)
        frame.pack(fill='x')
        return frame

    def table(self, parent, columns, rows, height=12):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=10)
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=height, selectmode='browse')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=130, minwidth=70, stretch=True)
        vertical = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for row in rows:
            tree.insert('', 'end', values=row)
        return tree

    def transaction_rows(self, rows):
        return [(r['id'], r['date'], r['type'], money(r['amount_paise']), r['category'], r['description'], r['payment_method']) for r in rows]

    def selected_id(self, tree):
        if not tree.selection():
            raise ValueError('Select a row first.')
        return int(tree.item(tree.selection()[0], 'values')[0])

    def dashboard(self):
        month = date.today().strftime('%Y-%m')
        self.page('Your money, at a glance', f'{month} • All-time totals and this month’s spending')
        summary = self.analytics.summary()
        spent = sum(r['amount_paise'] for r in self.tx.list(kind='expense') if r['date'].startswith(month))
        statuses = self.budgets.status(month)
        overall = next((b for b in statuses if b['category_id'] is None), None)
        cards = [('Total income', money(summary['income'])), ('Total expenses', money(summary['expense'])),
                 ('Available balance', money(summary['balance'])), ('This month’s expenses', money(spent)),
                 ('Monthly budget', money(overall['amount_paise']) if overall else 'Not set'),
                 ('Remaining budget', money(overall['remaining']) if overall else 'Not set')]
        container = ttk.Frame(self.content)
        container.pack(fill='x', pady=12)
        for i, (label, value) in enumerate(cards):
            card = tk.Frame(container, bg='white', padx=18, pady=15, highlightbackground='#dce6f3', highlightthickness=1)
            card.grid(row=i//3, column=i%3, sticky='nsew', padx=5, pady=5)
            container.columnconfigure(i%3, weight=1)
            tk.Label(card, text=label, bg='white', fg='#64748b', font=('Segoe UI', 10)).pack(anchor='w')
            tk.Label(card, text=value, bg='white', fg='#123263', font=('Segoe UI', 19, 'bold')).pack(anchor='w', pady=(8,0))
        if overall:
            ttk.Label(self.content, text=f"Budget utilization: {overall['percent']:.1f}% — {overall['warning']}").pack(anchor='w', pady=8)
            ttk.Progressbar(self.content, value=min(overall['percent'], 100), maximum=100).pack(fill='x')
        else:
            ttk.Label(self.content, text='Set a monthly budget to track utilization.').pack(anchor='w')
        warnings = [f"{b['category']}: {b['warning']} ({b['percent']:.1f}%)" for b in statuses if b['percent'] >= 80]
        if warnings:
            ttk.Label(self.content, text='\n'.join(warnings[:3]), foreground='#b45309').pack(anchor='w', pady=6)
        ttk.Label(self.content, text='Recent transactions', font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(14,0))
        self.table(self.content, ('ID','Date','Type','Amount','Category','Description','Payment'), self.transaction_rows(self.tx.list()[:8]), height=6)

    def transaction_form(self, transaction_id=None):
        record = self.tx.get(transaction_id) if transaction_id else {}
        self.page('Edit transaction' if record else 'Add transaction', 'Use YYYY-MM-DD dates. Amounts are in Indian rupees.')
        row = self.row()
        kind, kind_box = self.field(row, 'Type', record.get('type', 'expense'), ('expense','income'))
        amount, _ = self.field(row, 'Amount (₹)', f"{record['amount_paise']/100:.2f}" if record else '')
        row = self.row()
        category, category_box = self.field(row, 'Category', '', [])
        day, _ = self.field(row, 'Date', record.get('date', date.today().isoformat()))
        row = self.row()
        description, _ = self.field(row, 'Description', record.get('description', ''))
        payment, _ = self.field(row, 'Payment method', record.get('payment_method', 'UPI'), PAYMENTS)
        choices = {}
        def refresh_categories(event=None):
            choices.clear()
            choices.update({c['name']: c['id'] for c in self.tx.categories(kind.get())})
            category_box['values'] = list(choices)
            category.set(next(iter(choices), ''))
        refresh_categories()
        if record:
            category.set(next(name for name, cid in choices.items() if cid == record['category_id']))
        kind_box.bind('<<ComboboxSelected>>', refresh_categories)
        def save():
            values = (kind.get(), amount.get(), choices.get(category.get()), day.get(), description.get(), payment.get())
            if transaction_id:
                self.tx.update(transaction_id, *values)
            else:
                self.tx.add(*values)
            messagebox.showinfo('Saved', 'Transaction saved.', parent=self)
            self.history()
        actions = self.row()
        self.button(actions, 'Save transaction', save)
        self.button(actions, 'Cancel', self.history)

    def history(self):
        self.page('Transaction history', 'Combine filters, then click Apply. Select a row to edit or delete it.')
        row = self.row()
        search, _ = self.field(row, 'Description contains', '', width=20)
        kind, _ = self.field(row, 'Type', 'All', ('All','income','expense'), width=12)
        cats = {'All': None, **{f"{c['name']} ({c['type']})": c['id'] for c in self.tx.categories()}}
        category, _ = self.field(row, 'Category', 'All', list(cats), width=20)
        row = self.row()
        start, _ = self.field(row, 'From (YYYY-MM-DD)', '', width=16)
        end, _ = self.field(row, 'To (YYYY-MM-DD)', '', width=16)
        sort, _ = self.field(row, 'Sort', 'date_desc', ('date_desc','date_asc','amount_desc','amount_asc'), width=16)
        actions = self.row()
        tree = self.table(self.content, ('ID','Date','Type','Amount','Category','Description','Payment'), [])
        def apply():
            rows = self.tx.list(start.get(), end.get(), '' if kind.get() == 'All' else kind.get(), cats[category.get()], search.get(), sort.get())
            tree.delete(*tree.get_children())
            for values in self.transaction_rows(rows):
                tree.insert('', 'end', values=values)
        def delete():
            tid = self.selected_id(tree)
            if messagebox.askyesno('Delete transaction?', f'Delete transaction #{tid}? This cannot be undone.', parent=self):
                self.tx.delete(tid)
                apply()
        self.button(actions, 'Apply', apply)
        self.button(actions, 'Reset', self.history)
        self.button(actions, 'Edit selected', lambda: self.transaction_form(self.selected_id(tree)))
        self.button(actions, 'Delete selected', delete)
        apply()

    def categories_page(self):
        self.page('Categories', 'Income and expense categories are separate. Other is available for both.')
        row = self.row()
        name, _ = self.field(row, 'New category name')
        kind, _ = self.field(row, 'Type', 'expense', ('expense', 'income'))
        def add():
            self.tx.add_category(name.get(), kind.get())
            self.categories_page()
        self.button(self.row(), 'Add category', add)
        self.table(self.content, ('ID','Name','Type'), [(c['id'],c['name'],c['type']) for c in self.tx.categories()])

    def budget_page(self):
        self.page('Budget management', 'Overall and category limits are independent. Save replaces the limit for the selected month and scope.')
        row = self.row()
        month, _ = self.field(row, 'Month (YYYY-MM)', date.today().strftime('%Y-%m'), width=14)
        cats = {'Overall monthly budget': None, **{c['name']: c['id'] for c in self.tx.categories('expense')}}
        category, _ = self.field(row, 'Scope', 'Overall monthly budget', list(cats), width=22)
        amount, _ = self.field(row, 'Budget amount (₹)', '', width=16)
        actions = self.row()
        tree = self.table(self.content, ('ID','Scope','Budget','Spent','Remaining','Used','Status'), [])
        def refresh():
            rows = self.budgets.status(month.get())
            tree.delete(*tree.get_children())
            for b in rows:
                tree.insert('', 'end', values=(b['id'],b['category'],money(b['amount_paise']),money(b['spent']),money(b['remaining']),f"{b['percent']:.1f}%",b['warning']))
        def save():
            self.budgets.set(month.get(), amount.get(), cats[category.get()])
            refresh()
        def remove():
            bid = self.selected_id(tree)
            if messagebox.askyesno('Remove budget?', 'Remove the selected budget?', parent=self):
                self.budgets.delete(bid)
                refresh()
        self.button(actions, 'Show month', refresh)
        self.button(actions, 'Save budget', save)
        self.button(actions, 'Remove selected', remove)
        refresh()

    def analytics_page(self):
        self.page('Analytics', 'Charts are calculated from your saved transactions. Blank dates include all records.')
        row = self.row()
        start, _ = self.field(row, 'From (YYYY-MM-DD)', '', width=16)
        end, _ = self.field(row, 'To (YYYY-MM-DD)', '', width=16)
        chart, _ = self.field(row, 'Chart', CHARTS[0], CHARTS, width=24)
        actions = self.row()
        host = ttk.Frame(self.content)
        host.pack(fill='both', expand=True)
        def draw():
            fig = self.analytics.figure(chart.get(), start.get(), end.get())
            if self.chart_canvas:
                self.chart_canvas.get_tk_widget().destroy()
                self.chart_canvas.figure.clear()
            self.chart_canvas = FigureCanvasTkAgg(fig, master=host)
            self.chart_canvas.draw()
            self.chart_canvas.get_tk_widget().pack(fill='both', expand=True)
        self.button(actions, 'Update chart', draw)
        draw()

    def reports_page(self):
        self.page('Reports and data transfer', 'Choose inclusive report dates. CSV imports append records; importing the same file twice creates duplicates.')
        row = self.row()
        start, _ = self.field(row, 'From (YYYY-MM-DD)', date.today().replace(day=1).isoformat())
        end, _ = self.field(row, 'To (YYYY-MM-DD)', date.today().isoformat())
        actions = self.row()
        output = tk.Text(self.content, wrap='word', font=('Consolas', 11), bg='white', fg='#183153', relief='flat', padx=15, pady=15)
        output.pack(fill='both', expand=True, pady=10)
        def preview():
            text = self.reports.text(start.get(), end.get())
            output.configure(state='normal')
            output.delete('1.0', 'end')
            output.insert('1.0', text)
            output.configure(state='disabled')
        def export(extension):
            path = filedialog.asksaveasfilename(parent=self, defaultextension='.'+extension,
                                              filetypes=[(extension.upper(), '*.'+extension)])
            if path:
                action = self.reports.pdf if extension == 'pdf' else self.reports.export_csv
                action(path, start.get(), end.get())
                messagebox.showinfo('Export complete', f'Saved to:\n{path}', parent=self)
        def import_file():
            path = filedialog.askopenfilename(parent=self, filetypes=[('CSV files','*.csv')])
            if path and messagebox.askyesno('Import transactions?', 'Append transactions from this CSV?\nAdd any custom categories first. Re-importing creates duplicates.', parent=self):
                count = self.reports.import_csv(path)
                preview()
                messagebox.showinfo('Import complete', f'{count} transactions imported.', parent=self)
        self.button(actions, 'Preview summary', preview)
        self.button(actions, 'Export CSV', lambda: export('csv'))
        self.button(actions, 'Export PDF', lambda: export('pdf'))
        self.button(actions, 'Import CSV', import_file)
        preview()
