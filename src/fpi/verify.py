"""Reconcile DuckDB/dbt facts and marts with the generated reference snapshot."""
import json
import os
from decimal import Decimal
from pathlib import Path

from .pipeline import ROOT


def verify():
    import duckdb

    snapshot = json.loads((ROOT / 'docs/snapshot.json').read_text())
    html = (ROOT / 'docs/index.html').read_text()
    start = html.index('const DATA = ') + len('const DATA = ')
    embedded, _ = json.JSONDecoder().raw_decode(html[start:])
    if embedded != snapshot:
        raise ValueError('HTML and JSON snapshots differ')
    manifest = json.loads((ROOT / 'analytics/target/manifest.json').read_text())
    results = json.loads((ROOT / 'analytics/target/run_results.json').read_text())['results']
    expected = {k for k, v in manifest['nodes'].items() if v['resource_type'] in ('model', 'test', 'seed')}
    actual = [r['unique_id'] for r in results]
    if set(actual) != expected or len(actual) != len(expected) or any(r['status'] not in ('success', 'pass') for r in results):
        raise ValueError('A complete successful dbt build is required')
    path = os.getenv('FPI_DUCKDB_PATH', str(ROOT / 'data/finance_analytics.duckdb'))
    with duckdb.connect(path, read_only=True) as con:
        facts = con.execute('SELECT invoice_id, amount_eur, control_status FROM main.fct_invoices ORDER BY invoice_id').fetchall()
        expected_facts = sorted((r['invoice_id'], Decimal(str(r['amount'])), r['control_status']) for r in snapshot['invoices'])
        if facts != expected_facts:
            raise ValueError('dbt invoice amounts/control outcomes differ from reference')
        spend = sum((r[1] for r in facts), Decimal('0'))
        for query in ('SELECT SUM(actual_eur) FROM main.fct_budget_actuals',
                      'SELECT SUM(total_spend_eur) FROM main.fct_supplier_spend',
                      'SELECT SUM(affected_spend_eur) FROM main.fct_data_quality'):
            if con.execute(query).fetchone()[0] != spend:
                raise ValueError('dbt mart financial reconciliation failed')
        budget = con.execute('SELECT SUM(budget_eur) FROM main.fct_budget_actuals').fetchone()[0]
        if budget != Decimal(str(snapshot['kpis']['budget'])) or spend != Decimal(str(snapshot['kpis']['spend'])):
            raise ValueError('Snapshot financial KPIs differ from dbt')
        budgets = con.execute('SELECT brand_id, budget_month, category, budget_eur, actual_eur FROM main.fct_budget_actuals ORDER BY 1,2,3').fetchall()
        expected_budgets = sorted((r['brand'],r['period'],r['category'],Decimal(str(r['budget'])),Decimal(str(r['actual']))) for r in snapshot['budget_actuals'])
        if budgets != expected_budgets:
            raise ValueError('Budget-grain values differ between implementations')
        quality = dict(con.execute('SELECT control_status, invoice_count FROM main.fct_data_quality').fetchall())
        if quality != {r['name']: r['count'] for r in snapshot['quality'] if r['count']}:
            raise ValueError('Control counts differ')
        if len(facts) != snapshot['kpis']['invoice_count'] or sum(n for k,n in quality.items() if k != 'PASS') != snapshot['kpis']['alerts']:
            raise ValueError('Volume/quality KPIs differ')
    print(f'Reconciliation passed: {len(facts)} invoices; EUR {spend}; {snapshot["kpis"]["alerts"]} alerts')


if __name__ == '__main__':
    verify()
