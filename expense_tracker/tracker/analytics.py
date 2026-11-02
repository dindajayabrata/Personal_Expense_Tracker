import pandas as pd
from matplotlib.figure import Figure

CHARTS = ('Monthly expenses', 'Expense distribution', 'Income vs expenses',
          'Spending trend', 'Category comparison')


class Analytics:
    def __init__(self, transactions):
        self.transactions = transactions

    def frame(self, start='', end=''):
        columns = ['id', 'type', 'amount_paise', 'category_id', 'date', 'description', 'payment_method', 'category']
        df = pd.DataFrame(self.transactions.list(start=start, end=end), columns=columns)
        df['amount_paise'] = pd.to_numeric(df['amount_paise'])
        df['month'] = df['date'].str.slice(0, 7)
        return df

    def summary(self, start='', end=''):
        df = self.frame(start, end)
        income = int(df.loc[df.type == 'income', 'amount_paise'].sum())
        expense = int(df.loc[df.type == 'expense', 'amount_paise'].sum())
        return {'income': income, 'expense': expense, 'balance': income - expense, 'count': len(df)}

    def monthly(self, df):
        if df.empty:
            return pd.DataFrame(columns=['income', 'expense'])
        table = df.pivot_table(index='month', columns='type', values='amount_paise', aggfunc='sum', fill_value=0)
        months = pd.period_range(df.month.min(), df.month.max(), freq='M').astype(str)
        return table.reindex(index=months, columns=['income', 'expense'], fill_value=0).fillna(0)

    def categories(self, df):
        return df[df.type == 'expense'].groupby('category')['amount_paise'].sum().sort_values(ascending=False)

    def figure(self, chart, start='', end=''):
        if chart not in CHARTS:
            raise ValueError('Choose a chart.')
        df = self.frame(start, end)
        fig = Figure(figsize=(9, 5), dpi=100, layout='constrained')
        ax = fig.add_subplot(111)
        ax.set_title(chart, fontsize=15, pad=18)
        exp = df[df.type == 'expense']
        if df.empty or (chart != 'Income vs expenses' and exp.empty):
            ax.text(.5, .5, 'No matching transactions to chart', ha='center', va='center', transform=ax.transAxes)
            ax.set_axis_off()
            return fig
        monthly = self.monthly(df) / 100
        cats = self.categories(df) / 100
        if chart == 'Expense distribution':
            wedges, _, _ = ax.pie(cats.values, autopct='%1.1f%%', startangle=90)
            ax.legend(wedges, [f'{name}: INR {value:,.2f}' for name, value in cats.items()],
                      loc='center left', bbox_to_anchor=(1, .5), fontsize=8)
        elif chart == 'Category comparison':
            ax.barh(cats.index[::-1], cats.values[::-1], color='#2563eb', label='Expenses')
            ax.set_xlabel('Amount (INR)')
            ax.set_ylabel('Category')
            ax.legend()
        else:
            if chart == 'Monthly expenses':
                ax.bar(monthly.index, monthly.expense, color='#2563eb', label='Expenses')
            elif chart == 'Income vs expenses':
                ax.plot(monthly.index, monthly.income, 'o-', label='Income', color='#059669')
                ax.plot(monthly.index, monthly.expense, 'o-', label='Expenses', color='#e05d44')
            else:
                ax.plot(monthly.index, monthly.expense, 'o-', label='Expenses', color='#2563eb')
            ax.set_xlabel('Month')
            ax.set_ylabel('Amount (INR)')
            ax.tick_params(axis='x', rotation=35)
            ax.legend()
            ax.grid(axis='y', alpha=.2)
        return fig
