"""ChatGPT Work独立复现：仅合成数据，无外部API调用。"""

import unittest
import numpy as np
import pandas as pd

from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.audits import audit_formula, make_evidence, COVERAGE_ISSUER
from qresearch.contracts import NY, RECORD_COLUMNS, DataRequest
from qresearch.factors import FactorSpec
from qresearch.labels import (
    LabelProtocol, build_execution_labels, NUMBER_COLUMNS
)
from qresearch.models import ModelSpec
from qresearch.study import StudySpec
from qresearch.runtime import ResearchEngine


def ts(value):
    return pd.Timestamp(value, tz=NY)


def protocol(purpose="engineering_fixture"):
    return LabelProtocol.from_dict({
        "schema_version": 1,
        "protocol_id": "work-cash-roundtrip",
        "target_kind": "net_return",
        "price_basis": "actual_fill",
        "currency": "USD",
        "normalization": "raw",
        "corporate_action_policy": "reject_non_cash_actions",
        "denominator": "entry_notional",
        "purpose": purpose,
    })


def research_study():
    purpose = "research"
    label = protocol(purpose)
    model = ModelSpec.from_dict({
        "schema_version": 1,
        "model_id": "work-ridge",
        "model_family": "ridge",
        "features": ["signal"],
        "target_kind": "net_return",
        "preprocessing": {
            "standardize": True,
            "constant_feature_policy": "unit_scale",
        },
        "hyperparameters": {"alpha": 2.0, "fit_intercept": True},
        "trainable_parameters": [
            "coefficients", "intercept", "feature_mean", "feature_scale"
        ],
        "purpose": purpose,
    })
    acceptance = {
        "logic": "all",
        "metrics": [{
            "name": "mean_ic",
            "operator": "gte",
            "value": 0.1,
            "min_observations": 3,
            "scope": "validation",
        }],
    }
    factor = {
        "schema_version": 1,
        "factor_id": "raw_signal",
        "economic_hypothesis": {
            "mechanism": "Independent synthetic arithmetic only",
            "expected_direction": 1,
            "prediction_horizon_sessions": 1,
            "applicable_regimes": ["synthetic"],
            "failure_conditions": ["bad fixture"],
        },
        "allowed_fields": ["close"],
        "allowed_operators": [
            "lag", "rolling_mean", "rank",
            "safe_divide", "subtract", "multiply"
        ],
        "parameters": {},
        "formula": {
            "op": "lag",
            "arg": {"op": "field", "name": "close"},
            "periods": 1,
        },
        "availability_contract": {"rule": "Known receipt per row"},
        "label_entry_exit_contract": {
            "label_protocol_hash": label.configuration_hash
        },
        "baseline_and_incrementality_test": {
            "rule": "Pinned common population"
        },
        "fixed_model_binding": {
            "model_hash": model.configuration_hash
        },
        "preregistered_acceptance": {
            "acceptance_hash": content_hash(acceptance)
        },
    }
    return StudySpec.from_dict({
        "schema_version": 1,
        "study_id": "independent-work-study",
        "purpose": purpose,
        "synthetic": False,
        "timezone": "America/New_York",
        "research_phase": "factor",
        "factor_specs": [factor],
        "model_spec": model.to_dict(),
        "label_spec": label.to_dict(),
        "feature_bindings": {"signal": "raw_signal"},
        "fixed_model_hash": model.configuration_hash,
        "data_binding": {
            "data_version": "work-synthetic-v1",
            "universe_hash": "b" * 64,
            "code_hash": "c" * 64,
        },
        "development": {
            "start": "2010-01-01",
            "end_exclusive": "2024-01-01",
        },
        "final_evaluation": {"execution_enabled": False},
        "preregistered_acceptance": acceptance,
        "rolling_validation": {
            "first_training_year": 2010,
            "training_years": 8,
            "validation_years": 1,
            "step_years": 1,
            "rounds": 6,
        },
    }, field_catalog=["close"])


