"""Dagster assets for source generation, SQLite loading and snapshot validation."""
from pathlib import Path
import sqlite3
from dagster import Definitions, asset, AssetExecutionContext, materialize
from src.fpi.pipeline import ROOT, prepare_sources, load, compute, render

@asset(description='Generate and copy deterministic CSV sources for dbt.')
def procurement_sources(context: AssetExecutionContext) -> str:
    base = prepare_sources()
    context.log.info('Generated synthetic procurement sources: %s', base)
    return str(base)

@asset(description='Load relational warehouse with a transaction and foreign-key checks.')
def procurement_warehouse(context: AssetExecutionContext, procurement_sources: str) -> str:
    db=ROOT/'data'/'warehouse.sqlite'
    con=load(Path(procurement_sources),db)
    con.close()
    context.log.info('Loaded warehouse: %s',db)
    return str(db)

@asset(description='Reconcile invoices to budget actuals and publish static UI snapshot.')
def finance_dashboard_snapshot(context: AssetExecutionContext, procurement_warehouse: str) -> str:
    con=sqlite3.connect(procurement_warehouse)
    try: output=compute(con)
    finally: con.close()
    render(output,ROOT/'docs')
    context.log.info('Published %d invoices',output['kpis']['invoice_count'])
    return str(ROOT/'docs'/'index.html')

defs=Definitions(assets=[procurement_sources,procurement_warehouse,finance_dashboard_snapshot])


if __name__ == '__main__':
    result = materialize([procurement_sources, procurement_warehouse, finance_dashboard_snapshot])
    if not result.success:
        raise SystemExit('Dagster materialization failed')
