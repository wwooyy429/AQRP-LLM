"""Synthetic registered-study integration; no market data or profitability claim."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.contracts import NY
from qresearch.labels import LabelProtocol, LabelValidationError, build_execution_labels
from qresearch.models import ModelSpec, restore_model
from qresearch.pipeline import PipelineValidationError, evaluate_registered_study
from qresearch.study import StudySpec
from qresearch.evaluation import walk_forward_evaluate, six_rolling_folds
from test_study import fixture_study, fixture_trading


def stamp(text):
    return pd.Timestamp(text, tz=NY)


def complete_study(*, target_kind="net_return", purpose="engineering_fixture"):
    raw = fixture_study(purpose)
    raw["study_id"] = "synthetic-six-fold-execution-pipeline"
    raw["development"] = {"start": "2010-01-01", "end_exclusive": "2024-01-01"}
    raw["model_spec"]["target_kind"] = target_kind
    raw["label_spec"]["target_kind"] = target_kind
    raw["fixed_model_hash"] = ModelSpec.from_dict(raw["model_spec"]).configuration_hash
    if purpose == "research":
        raw["trading_spec"] = fixture_trading()
        raw["factor_specs"][0]["fixed_model_binding"] = {"model_hash": raw["fixed_model_hash"]}
        raw["factor_specs"][0]["label_entry_exit_contract"] = {
            "label_protocol_hash": LabelProtocol.from_dict(raw["label_spec"]).configuration_hash}
    return StudySpec.from_dict(raw, field_catalog=["close"])


def roundtrip_rows():
    features, trades = [], []
    for year in range(2010, 2024):
        for name, score, exit_price, fee in (("A", 1., 100., 0.), ("B", 2., 110., 20.), ("C", 3., 120., 40.)):
            formation = stamp(f"{year}-06-01 09:00")
            features.append({"sid": "SID-" + name, "formation_at": formation, "fixture_factor": score})
            identity = str(year) + "-" + name
            trades.append({"trade_id": identity, "sid": "SID-" + name, "side": "long", "currency": "USD", "normalization": "raw",
                 "execution_source": "synthetic-fixture", "entry_execution_id": identity + "-buy", "exit_execution_id": identity + "-sell",
                 "non_cash_corporate_action": False, "formation_at": formation,
                 "entry_at": stamp(f"{year}-06-01 10:00"), "exit_at": stamp(f"{year}-06-02 10:00"),
                 "entry_available_at": stamp(f"{year}-06-01 10:01"), "exit_available_at": stamp(f"{year}-06-02 10:01"),
                 "costs_available_at": stamp(f"{year}-06-02 11:00"), "corporate_actions_available_at": stamp(f"{year}-06-02 10:30"),
                 "entry_quantity": 1., "exit_quantity": 1., "entry_price": 100., "exit_price": exit_price,
                 "entry_fee": fee / 2, "exit_fee": fee / 2, "other_costs": 0., "cash_distributions": 0.})
    return pd.DataFrame(features), pd.DataFrame(trades)


def registered_package(study, store):
    document = study.to_dict()
    binding, parts = document["data_binding"], document["component_hashes"]
    identity = {"code_hash": binding["code_hash"], "data_hash": content_hash(binding),
                "universe_hash": binding["universe_hash"], "label_hash": parts["label"],
                "factor_set_hash": content_hash(parts["factors"]), "model_hash": parts["model"],
                "trading_hash": parts["trading"], "data_end_exclusive": stamp("2024-01-01").isoformat()}
    package = {"workflow_schema_version": 1, "study": document, "identity": identity, "campaign_hash": "a" * 64}
    store.write_once("configurations/" + content_hash(package) + ".json", canonical_json(package))
    return package


class PipelineTests(unittest.TestCase):
    def test_six_fold_net_target_binding_and_restorable_artifacts(self):
        study, store = complete_study(), MemoryArtifactStore()
        features, trades = roundtrip_rows()
        result = evaluate_registered_study(study, features, trades, audit_store=store)
        self.assertEqual(len(result.folds), 6)
        self.assertEqual(len(result.model_artifacts), 6)
        self.assertEqual(len(result.artifact_keys), 6)
        self.assertEqual(result.target_kind, "net_return")
        self.assertEqual(result.feature_bindings, {"candidate_score": "fixture_factor"})
        # Gross ranks rise with score, but supplied explicit execution costs
        # make net returns (0,-.1,-.2): six daily RankIC values must equal -1.
        np.testing.assert_allclose(result.daily_ic.ic, [-1.] * 6, atol=1e-14)
        self.assertEqual(result.daily_ic.n.tolist(), [3] * 6)
        np.testing.assert_allclose(result.predictions.prediction, [1., 2., 3.] * 6)
        np.testing.assert_allclose(result.predictions.label, [0., -.1, -.2] * 6)
        self.assertTrue(result.predictions.target_kind.eq("net_return").all())
        for index, artifact in enumerate(result.model_artifacts):
            self.assertEqual(artifact["train_start"], stamp(f"{2010 + index}-01-01").isoformat())
            self.assertEqual(artifact["fit_cutoff"], stamp(f"{2018 + index}-01-01").isoformat())
            self.assertEqual(artifact["training_rows"], 24)
            self.assertTrue(store.exists(result.artifact_keys[index]))
            restored = restore_model(artifact)
            np.testing.assert_array_equal(restored.predict(pd.DataFrame({"candidate_score": [1., 2., 3.]})), [1., 2., 3.])

    def test_gross_target_is_not_silently_replaced_with_net_or_generic_label(self):
        features, trades = roundtrip_rows()
        result = evaluate_registered_study(complete_study(target_kind="gross_return"), features, trades)
        np.testing.assert_allclose(result.daily_ic.ic, [1.] * 6, atol=1e-14)
        np.testing.assert_allclose(result.predictions.label, [0., .1, .2] * 6)
        self.assertEqual(result.target_kind, "gross_return")

    def test_delayed_entry_receipt_is_purged_from_exact_training_fold(self):
        features, trades = roundtrip_rows()
        row = trades.iloc[0].copy()
        row["trade_id"], row["sid"] = "boundary", "SID-BOUNDARY"
        row["entry_execution_id"], row["exit_execution_id"] = "boundary-buy", "boundary-sell"
        for name, time in {"formation_at": "2017-12-28 09:00", "entry_at": "2017-12-28 10:00",
                           "exit_at": "2017-12-29 10:00", "entry_available_at": "2018-01-05 09:00",
                           "exit_available_at": "2017-12-29 10:01", "costs_available_at": "2017-12-29 11:00",
                           "corporate_actions_available_at": "2017-12-29 11:00"}.items():
            row[name] = stamp(time)
        trades = pd.concat([trades, row.to_frame().T], ignore_index=True)
        features = pd.concat([features, pd.DataFrame([{"sid": row.sid, "formation_at": row.formation_at, "fixture_factor": 1000.}])], ignore_index=True)
        result = evaluate_registered_study(complete_study(), features, trades)
        self.assertEqual(result.folds.purged_train_n.iloc[0], 1)
        self.assertEqual(result.model_artifacts[0]["training_rows"], 24)
        self.assertEqual(result.model_artifacts[1]["training_rows"], 25)

    def test_extra_metadata_labels_duplicate_or_unmatched_population_rejected(self):
        study = complete_study()
        features, trades = roundtrip_rows()
        for column in ("label", "net_return", "entry_at", "candidate_score", "other_factor"):
            with self.subTest(column=column), self.assertRaises(PipelineValidationError):
                evaluate_registered_study(study, features.assign(**{column: 1.}), trades)
        for bad_features, bad_trades in ((features.iloc[1:], trades), (features, trades.iloc[1:]),
                                        (pd.concat([features, features.iloc[[0]]]), trades)):
            with self.assertRaises(PipelineValidationError):
                evaluate_registered_study(study, bad_features, bad_trades)

    def test_generated_label_protocol_and_target_are_checked_per_row(self):
        study = complete_study()
        features, trades = roundtrip_rows()
        labels = build_execution_labels(trades, LabelProtocol.from_dict(study.to_dict()["label_spec"]))
        for column, value in (("target_kind", "gross_return"), ("label_protocol_hash", "0" * 64)):
            corrupt = labels.copy()
            corrupt.loc[0, column] = value
            with patch("qresearch.pipeline.build_execution_labels", return_value=corrupt), self.assertRaises(PipelineValidationError):
                evaluate_registered_study(study, features, trades)

    def test_registered_configuration_hash_bindings_are_required_and_checked(self):
        study, store = complete_study(), MemoryArtifactStore()
        features, trades = roundtrip_rows()
        package = registered_package(study, store)
        result = evaluate_registered_study(study, features, trades, audit_store=store, registered_configuration=package)
        self.assertEqual(result.configuration_hash, content_hash(package))
        for alteration in ("study", "model_hash", "data_hash", "label_hash", "factor_set_hash"):
            broken = deepcopy(package)
            if alteration == "study":
                broken["study"]["study_id"] = "different-study"
            else:
                broken["identity"][alteration] = "0" * 64
            with self.subTest(alteration=alteration), self.assertRaises(PipelineValidationError):
                evaluate_registered_study(study, features, trades, audit_store=store, registered_configuration=broken)
        with self.assertRaises(PipelineValidationError):
            evaluate_registered_study(study, features, trades, audit_store=MemoryArtifactStore(), registered_configuration=package)

    def test_market_pipeline_cannot_use_fixture_approval_or_unregistered_data(self):
        study, store = complete_study(purpose="research"), MemoryArtifactStore()
        features, trades = roundtrip_rows()
        with self.assertRaises(PipelineValidationError):
            evaluate_registered_study(study, features, trades)
        package = registered_package(study, store)
        with self.assertRaisesRegex(PipelineValidationError, "cloud"):
            evaluate_registered_study(study, features, trades, audit_store=store, registered_configuration=package,
                                      audit_evidence={"formula_timing": True, "data_coverage": True})
        store.residency = "quantconnect_cloud"  # Synthetic SDK boundary fixture, not a real cloud store.
        with self.assertRaises(ValueError):
            evaluate_registered_study(study, features, trades, audit_store=store, registered_configuration=package,
                                      audit_evidence={"formula_timing": True, "data_coverage": True})

    def test_existing_evaluator_without_callback_keeps_empty_artifact_tuple(self):
        study = complete_study()
        features, trades = roundtrip_rows()
        labels = build_execution_labels(trades, LabelProtocol.from_dict(study.to_dict()["label_spec"]))
        rows = features.rename(columns={"fixture_factor": "candidate_score"}).merge(labels, on=["sid", "formation_at"])
        class Fixed:
            def fit(self, X, y):
                return self
            def predict(self, X):
                return X.candidate_score.to_numpy()
        old = walk_forward_evaluate(rows, ["candidate_score"], "net_return", Fixed)
        self.assertEqual(old.model_artifacts, ())


if __name__ == "__main__":
    unittest.main()
