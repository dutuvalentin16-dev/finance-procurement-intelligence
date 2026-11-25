"""Offline reference implementation: synthetic subscription sales, SCD2 and run auditing."""
from datetime import date, timedelta
import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, as_of TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(account_id TEXT NOT NULL, region TEXT NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT, PRIMARY KEY(account_id,valid_from), CHECK(valid_to IS NULL OR valid_to>valid_from));
CREATE UNIQUE INDEX IF NOT EXISTS one_current ON accounts(account_id) WHERE valid_to IS NULL;
CREATE TABLE IF NOT EXISTS sales(sale_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, booked_on TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), rep TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(run_id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL, status TEXT NOT NULL, reason TEXT, as_of TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE VIEW IF NOT EXISTS sales_detail AS
SELECT s.sale_id,s.account_id,s.booked_on,s.amount_cents,s.rep,a.region,a.valid_from,
 substr(s.booked_on,1,4)||'-Q'||((CAST(substr(s.booked_on,6,2) AS INTEGER)-1)/3+1) AS quarter
FROM sales s JOIN accounts a ON a.account_id=s.account_id AND a.valid_from<=s.booked_on AND (a.valid_to IS NULL OR s.booked_on<a.valid_to);
CREATE VIEW IF NOT EXISTS qbr AS SELECT quarter,region,COUNT(*) AS bookings,SUM(amount_cents) AS booked_cents FROM sales_detail GROUP BY quarter,region;
CREATE VIEW IF NOT EXISTS compensation AS SELECT quarter,rep,SUM(amount_cents) AS booked_cents,SUM((amount_cents*5+50)/100) AS commission_cents FROM sales_detail GROUP BY quarter,rep;
"""


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def sample_batches():
    # All identifiers, regions and transactions are fabricated; no external data.
    return [
        dict(id='B001', as_of='2025-03-01', accounts=[('A001','North'),('A002','West')], sales=[('S001','A001','2025-03-01',100000,'R001'),('S002','A002','2025-03-01',250000,'R002')]),
        dict(id='B002', as_of='2025-04-01', accounts=[('A001','South')], sales=[('S003','A001','2025-04-01',300000,'R001'),('S004','A002','2025-04-01',150000,'R002')]),
        dict(id='B003', as_of='2025-04-02', accounts=[], sales=[('S005','A001','2025-03-15',50000,'R001')]),
    ]


def reconcile(db):
    raw = db.execute('SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM sales').fetchone()
    detail = db.execute('SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM sales_detail').fetchone()
    qbr = db.execute('SELECT COALESCE(SUM(bookings),0),COALESCE(SUM(booked_cents),0) FROM qbr').fetchone()
    comp = db.execute('SELECT COALESCE(SUM(booked_cents),0) FROM compensation').fetchone()[0]
    if tuple(raw) != tuple(detail) or tuple(raw) != tuple(qbr) or raw[1] != comp:
        raise ValueError('Source-to-mart reconciliation failed')
    return dict(bookings=raw[0], booked_cents=raw[1])


def apply_batch(db, batch):
    """Atomic ordered batches; late sales allowed, late dimension changes rejected."""
    bid, day = batch['id'], batch['as_of']
    payload = json.dumps(batch, sort_keys=True, separators=(',',':'))
    try:
        date.fromisoformat(day)
        with db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT payload FROM batches WHERE id=?',(bid,)).fetchone()
            if old:
                if old[0] != payload:
                    raise ValueError('Batch ID reused with different content')
                status = 'SKIPPED'
            else:
                last = db.execute('SELECT MAX(as_of) FROM batches').fetchone()[0]
                if last and day <= last:
                    raise ValueError('Out-of-order dimension batch')
                seen = set()
                for account, region in batch['accounts']:
                    if not account or not region or account in seen:
                        raise ValueError('Invalid or duplicate account update')
                    seen.add(account)
                    current = db.execute('SELECT region FROM accounts WHERE account_id=? AND valid_to IS NULL',(account,)).fetchone()
                    if current and current[0] == region:
                        continue
                    if current:
                        db.execute('UPDATE accounts SET valid_to=? WHERE account_id=? AND valid_to IS NULL',(day,account))
                    db.execute('INSERT INTO accounts VALUES(?,?,?,NULL)',(account,region,day))
                for sid, account, booked, cents, rep in batch['sales']:
                    date.fromisoformat(booked)
                    if not sid or not rep or booked>day or type(cents) is not int or cents<0:
                        raise ValueError('Invalid booking')
                    db.execute('INSERT INTO sales VALUES(?,?,?,?,?)',(sid,account,booked,cents,rep))
                reconcile(db)
                db.execute('INSERT INTO batches VALUES(?,?,?)',(bid,day,payload))
                status = 'SUCCESS'
            db.execute('INSERT INTO runs(batch_id,status,as_of) VALUES(?,?,?)',(bid,status,day))
        return status
    except (ValueError, sqlite3.Error) as exc:
        # The failed transaction has rolled back; the audit entry is separate.
        with db:
            db.execute('INSERT INTO runs(batch_id,status,reason,as_of) VALUES(?,?,?,?)',(bid,'FAILED',str(exc),day))
        raise


def freshness(db, as_of, max_age_days=1):
    last = db.execute('SELECT MAX(as_of) FROM batches').fetchone()[0]
    return {'last_successful_batch_date':last,'stale':last is None or date.fromisoformat(as_of)-date.fromisoformat(last)>timedelta(days=max_age_days)}


def snapshot(db, as_of):
    return {'synthetic':True,'currency':'fictional EUR','totals':reconcile(db),'freshness':freshness(db,as_of),
            'qbr':[dict(r) for r in db.execute('SELECT * FROM qbr ORDER BY quarter,region')],
            'compensation':[dict(r) for r in db.execute('SELECT * FROM compensation ORDER BY quarter,rep')],
            'runs':[dict(r) for r in db.execute('SELECT batch_id,status,reason,as_of FROM runs ORDER BY run_id')]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='build/demo.sqlite')
    parser.add_argument('--as-of',default='2025-04-04')
    parser.add_argument('--output',default='build/report.json')
    args=parser.parse_args()
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    with connect(args.db) as db:
        batches=sample_batches()
        for batch in batches:
            apply_batch(db,batch)
        apply_batch(db,batches[-1])
        # Deliberately introduce a missing dimension to demonstrate rollback and audit.
        invalid=dict(id='B004',as_of='2025-04-03',accounts=[('A001','East')],sales=[('S006','MISSING','2025-04-03',100,'R003')])
        try:
            apply_batch(db,invalid)
        except ValueError:
            pass
        report=snapshot(db,args.as_of)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
