"""Synthetic end-to-end data-plan, causal view, formula and artifact reuse."""
import json
import unittest
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore
from qresearch.cache import SharedDataCache
from qresearch.contracts import RECORD_COLUMNS
from qresearch.factors import FactorSpec
from qresearch.runtime import ResearchEngine
from test_data_pipeline import FixtureProvider, ts
import test_data_pipeline as fixtures
from test_factors import specification


class RuntimeTests(unittest.TestCase):
    def test_one_prefetch_many_factors_and_deduplicated_result(self):
        class CountingStore(MemoryArtifactStore):
            creations = 0
            def write_once(self, key, data):
                created = super().write_once(key, data)
                self.creations += int(created)
                return created
        store, provider = CountingStore(), FixtureProvider()
        cache = SharedDataCache(store, provider)
        engine = ResearchEngine(cache, synthetic=True)
        request = fixtures.DataPipelineTests().request()
        engine.prepare([request])
        specs = [FactorSpec.from_dict(specification({"op": "field", "name": "close"}, "a")),
                 FactorSpec.from_dict(specification({"op": "multiply", "args": [2, {"op": "field", "name": "close"}]}, "b"))]
        # Declare just the actual required approved field for this fixture.
        for i, item in enumerate(specs):
            raw = item.to_dict()
            raw["allowed_fields"] = ["close"]
            specs[i] = FactorSpec.from_dict(raw)
        formation = ts(3, 9)
        membership = pd.DataFrame([[True, True]], index=[formation], columns=["A", "B"])
        arguments = (specs, request, [formation], ("A", "B"), {"close": "exact_session"}, {formation: ts(2)})
        first = engine.evaluate(*arguments, membership=membership)
        before = store.creations
        second = engine.evaluate(*arguments, membership=membership)
        self.assertEqual(first, second)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(first["values"]["data"]), 2)
        self.assertEqual(before, store.creations)
        membership.loc[formation, "B"] = False
        third = engine.evaluate(*arguments, membership=membership)
        self.assertEqual(len(third["values"]["data"]), 1)
        self.assertNotEqual(first["identity"], third["identity"])

    def test_market_cache_rejects_local_store(self):
        with self.assertRaises(ValueError):
            ResearchEngine(SharedDataCache(MemoryArtifactStore(), FixtureProvider()), code_version="pinned")


if __name__ == "__main__":
    unittest.main()
