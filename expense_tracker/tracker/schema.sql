PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS categories (
 id INTEGER PRIMARY KEY,
 name TEXT NOT NULL COLLATE NOCASE CHECK(length(trim(name)) BETWEEN 1 AND 60),
 type TEXT NOT NULL CHECK(type IN ('income','expense')),
 UNIQUE(name,type), UNIQUE(id,type)
);
CREATE TABLE IF NOT EXISTS transactions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 type TEXT NOT NULL CHECK(type IN ('income','expense')),
 amount_paise INTEGER NOT NULL CHECK(typeof(amount_paise)='integer' AND amount_paise>0 AND amount_paise<=100000000000),
 category_id INTEGER NOT NULL,
 date TEXT NOT NULL CHECK(length(date)=10 AND date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
 description TEXT NOT NULL CHECK(length(trim(description)) BETWEEN 1 AND 500),
 payment_method TEXT NOT NULL CHECK(payment_method IN ('Cash','UPI','Debit Card','Credit Card','Bank Transfer','Other')),
 FOREIGN KEY(category_id,type) REFERENCES categories(id,type) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS budgets (
 id INTEGER PRIMARY KEY,
 month TEXT NOT NULL CHECK(length(month)=7 AND month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
 category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
 amount_paise INTEGER NOT NULL CHECK(typeof(amount_paise)='integer' AND amount_paise>0 AND amount_paise<=100000000000)
);
CREATE UNIQUE INDEX IF NOT EXISTS budget_scope ON budgets(month,COALESCE(category_id,0));
CREATE INDEX IF NOT EXISTS transaction_date ON transactions(date);
CREATE TRIGGER IF NOT EXISTS budget_expense_insert BEFORE INSERT ON budgets
WHEN NEW.category_id IS NOT NULL AND (SELECT type FROM categories WHERE id=NEW.category_id)!='expense'
BEGIN SELECT RAISE(ABORT,'Budgets require an expense category'); END;
CREATE TRIGGER IF NOT EXISTS budget_expense_update BEFORE UPDATE ON budgets
WHEN NEW.category_id IS NOT NULL AND (SELECT type FROM categories WHERE id=NEW.category_id)!='expense'
BEGIN SELECT RAISE(ABORT,'Budgets require an expense category'); END;
