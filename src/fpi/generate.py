"""Deterministic synthetic procurement data. All brands, suppliers and transactions are fictional."""
import csv, random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
BRANDS=[('NOVA','Nova Travel'),('ATLAS','Atlas Stay'),('ORBIT','Orbit Labs')]
CATEGORIES=['Cloud','Software','Marketing','Facilities','Consulting','Operations']
FX={'EUR':1.,'USD':.91,'GBP':1.17,'RON':.20}
NAMES=['Apex Cloud','Mosaic Software','Bluebird Media','Northstar Digital','Delta Consulting','Vantage Facilities','Summit Infrastructure','Arcstone Partners','Pioneer Analytics','Fieldstone Tech','Cobalt Solutions','Vertex Creative','Nimble Networks','Lumen Services','Cedar Operations','Luminary Labs','Orion Systems','Clearpath Agency','Beacon Data','Horizon Works','Amberline IT','Stratus Platforms','Evergreen Media','Terra Advisory','Signal Studio','Waypoint Cloud','Meridian Supply','Highline Partners','Prism Digital','Drift Technologies','Solace Software','Acorn Systems','Cloudrise Inc','Fjord Labs','Papertrail Office','Brightpath Consulting','Sable Services','Redwood Security']
def save(path, rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def generate(base,seed=26,count=426):
 rng=random.Random(seed); base=Path(base)
 suppliers=[dict(supplier_id=f'SUP-{i:03}',supplier_name=name,category=CATEGORIES[(i-1)%6],country=['RO','DE','NL','UK','US'][(i-1)%5]) for i,name in enumerate(NAMES,1)]
 invoices=[];pos=[]
 for i in range(1,count+1):
  s=rng.choice(suppliers);brand=rng.choice(BRANDS)[0];d=date(2026,1,1)+timedelta(days=rng.randrange(1,315))
  cur=rng.choices(list(FX),weights=[62,21,11,6])[0];amt=Decimal(rng.randrange(85000,1450000))/100
  po_amount=amt+Decimal(rng.randrange(-12000,17500))/100;po=f'PO-{i:05d}'
  if i in (31,133,251,409):po=''
  if i in (74,168,309):po_amount=amt*Decimal('.70')
  if po:pos.append(dict(po_id=po,supplier_id=s['supplier_id'],brand_id=brand,currency=cur,po_amount=f'{po_amount:.2f}',created_at=str(d-timedelta(days=8))))
  invoices.append(dict(invoice_id=f'INV-{i:05d}',supplier_id=s['supplier_id'],brand_id=brand,po_id=po,currency=cur,amount=f'{amt:.2f}',invoice_date=str(d),status=rng.choices(['PAID','APPROVED','PENDING'],[48,34,18])[0],source=['ERP','CSV','Spreadsheet'][i%3]))
 # A duplicate business event with a distinct source row ID.
 a=invoices[382];b=invoices[381]
 for key in ('supplier_id','brand_id','po_id','currency','amount','invoice_date'):a[key]=b[key]
 budgets=[dict(brand_id=brand,month=f'2026-{m:02d}',category=cat,budget_eur=f'{Decimal(rng.randrange(40000,78000)):.2f}') for brand,_ in BRANDS for m in range(1,13) for cat in CATEGORIES]
 result=dict(suppliers=suppliers,purchase_orders=pos,invoices=invoices,budgets=budgets)
 for name,rows in result.items():save(base/f'{name}.csv',rows)
 return result
if __name__=='__main__': generate(Path('data/raw'))