class WorkP1Reproductions(unittest.TestCase):
    def test_WR01_unsigned_loss_label(self):
        t = ts("2020-02-03 09:00")
        frame = pd.DataFrame([{
            "trade_id": "one",
            "sid": "A",
            "side": "long",
            "currency": "USD",
            "normalization": "raw",
            "execution_source": "work-independent-synthetic",
            "entry_execution_id": "one-entry",
            "exit_execution_id": "one-exit",
            "non_cash_corporate_action": False,
            "formation_at": t,
            "entry_at": t + pd.Timedelta(hours=1),
            "exit_at": t + pd.Timedelta(days=1),
            "entry_available_at": t + pd.Timedelta(hours=2),
            "exit_available_at": t + pd.Timedelta(days=1, minutes=1),
            "costs_available_at": t + pd.Timedelta(days=1, minutes=2),
            "corporate_actions_available_at":
                t + pd.Timedelta(days=1, minutes=3),
            "entry_quantity": 1,
            "exit_quantity": 1,
            "entry_price": 100,
            "exit_price": 90,
            "entry_fee": 1,
            "exit_fee": 1,
            "other_costs": 0,
            "cash_distributions": 0,
        }])

        frame[list(NUMBER_COLUMNS)] = (
            frame[list(NUMBER_COLUMNS)].astype("uint64")
        )
        result = build_execution_labels(frame, protocol())

        # 正确答案：毛收益-10%，净收益-12%。
        # 原113fdf7实际输出约1.8446744073709552e17。
        np.testing.assert_allclose(
            result[["gross_return", "net_return"]],
            [[-0.10, -0.12]],
            rtol=0,
            atol=1e-14,
        )

    def test_WR02_A_audit_cannot_authorize_B(self):
        # 仅模拟驻留接口；不连接QuantConnect。
        store = MemoryArtifactStore()
        store.residency = "quantconnect_cloud"

        study_a = research_study()
        document = study_a.to_dict()
        binding = document["data_binding"]
        factor_a = study_a.factor_specs[0]

        raw_b = factor_a.to_dict()
        raw_b["formula"] = {
            "op": "multiply",
            "args": [2, {"op": "field", "name": "close"}],
        }
        factor_b = FactorSpec.from_dict(
            raw_b, field_catalog=["close"]
        )
        self.assertNotEqual(
            factor_a.configuration_hash,
            factor_b.configuration_hash,
        )

        # 真正生成、存储并引用A的原始审计报告。
        formula_a = audit_formula(
            store,
            study_a,
            subject_hash=study_a.hash,
            source_hash=binding["code_hash"],
        )
        # 这是覆盖审计的合成契约夹具，不是市场覆盖认证。
        coverage_a = make_evidence(
            store,
            subject_hash=study_a.hash,
            source_hash=binding["code_hash"],
            issuer=COVERAGE_ISSUER,
            checks={
                "historical_universe_coverage": True,
                "actual_availability_verified": True,
                "source_revision_pinned": True,
                "development_only": True,
            },
            scope="research",
        )

        # A的subject和报告不变，仅自由字典改为B的因子哈希。
        approval = {
            "formula_timing_audit_passed": True,
            "coverage_audit_passed": True,
            "fixed_model_hash":
                document["component_hashes"]["model"],
            "label_contract_hash":
                document["component_hashes"]["label"],
            "preregistered_comparison_hash":
                content_hash(document["preregistered_acceptance"]),
            "study_hash": study_a.hash,
            "audit_evidence": {
                "formula_timing": formula_a.to_dict(),
                "data_coverage": coverage_a.to_dict(),
            },
            "factor_hashes": [factor_b.configuration_hash],
            "data_version": binding["data_version"],
            "universe_hash": binding["universe_hash"],
        }

        event = ts("2020-02-03 16:00")
        decision = ts("2020-02-04 09:00")
        rows = pd.DataFrame([[
            "A", "close", event, event, 7.0, "independent"
        ]], columns=RECORD_COLUMNS)

        class StaticCache:
            def __init__(self):
                self.store = store

            def read(self, request, allow_fetch=False):
                return rows.copy()

        engine = ResearchEngine(
            StaticCache(),
            code_version=binding["code_hash"],
            research_approval=approval,
        )
        request = DataRequest(
            "US Equities",
            ("close",),
            ("A",),
            ts("2020-01-01"),
            ts("2021-01-01"),
            binding["data_version"],
            binding["universe_hash"],
        )
        membership = pd.DataFrame(
            [[True]], index=[decision], columns=["A"]
        )

        try:
            result = engine.evaluate(
                [factor_b],
                request,
                [decision],
                ["A"],
                {"close": "exact_session"},
                {decision: event},
                membership=membership,
            )
        except ValueError:
            return

        self.fail(
            "A's unchanged audit authorized B=2*close; "
            f"accepted values={result['values']['data']}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
