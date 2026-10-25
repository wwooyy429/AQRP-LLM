# AQRP-LLM development and review rules

- Preserve the user's research charter, budget usage and prior data-exposure facts. Engineering fixtures are not economic discoveries or an independent financial test.
- Use the staged acceptance plan in `config/development.json`. Stage completion needs independent review of the exact code version, not just a developer's test result.
- Run `python -B tools/stages.py verify` for offline stage verification. These tests are synthetic and must not contact a market-data provider or submit a cloud backtest.
- Keep one shared calculation library in `cloud/qresearch`, one configuration source in `config`, and one authoritative budget registry. Generated configuration is rebuilt using `python -B tools/research.py build`.
- Before any QuantConnect project operation, list projects and use only returned IDs. Debit real Research executions and backtest submissions before dispatch. Failures do not refund the quota.
- Use fixed programs for audit checks, metric computation and preregistered decisions. LLM proposals cannot issue audit approvals, choose unrestricted fields, change budgets or open final-test dates.
- Real datasets and row-level derived values remain in QuantConnect Cloud. Git contains readable source, configuration, synthetic fixtures and permitted audit metadata only. Never commit credentials or notebook data outputs.
- Do not silently replace missing historical constituents or financial observations. Keep permanent SIDs, actual expected sessions and availability/vintage evidence.
- Do not poll a just-submitted backtest through the chat connector. Record its task identity and wait for the delivered completion. Unknown submissions require reconciliation before retry.
- Do not call the reserved 2024-2026 window untouched: 2024-2025 was previously used. Final evaluation remains disabled until a frozen procedure and a separate executor are ready.
- Reviewers should create independent boundary and known-answer tests, report reproducible failures and distinguish software acceptance from market-data coverage and financial evidence.
