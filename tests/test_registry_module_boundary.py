"""Deployment/import boundaries of the readable shared Registry modules."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RegistryModuleBoundaryTests(unittest.TestCase):
    def test_both_import_orders_preserve_one_error_type_and_one_state_policy(self):
        for first, second in (("registry_engineering", "registry"), ("registry", "registry_engineering")):
            code = ("import sys\n"
                + "sys.path.insert(0," + repr(str(ROOT / "cloud")) + ")\n"
                + "import qresearch." + first + "\nimport qresearch." + second + "\n"
                + "from qresearch import registry as core, registry_engineering as engineering\n"
                + "assert issubclass(core.Registry,engineering.RegistryEngineeringMixin)\n"
                + "assert core.RegistryError is engineering.RegistryError\n"
                + "assert core.BudgetExceeded is engineering.BudgetExceeded\n"
                + "assert core.CorruptRegistry is engineering.CorruptRegistry\n"
                + "assert issubclass(core.BudgetExceeded,core.RegistryError)\n"
                + "assert core._OPEN_STATES is engineering._OPEN_STATES\n"
                + "assert set(core._BUDGET_KEYS)==set(engineering.RESOURCES)\n"
                + "assert core.Registry.authorize_engineering_round.__module__=='qresearch.registry_engineering'\n"
                + "assert core.Registry._replay.__module__=='qresearch.registry'\n"
                + "print('shared-registry-import-ok')\n")
            process = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.strip(), "shared-registry-import-ok")

    def test_readable_registry_parts_fit_native_cloud_file_limit_with_headroom(self):
        for name in ("registry.py", "registry_engineering.py"):
            path = ROOT / "cloud/qresearch" / name
            text = path.read_text(encoding="utf-8-sig")
            # QC's file size is characters; UTF-16 units conservatively cover
            # any supplementary Unicode in comments as well as ordinary ASCII.
            self.assertLess(len(text.encode("utf-16-le")) // 2, 55000, name)
            self.assertGreater(len(text.splitlines()), 100, name)
            self.assertNotIn("exec(base64", text)


if __name__ == "__main__":
    unittest.main()
