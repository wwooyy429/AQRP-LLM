"""Independent arithmetic fixtures; no market data or active trading strategy."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.contracts import NY, digest
from qresearch.labels import LabelProtocol, LabelValidationError, build_execution_labels
from qresearch.models import ModelSpec, ModelValidationError, create_model, restore_model


def stamp(text):
    return pd.Timestamp(text, tz=NY)


def label_spec(target="net_return", **changes):
    spec = {"schema_version": 1, "protocol_id": "synthetic-roundtrip-v1", "target_kind": target,
            "price_basis": "actual_fill", "currency": "USD", "normalization": "raw",
            "corporate_action_policy": "reject_non_cash_actions", "denominator": "entry_notional",
            "purpose": "engineering_fixture"}
    spec.update(changes)
    return spec


def executions():
    # Three hand answers on entry notional: +10%-2%=8%; -10%-2%=-12%;
    # no price change +3%cash distribution -1%fees =2%net.
    rows = []
    for name, entry, exit_price, quantity, entry_fee, exit_fee, cash in (
            ("A", 100., 110., 10., 10., 10., 0.),
            ("B", 50., 45., 20., 5., 15., 0.),
            ("C", 20., 20., 5., .5, .5, 3.)):
        rows.append({"trade_id": name, "sid": "SID-" + name, "side": "long", "currency": "USD", "normalization": "raw",
                     "execution_source": "synthetic-fixture", "entry_execution_id": name + "-buy", "exit_execution_id": name + "-sell",
                     "non_cash_corporate_action": False, "formation_at": stamp("2018-01-02 09:00"),
                     "entry_at": stamp("2018-01-02 10:00"), "exit_at": stamp("2018-01-03 10:00"),
                     "entry_available_at": stamp("2018-01-02 10:01"), "exit_available_at": stamp("2018-01-03 10:01"),
                     "costs_available_at": stamp("2018-01-03 11:00"), "corporate_actions_available_at": stamp("2018-01-03 10:30"),
                     "entry_quantity": quantity, "exit_quantity": quantity, "entry_price": entry, "exit_price": exit_price,
                     "entry_fee": entry_fee, "exit_fee": exit_fee, "other_costs": 0., "cash_distributions": cash})
    return pd.DataFrame(rows)


def model_spec(family="identity", standardize=False, **changes):
    spec = {"schema_version": 1, "model_id": "synthetic-" + family, "model_family": family,
            "features": ["factor_a"], "target_kind": "net_return", "purpose": "engineering_fixture",
            "preprocessing": {"standardize": standardize, "constant_feature_policy": "unit_scale"},
            "hyperparameters": {"coefficient": 1.} if family == "identity" else {"alpha": 1., "fit_intercept": True},
            "trainable_parameters": [] if family == "identity" else ["coefficients", "intercept"] +
                                     (["feature_mean", "feature_scale"] if standardize else [])}
    spec.update(changes)
    return spec


def metadata(years):
    rows = []
    for i, year in enumerate(years):
        rows.append({"sid": "SID-" + str(i), "formation_at": stamp(f"{year}-06-01 09:00"),
                     "entry_at": stamp(f"{year}-06-01 10:00"), "exit_at": stamp(f"{year}-06-02 10:00"),
                     "label_available_at": stamp(f"{year}-06-02 11:00")})
    return pd.DataFrame(rows)


class LabelTests(unittest.TestCase):
    def test_three_hand_computed_roundtrip_answers_and_maturity(self):
        result = build_execution_labels(executions(), LabelProtocol.from_dict(label_spec()))
        np.testing.assert_allclose(result.gross_return, [.10, -.10, .03], rtol=0, atol=1e-14)
        np.testing.assert_allclose(result.net_return, [.08, -.12, .02], rtol=0, atol=1e-14)
        np.testing.assert_allclose(result.label, result.net_return)
        self.assertTrue(result.label_available_at.eq(stamp("2018-01-03 11:00")).all())
        self.assertEqual(result.label_protocol_hash.nunique(), 1)
        gross = build_execution_labels(executions(), LabelProtocol.from_dict(label_spec("gross_return")))
        np.testing.assert_allclose(gross.label, gross.gross_return)
        self.assertNotEqual(result.label_protocol_hash.iloc[0], gross.label_protocol_hash.iloc[0])

    def test_no_missing_cost_defaults_or_implicit_zero_cost(self):
        data = executions()
        with self.assertRaises(LabelValidationError):
            build_execution_labels(data.drop(columns="entry_fee"), LabelProtocol.from_dict(label_spec()))
        data.loc[0, ["entry_fee", "exit_fee"]] = 0.
        with self.assertRaises(LabelValidationError):
            build_execution_labels(data, LabelProtocol.from_dict(label_spec()))
        result = build_execution_labels(data, LabelProtocol.from_dict(label_spec(zero_cost_reason="Explicit synthetic zero-fee row")))
        self.assertAlmostEqual(result.net_return.iloc[0], .10)

    def test_late_entry_receipt_delays_maturity_and_cannot_be_overridden(self):
        data = executions()
        data.loc[0, "entry_available_at"] = stamp("2018-01-05 09:00")
        protocol = LabelProtocol.from_dict(label_spec())
        result = build_execution_labels(data, protocol)
        self.assertEqual(result.label_available_at.iloc[0], stamp("2018-01-05 09:00"))
        self.assertEqual(result.label_available_at.iloc[1], stamp("2018-01-03 11:00"))
        data["label_available_at"] = stamp("2018-01-03 11:00")
        with self.assertRaisesRegex(LabelValidationError, "precedes actual outcome maturity"):
            build_execution_labels(data, protocol)

    def test_invalid_execution_inputs_fail_instead_of_silent_drop(self):
        mutations = [("entry_fee", -1.), ("entry_price", 0.), ("exit_price", np.nan), ("other_costs", True),
                     ("exit_quantity", 9.), ("side", "short"), ("currency", "EUR"), ("normalization", "adjusted"),
                     ("non_cash_corporate_action", True), ("exit_at", stamp("2018-01-02 09:00")),
                     ("label_available_at", stamp("2018-01-03 10:01")),
                     ("exit_available_at", stamp("2024-01-01")), ("formation_at", pd.Timestamp("2018-01-02"))]
        for column, value in mutations:
            data = executions()
            if isinstance(value, bool) or (isinstance(value, pd.Timestamp) and value.tzinfo is None):
                data[column] = data[column].astype(object)
            data.loc[0, column] = value
            with self.subTest(column=column, value=value), self.assertRaises((LabelValidationError, ValueError)):
                build_execution_labels(data, LabelProtocol.from_dict(label_spec()))
        with self.assertRaises(LabelValidationError):
            build_execution_labels(pd.concat([executions(), executions().iloc[[0]]]), LabelProtocol.from_dict(label_spec()))

    def test_synthetic_rows_cannot_certify_research_and_templates_rejected(self):
        with self.assertRaises(LabelValidationError):
            build_execution_labels(executions(), LabelProtocol.from_dict(label_spec(purpose="research")))
        for raw in ({}, label_spec(price_basis="next_close"), label_spec(target="other")):
            with self.assertRaises(LabelValidationError):
                LabelProtocol.from_dict(raw)

    def test_no_empty_or_non_real_or_overflowed_label_evidence(self):
        protocol = LabelProtocol.from_dict(label_spec())
        with self.assertRaises(LabelValidationError):
            build_execution_labels(executions().iloc[0:0], protocol)
        complex_data = executions()
        complex_data["entry_price"] = complex_data.entry_price.astype(complex)
        complex_data.loc[0, "entry_price"] = 100. + 2.j
        with self.assertRaises(LabelValidationError):
            build_execution_labels(complex_data, protocol)
        overflow = executions()
        overflow.loc[0, ["entry_quantity", "exit_quantity", "entry_price"]] = 1e308
        with self.assertRaises(LabelValidationError):
            build_execution_labels(overflow, protocol)


class ModelTests(unittest.TestCase):
    def test_explicit_identity_and_target_convention(self):
        spec = ModelSpec.from_dict(model_spec())
        model = create_model(spec)
        X = pd.DataFrame({"factor_a": [1., 2., 4.]})
        y = pd.Series([.1, .2, -.1], name="net_return")
        with self.assertRaises(ModelValidationError):
            model.predict(X)
        model.fit(X, y)
        np.testing.assert_array_equal(model.predict(X), [1., 2., 4.])
        with self.assertRaises(ModelValidationError):
            model.fit(X, y.rename("gross_return"))
        model.fit(X, y)
        artifact = model.artifact(fit_cutoff=stamp("2018-01-01"), train_start=stamp("2010-01-01"),
                                  training_metadata=metadata([2010, 2014, 2017]))
        self.assertEqual(artifact["learned_state"], {})
        np.testing.assert_array_equal(restore_model(artifact).predict(X), [1., 2., 4.])

    def test_ridge_has_hand_computed_solution_and_frozen_hyperparameters(self):
        # X=(-1,0,1), y=(-2,0,2), alpha=1 -> coefficient 4/(2+1)=4/3, intercept0.
        spec = ModelSpec.from_dict(model_spec("ridge"))
        model = create_model(spec).fit(pd.DataFrame({"factor_a": [-1., 0., 1.]}),
                                       pd.Series([-2., 0., 2.], name="net_return"))
        np.testing.assert_allclose(model.predict(pd.DataFrame({"factor_a": [-1., 0., 1.]})), [-4 / 3, 0., 4 / 3])
        self.assertNotEqual(spec.configuration_hash,
                            ModelSpec.from_dict(model_spec("ridge", hyperparameters={"alpha": 2., "fit_intercept": True})).configuration_hash)

    def test_train_statistics_are_overwritten_after_old_year_removed(self):
        model = create_model(ModelSpec.from_dict(model_spec("ridge", standardize=True)))
        old_X = pd.DataFrame({"factor_a": [1000., 2., 4.]})
        y = pd.Series([1., 2., 4.], name="net_return")
        model.fit(old_X, y)
        old = model.artifact(fit_cutoff=stamp("2018-01-01"), train_start=stamp("2010-01-01"),
                             training_metadata=metadata([2010, 2014, 2017]))
        X = pd.DataFrame({"factor_a": [2., 4., 6.]})
        model.fit(X, y)
        fitted = model.artifact(fit_cutoff=stamp("2019-01-01"), train_start=stamp("2011-01-01"),
                                training_metadata=metadata([2011, 2015, 2018]))
        self.assertEqual(fitted["learned_state"]["feature_mean"], [4.])
        self.assertNotEqual(old["training_frame_hash"], fitted["training_frame_hash"])
        np.testing.assert_allclose(model.predict(X), restore_model(fitted).predict(X))
        fresh = create_model(model.spec).fit(X, y)
        np.testing.assert_allclose(model.predict(X), fresh.predict(X))

    def test_multifactor_ridge_and_constant_feature_scale(self):
        raw = model_spec("ridge", features=["factor_a", "factor_b"], standardize=True)
        model = create_model(ModelSpec.from_dict(raw))
        X = pd.DataFrame({"factor_a": [-1., 0., 1.], "factor_b": [5., 5., 5.]})
        model.fit(X, pd.Series([-2., 0., 2.], name="net_return"))
        artifact = model.artifact(fit_cutoff=stamp("2018-01-01"), train_start=stamp("2010-01-01"),
                                  training_metadata=metadata([2010, 2014, 2017]))
        self.assertEqual(artifact["learned_state"]["feature_scale"][1], 1.)
        self.assertEqual(artifact["learned_state"]["coefficients"][1], 0.)
        np.testing.assert_allclose(model.predict(X), [-1.5, 0., 1.5], atol=1e-14)
        np.testing.assert_allclose(restore_model(artifact).predict(X), model.predict(X))

    def test_artifacts_reject_immature_labels_old_window_and_tampering(self):
        X, y = pd.DataFrame({"factor_a": [1., 2.]}), pd.Series([.1, .2], name="net_return")
        model = create_model(ModelSpec.from_dict(model_spec())).fit(X, y)
        base = metadata([2010, 2017])
        for change in ("immature", "too_old", "mismatch"):
            data = base.copy()
            if change == "immature":
                data.loc[1, "label_available_at"] = stamp("2018-01-01")
            elif change == "too_old":
                data.loc[0, "formation_at"] = stamp("2009-01-01")
            else:
                data.index = [2, 3]
            with self.subTest(change=change), self.assertRaises(ModelValidationError):
                model.artifact(fit_cutoff=stamp("2018-01-01"), train_start=stamp("2010-01-01"), training_metadata=data)
        artifact = model.artifact(fit_cutoff=stamp("2018-01-01"), train_start=stamp("2010-01-01"), training_metadata=base)
        artifact["training_rows"] = 3
        with self.assertRaises(ModelValidationError):
            restore_model(artifact)

    def test_undefined_model_features_and_partial_inputs_rejected(self):
        for raw in ({}, model_spec(model_family=None), model_spec(features=["label"]),
                    model_spec("ridge", hyperparameters={"alpha": -1., "fit_intercept": True}),
                    model_spec("ridge", trainable_parameters=[])):
            with self.assertRaises(ModelValidationError):
                ModelSpec.from_dict(raw)
        model = create_model(ModelSpec.from_dict(model_spec()))
        with self.assertRaises(ModelValidationError):
            model.fit(pd.DataFrame({"factor_a": [np.nan]}), pd.Series([.1], name="net_return"))
        with self.assertRaises(ModelValidationError):
            model.fit(pd.DataFrame({"factor_a": [1.], "sid": [2.]}), pd.Series([.1], name="net_return"))

    def test_invalid_refit_invalidates_previous_state_and_rehashed_boundary_fails(self):
        X, y = pd.DataFrame({"factor_a": [1., 2.]}), pd.Series([.1, .2], name="net_return")
        model = create_model(ModelSpec.from_dict(model_spec())).fit(X, y)
        artifact = model.artifact(fit_cutoff=stamp("2018-01-01"), train_start=stamp("2010-01-01"),
                                  training_metadata=metadata([2010, 2017]))
        artifact["fit_cutoff"], artifact["train_start"] = stamp("2018-02-01").isoformat(), stamp("2010-02-01").isoformat()
        artifact["artifact_hash"] = digest({k: v for k, v in artifact.items() if k != "artifact_hash"})
        with self.assertRaises(ModelValidationError):
            restore_model(artifact)
        with self.assertRaises(ModelValidationError):
            model.fit(X, y.rename("gross_return"))
        with self.assertRaises(ModelValidationError):
            model.predict(X)
        with self.assertRaises(ModelValidationError):
            ModelSpec.from_dict(model_spec(features=[{"not": "a feature"}]))


if __name__ == "__main__":
    unittest.main()
