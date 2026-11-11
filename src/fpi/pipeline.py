"""CSV -> transactional SQLite warehouse -> reconciled, static dashboard snapshot."""
import csv,json,sqlite3,shutil
from collections import defaultdict
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from .generate import generate,BRANDS,FX
ROOT=Path(__file__).resolve().parents[2]
SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE brands(id TEXT PRIMARY KEY,name TEXT NOT NULL);
CREATE TABLE suppliers(id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,country TEXT);
CREATE TABLE purchase_orders(id TEXT PRIMARY KEY,supplier_id TEXT REFERENCES suppliers(id),brand_id TEXT REFERENCES brands(id),currency TEXT,amount_cents INTEGER,created_at TEXT);
CREATE TABLE invoices(id TEXT PRIMARY KEY,supplier_id TEXT NOT NULL REFERENCES suppliers(id),brand_id TEXT NOT NULL REFERENCES brands(id),po_id TEXT,currency TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0),invoice_date TEXT NOT NULL,status TEXT NOT NULL,source TEXT);
CREATE TABLE budgets(brand_id TEXT REFERENCES brands(id),month TEXT,category TEXT,amount_cents INTEGER,PRIMARY KEY(brand_id,month,category));
CREATE TABLE fx(currency TEXT PRIMARY KEY,rate REAL NOT NULL);
CREATE VIEW fct_invoices AS SELECT i.*,s.name supplier_name,s.category,b.name brand_name,
CAST(ROUND(i.amount_cents*fx.rate) AS INTEGER) eur_cents,
CASE WHEN i.po_id IS NULL OR p.id IS NULL THEN 'MISSING_PO'
 WHEN p.supplier_id<>i.supplier_id OR p.brand_id<>i.brand_id THEN 'PO_MISMATCH'
 WHEN i.amount_cents>p.amount_cents*1.10 THEN 'OVER_PO_LIMIT' ELSE 'PASS' END control_status
