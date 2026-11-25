"""Synthetic service-company reporting model. Python standard library only."""
import csv
import sqlite3
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent
SQL = '''
CREATE TABLE dim_date(day TEXT PRIMARY KEY, year INTEGER, month INTEGER);
CREATE TABLE dim_region(region_id INTEGER PRIMARY KEY, region TEXT UNIQUE);
CREATE TABLE dim_service(service_id INTEGER PRIMARY KEY, service TEXT UNIQUE);
CREATE TABLE fact_actual(day TEXT REFERENCES dim_date(day), region_id INTEGER REFERENCES dim_region(region_id), service_id INTEGER REFERENCES dim_service(service_id), amount_cents INTEGER CHECK(amount_cents>=0), PRIMARY KEY(day,region_id,service_id));
CREATE TABLE fact_budget(day TEXT REFERENCES dim_date(day), region_id INTEGER REFERENCES dim_region(region_id), service_id INTEGER REFERENCES dim_service(service_id), amount_cents INTEGER CHECK(amount_cents>=0), PRIMARY KEY(day,region_id,service_id));
CREATE VIEW reporting AS SELECT a.day,a.region_id,a.service_id,a.amount_cents AS actual_cents,b.amount_cents AS budget_cents,a.amount_cents-b.amount_cents AS variance_cents FROM fact_actual a JOIN fact_budget b USING(day,region_id,service_id);
'''

def build():
    db=sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SQL)
    db.executemany('INSERT INTO dim_region VALUES (?,?)',[(1,'North'),(2,'Central'),(3,'South')])
    db.executemany('INSERT INTO dim_service VALUES (?,?)',[(1,'Advisory'),(2,'Implementation'),(3,'Support')])
    start=date(2024,1,1)
    db.executemany('INSERT INTO dim_date VALUES (?,?,?)',[(d.isoformat(),d.year,d.month) for d in (start+timedelta(days=i) for i in range(731))])
    for y in (2024,2025):
        for m in range(1,13):
            for r in range(1,4):
                for s in range(1,4):
                    b=0 if (y,m,r,s)==(2025,1,1,1) else (70000+15000*r+10000*s+2300*m)*(100+y-2024)//100
                    a=b*(90+(m*7+r*3+s*5+y)%31)//100
                    if (y,m,r,s)==(2025,1,1,1): a=45000
                    if (y,m,r,s)==(2025,2,2,2): a=0
                    key=(f'{y}-{m:02d}-01',r,s)
                    db.execute('INSERT INTO fact_actual VALUES (?,?,?,?)',(*key,a))
                    db.execute('INSERT INTO fact_budget VALUES (?,?,?,?)',(*key,b))
    db.commit()
    return db

def verify(db):
    def check(ok, name):
        if not ok: raise AssertionError(name)
        print('PASS',name)
    check(db.execute('PRAGMA foreign_key_check').fetchall()==[], 'foreign keys')
    check(db.execute('SELECT COUNT(*) FROM dim_date').fetchone()[0]==731, 'continuous calendar')
    for table in ('fact_actual','fact_budget'):
        check(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==216, table+' grain and completeness')
    check(db.execute('SELECT COUNT(*) FROM reporting').fetchone()[0]==216, 'one-to-one comparison grain')
    for col,table in [('actual_cents','fact_actual'),('budget_cents','fact_budget')]:
        check(db.execute(f'SELECT SUM({col}) FROM reporting').fetchone()==db.execute(f'SELECT SUM(amount_cents) FROM {table}').fetchone(), col+' reconciliation')
    check(db.execute('SELECT SUM(variance_cents)=SUM(actual_cents)-SUM(budget_cents) FROM reporting').fetchone()[0]==1, 'additive variance')
    check(db.execute('SELECT COUNT(*) FROM reporting WHERE budget_cents=0 AND actual_cents>0').fetchone()[0]==1, 'zero-budget exception')
    check(db.execute('SELECT COUNT(*) FROM reporting WHERE actual_cents=0 AND budget_cents>0').fetchone()[0]==1, 'zero-actual exception')

def export(db):
    out=ROOT/'data';out.mkdir(exist_ok=True)
    for table in ('dim_date','dim_region','dim_service','fact_actual','fact_budget','reporting'):
        cur=db.execute(f'SELECT * FROM {table} ORDER BY 1,2,3' if table not in ('dim_region','dim_service') else f'SELECT * FROM {table} ORDER BY 1')
        with (out/(table+'.csv')).open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow([c[0] for c in cur.description]);w.writerows(cur)
    for year,actual,budget in db.execute('SELECT substr(day,1,4),SUM(actual_cents),SUM(budget_cents) FROM reporting GROUP BY 1'):
        print(year,'actual cents',actual,'budget cents',budget)

if __name__=='__main__':
    with build() as db:
        verify(db);export(db)
