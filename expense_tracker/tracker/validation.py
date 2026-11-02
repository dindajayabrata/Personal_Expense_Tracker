from datetime import date
from decimal import Decimal, InvalidOperation
import re

PAYMENTS = ('Cash', 'UPI', 'Debit Card', 'Credit Card', 'Bank Transfer', 'Other')


def amount_to_paise(value):
    try:
        number = Decimal(str(value).strip())
        if not number.is_finite() or number <= 0 or number > Decimal('1000000000'):
            raise ValueError('Amount must be greater than zero and at most 1,000,000,000 rupees.')
        if number * 100 != (number * 100).to_integral_value():
            raise ValueError('Use at most two decimal places.')
        return int(number * 100)
    except InvalidOperation:
        raise ValueError('Enter a valid numeric amount.') from None


def valid_date(value):
    value = str(value).strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Date must use YYYY-MM-DD.')
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError('Enter a real calendar date.') from None
    return value


def valid_month(value):
    value = str(value).strip()
    valid_date(value + '-01')
    return value


def date_range(start='', end=''):
    start = valid_date(start) if start else ''
    end = valid_date(end) if end else ''
    if start and end and start > end:
        raise ValueError('Start date must not be after end date.')
    return start, end


def money(paise):
    return f'₹{paise / 100:,.2f}'
