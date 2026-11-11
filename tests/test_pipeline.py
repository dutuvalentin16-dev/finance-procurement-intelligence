import tempfile,unittest
from pathlib import Path
from src.fpi.generate import generate
from src.fpi.pipeline import load,compute,cents
class FinanceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
  generate(cls.path/'raw');cls.con=load(cls.path/'raw',cls.path/'warehouse.sqlite');cls.out=compute(cls.con)
 @classmethod
 def tearDownClass(cls):cls.con.close();cls.tmp.cleanup()
 def test_volume(self):self.assertEqual(self.out['kpis']['invoice_count'],426)
 def test_brands(self):self.assertEqual(len(self.out['brands']),3)
 def test_sources(self):self.assertEqual(set(r['source'] for r in self.out['invoices']),{'CSV','ERP','Spreadsheet'})
 def test_positive_spend(self):self.assertGreater(self.out['kpis']['spend'],0)
 def test_budget(self):self.assertGreater(self.out['kpis']['budget'],self.out['kpis']['spend'])
 def test_quality_alerts(self):self.assertGreaterEqual(self.out['kpis']['alerts'],7)
 def test_missing_po(self):self.assertIn('MISSING_PO',set(r['control_status'] for r in self.out['invoices']))
 def test_over_po(self):self.assertIn('OVER_PO_LIMIT',set(r['control_status'] for r in self.out['invoices']))
 def test_duplicate(self):self.assertIn('DUPLICATE',set(r['control_status'] for r in self.out['invoices']))
 def test_financial_reconciliation(self):self.assertAlmostEqual(sum(x['amount'] for x in self.out['monthly']),self.out['kpis']['spend'],places=2)
 def test_amount_cents(self):self.assertEqual(cents('10.99'),1099)
 def test_db_integrity(self):self.assertEqual(self.con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
 def test_generator_deterministic(self):
  generate(self.path/'raw2')
  self.assertEqual((self.path/'raw2'/'invoices.csv').read_bytes(),(self.path/'raw'/'invoices.csv').read_bytes())
if __name__=='__main__':unittest.main()
