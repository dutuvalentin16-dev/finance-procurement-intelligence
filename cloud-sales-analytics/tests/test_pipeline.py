import sqlite3
import unittest
from pipeline import connect, sample_batches, apply_batch, reconcile, freshness, snapshot

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:')
        self.batches=sample_batches()
        for batch in self.batches:
            apply_batch(self.db,batch)

    def tearDown(self):
        self.db.close()

    def test_reconciliation(self):
        self.assertEqual(reconcile(self.db),{'bookings':5,'booked_cents':850000})
        self.assertEqual(sum(r[0] for r in self.db.execute('SELECT commission_cents FROM compensation')),42500)

    def test_historical_region_including_late_sale(self):
        regions=dict(self.db.execute('SELECT sale_id,region FROM sales_detail'))
        self.assertEqual(regions,{'S001':'North','S002':'West','S003':'South','S004':'West','S005':'North'})
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT region,valid_from,valid_to FROM accounts WHERE account_id='A001' ORDER BY valid_from")],[('North','2025-03-01','2025-04-01'),('South','2025-04-01',None)])

    def test_replay(self):
        self.assertEqual(apply_batch(self.db,self.batches[-1]),'SKIPPED')
        self.assertEqual(reconcile(self.db)['bookings'],5)

    def test_changed_replay(self):
        with self.assertRaises(ValueError):
            apply_batch(self.db,dict(self.batches[-1],sales=[]))

    def test_missing_dimension_rollback_and_audit(self):
        with self.assertRaises(ValueError):
            apply_batch(self.db,dict(id='FAIL',as_of='2025-04-03',accounts=[('A001','East')],sales=[('S006','MISSING','2025-04-03',100,'R003')]))
        self.assertEqual(reconcile(self.db)['bookings'],5)
        self.assertEqual(self.db.execute("SELECT region FROM accounts WHERE account_id='A001' AND valid_to IS NULL").fetchone()[0],'South')
        self.assertEqual(self.db.execute('SELECT status FROM runs ORDER BY run_id DESC LIMIT 1').fetchone()[0],'FAILED')

    def test_duplicate_sale_rollback(self):
        with self.assertRaises(sqlite3.IntegrityError):
            apply_batch(self.db,dict(id='DUP',as_of='2025-04-03',accounts=[],sales=[('S001','A001','2025-04-03',100,'R001')]))
        self.assertEqual(reconcile(self.db)['bookings'],5)

    def test_out_of_order(self):
        with self.assertRaises(ValueError):
            apply_batch(self.db,dict(id='LATE',as_of='2025-03-20',accounts=[],sales=[]))

    def test_freshness(self):
        self.assertFalse(freshness(self.db,'2025-04-03')['stale'])
        self.assertTrue(freshness(self.db,'2025-04-04')['stale'])

    def test_snapshot(self):
        report=snapshot(self.db,'2025-04-04')
        self.assertTrue(report['synthetic'])
        self.assertEqual(len(report['qbr']),4)

if __name__=='__main__':
    unittest.main()