FROM invoices i JOIN suppliers s ON s.id=i.supplier_id JOIN brands b ON b.id=i.brand_id JOIN fx ON fx.currency=i.currency LEFT JOIN purchase_orders p ON i.po_id=p.id;
CREATE VIEW fct_budget_actuals AS SELECT b.brand_id,b.month,b.category,b.amount_cents budget_cents,COALESCE(SUM(f.eur_cents),0) actual_cents
FROM budgets b LEFT JOIN fct_invoices f ON f.brand_id=b.brand_id AND substr(f.invoice_date,1,7)=b.month AND f.category=b.category
GROUP BY b.brand_id,b.month,b.category,b.amount_cents;
'''
def csvrows(path):
 with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def cents(v):return int((Decimal(str(v))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def load(base,dbfile):
 dbfile.parent.mkdir(parents=True,exist_ok=True)
 if dbfile.exists():dbfile.unlink()
 con=sqlite3.connect(dbfile);con.executescript(SCHEMA)
 with con:
  con.executemany('INSERT INTO brands VALUES (?,?)',BRANDS)
  con.executemany('INSERT INTO fx VALUES (?,?)',FX.items())
  con.executemany('INSERT INTO suppliers VALUES (?,?,?,?)',[(r['supplier_id'],r['supplier_name'],r['category'],r['country']) for r in csvrows(base/'suppliers.csv')])
  con.executemany('INSERT INTO purchase_orders VALUES (?,?,?,?,?,?)',[(r['po_id'],r['supplier_id'],r['brand_id'],r['currency'],cents(r['po_amount']),r['created_at']) for r in csvrows(base/'purchase_orders.csv')])
  con.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?)',[(r['invoice_id'],r['supplier_id'],r['brand_id'],r['po_id'] or None,r['currency'],cents(r['amount']),r['invoice_date'],r['status'],r['source']) for r in csvrows(base/'invoices.csv')])
  con.executemany('INSERT INTO budgets VALUES (?,?,?,?)',[(r['brand_id'],r['month'],r['category'],cents(r['budget_eur'])) for r in csvrows(base/'budgets.csv')])
 assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 return con
def compute(con):
 con.row_factory=sqlite3.Row
 rows=[dict(r) for r in con.execute('SELECT * FROM fct_invoices ORDER BY invoice_date DESC,id DESC')]
 # duplicate business event: supplier+PO+date+amount
 seen=set()
 for r in reversed(rows):
  k=(r['supplier_id'],r['po_id'],r['invoice_date'],r['amount_cents'])
  if k in seen and r['po_id']:r['control_status']='DUPLICATE'
  seen.add(k)
 budgets=[dict(r) for r in con.execute('SELECT * FROM fct_budget_actuals ORDER BY month,brand_id,category')]
 spend=sum(r['eur_cents'] for r in rows);budget_actual=sum(r['actual_cents'] for r in budgets)
 assert spend==budget_actual, 'Financial reconciliation failed: invoice spend != modeled actuals'
 monthly=defaultdict(int);brands=defaultdict(int);categories=defaultdict(int)
 for r in rows:
  r['invoice_id']=r.pop('id')
  monthly[r['invoice_date'][:7]]+=r['eur_cents'];brands[r['brand_name']]+=r['eur_cents'];categories[r['category']]+=r['eur_cents']
  r['amount']=round(r['eur_cents']/100,2)
  for k in ('amount_cents','eur_cents'):del r[k]
 totalbudget=sum(r['budget_cents'] for r in budgets)
 return {'meta':{'type':'SYNTHETIC DATA','note':'All vendors, brands and transactions are fictional. Fixed illustrative FX rates; not live quotes.','currency':'EUR'},
         'kpis':{'spend':spend/100,'budget':totalbudget/100,'utilization':round(spend/totalbudget*100,1),'invoice_count':len(rows),'alerts':sum(r['control_status']!='PASS' for r in rows),'paid':sum(r['status']=='PAID' for r in rows)},
         'monthly':[{'period':k,'amount':v/100} for k,v in sorted(monthly.items())],
         'brands':[{'name':k,'amount':v/100} for k,v in sorted(brands.items(),key=lambda x:-x[1])],
         'categories':[{'name':k,'amount':v/100} for k,v in sorted(categories.items(),key=lambda x:-x[1])],
         'invoices':rows,
         'quality':[{'name':k,'count':sum(r['control_status']==k for r in rows)} for k in ('PASS','MISSING_PO','PO_MISMATCH','OVER_PO_LIMIT','DUPLICATE')],
         'budget_actuals':[{'brand':r['brand_id'],'period':r['month'],'category':r['category'],'budget':r['budget_cents']/100,'actual':r['actual_cents']/100} for r in budgets]}
def render(snapshot,output):
 output.mkdir(parents=True,exist_ok=True)
 (output/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
 template=(ROOT/'web'/'index.template.html').read_text(encoding='utf-8')
 (output/'index.html').write_text(template.replace('/*__DATA_PAYLOAD__*/','const DATA = '+json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))+';'),encoding='utf-8')
def prepare_sources():
 base=ROOT/'data'/'raw';generate(base)
 seed=ROOT/'analytics'/'seeds';seed.mkdir(parents=True,exist_ok=True)
 for name in ('suppliers','purchase_orders','invoices','budgets'):
  shutil.copyfile(base/f'{name}.csv',seed/f'{name}.csv')
 return base
def run():
 base=prepare_sources()
 con=load(base,ROOT/'data'/'warehouse.sqlite')
 try:data=compute(con)
 finally:con.close()
 render(data,ROOT/'docs')
 print('OK | invoices:',data['kpis']['invoice_count'],'| quality alerts:',data['kpis']['alerts'],'| spend EUR:',f"{data['kpis']['spend']:,.2f}")
 return data
if __name__=='__main__':run()
