# AQRP-LLM

A staged LLM + QuantConnect factor research platform.

Development follows stages 0-7: contracts, offline calculation, QuantConnect integration, Research evaluation, trading validation, bounded LLM proposals, constrained search, and frozen evaluation/forward monitoring.

This repository starts with engineering infrastructure. It has no validated economic factor, no live trading authorization, and no certified independent final-test result. Research data access is limited to dates before 2024 until a separate frozen executor is configured. The requested 2024-2026 evaluation includes a previously research-exposed 2024-2025 segment.

Source, configuration contracts, synthetic tests, and non-market audit metadata may be versioned here. Licensed market panels and row-level derived values stay in QuantConnect Cloud. Credentials are never committed.

Changes are developed on feature branches and submitted for stage-based review. GPT Work reviews a fixed Git commit with independent tests; its software review is separate from the final financial holdout.
