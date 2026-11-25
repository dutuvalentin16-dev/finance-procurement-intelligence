# Cloud design and incident runbook

Proposed architecture, not provisioned: ADF schedule -> ADLS Gen2 immutable synthetic batch files -> Databricks job (bronze/silver/gold Delta tables) -> reporting consumer. Use a dedicated sandbox resource group, managed identity, Key Vault references only if necessary, least-privilege permissions and a budget alert. No secrets belong in Git.

## Deployment acceptance criteria

- Bronze: preserve batch identity and payload hash, store source arrival time and schema; reject duplicate IDs with changed payload.
- Silver: Delta SCD2 account history with nonoverlapping half-open date intervals; immutable sales keyed by sale ID; late facts matched to the historically valid dimension.
- Gold: quarter/region bookings and quarter/rep compensation. Publish a consistent snapshot only after both marts reconcile to source facts; failed partial writes must not become visible to consumers. Delta transactions are table-scoped: use versioned staging outputs plus a manifest/publish pointer, not an assumed cross-table transaction.
- ADF dependencies: trigger ingestion, wait for Databricks success, run quality gate, then publish. Retry transient errors only; invalid data goes to quarantine. Set concurrency to one for this ordered-batch design.
- Persist batch status, timestamps, row counts and quality outcomes. Alert on failed jobs and stale source arrival separately. Configure log destinations in the deployment environment, not this repository.
- Query performance: compare execution plans, data skipping and partition strategy on a realistically sized synthetic dataset before choosing optimizations; the five-row local fixture is not a benchmark.

## Incident exercise

1. Run `python pipeline.py` locally; observe B004 failure, rollback, and stale data status.
2. Inspect the run audit and trace missing account reference to source input. Confirm the previous account version and the accepted five bookings remain intact.
3. Correct the synthetic source batch, rerun with its original unaccepted ID, reconcile and verify the freshness state. Never change an already accepted batch payload.
4. Record cause, affected report period, resolution and preventative test. In cloud, inspect ADF activity output and Databricks job logs; release only after validation.

## Limitations

Local persistence uses SQLite, not Delta. The Spark reference is an unexecuted full rebuild, not the operational pipeline. ADF, cloud credentials, alerts, infrastructure and performance benchmarks are future acceptance items, not delivered cloud capabilities. No real data or external accounts are required to explore the local lab.
