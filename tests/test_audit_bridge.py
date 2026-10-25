"""Trusted program evidence must resolve to exact immutable check observations."""
import unittest
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.audits import FORMULA_ISSUER, audit_formula, make_evidence, verify_evidence
from qresearch.study import StudySpec
from test_study import fixture_study


class AuditBridgeTests(unittest.TestCase):
    def test_formula_audit_produces_resolvable_engineering_evidence(self):
        store = MemoryArtifactStore()
        study = StudySpec.from_dict(fixture_study(), field_catalog=["close"])
        evidence = audit_formula(store, study, subject_hash=study.hash,
                                 source_hash=study.to_dict()["data_binding"]["code_hash"])
        evidence.verify_references(store).require_passed()
        verify_evidence(store, evidence.to_dict(), subject_hash=study.hash,
                        source_hash=study.to_dict()["data_binding"]["code_hash"],
                        issuer=FORMULA_ISSUER, required_checks=("validated_study_contract",), scope="engineering")
        with self.assertRaises(ValueError):
            verify_evidence(store, evidence.to_dict(), subject_hash=study.hash,
                            source_hash=study.to_dict()["data_binding"]["code_hash"],
                            issuer=FORMULA_ISSUER, required_checks=("validated_study_contract",), scope="research")

    def test_failed_or_unrelated_checks_cannot_advance(self):
        store = MemoryArtifactStore()
        subject, source = content_hash({"study": 1}), content_hash({"code": 1})
        evidence = make_evidence(store, subject_hash=subject, source_hash=source,
                                 issuer=FORMULA_ISSUER, checks={"required": False}, scope="engineering")
        with self.assertRaises(ValueError):
            verify_evidence(store, evidence.to_dict(), subject_hash=subject, source_hash=source,
                            issuer=FORMULA_ISSUER, required_checks=("required",), scope="engineering")
        with self.assertRaises(ValueError):
            verify_evidence(store, evidence.to_dict(), subject_hash=subject, source_hash=source,
                            issuer=FORMULA_ISSUER, required_checks=("different",), scope="engineering")

    def test_cannot_change_failed_observation_into_passed_envelope(self):
        store = MemoryArtifactStore()
        subject, source = content_hash({"study": 1}), content_hash({"code": 1})
        evidence = make_evidence(store, subject_hash=subject, source_hash=source,
                                 issuer=FORMULA_ISSUER, checks={"required": False}, scope="engineering")
        forged = evidence.to_dict()
        forged["checks"][0]["passed"] = True
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_evidence(store, forged, subject_hash=subject, source_hash=source,
                            issuer=FORMULA_ISSUER, required_checks=("required",), scope="engineering", require_passed=False)

    def test_registered_audit_cannot_back_a_different_study(self):
        store = MemoryArtifactStore()
        study = StudySpec.from_dict(fixture_study(), field_catalog=["close"])
        package = {"study": study.to_dict(), "workflow_schema_version": 1}
        package_hash = content_hash(package)
        from qresearch.artifacts import canonical_json
        store.write_once("configurations/" + package_hash + ".json", canonical_json(package))
        audit_formula(store, study, subject_hash=package_hash, source_hash=study.to_dict()["data_binding"]["code_hash"])
        wrong = {"study": {"other": True}, "workflow_schema_version": 1}
        wrong_hash = content_hash(wrong)
        store.write_once("configurations/" + wrong_hash + ".json", canonical_json(wrong))
        with self.assertRaisesRegex(ValueError, "exact"):
            audit_formula(store, study, subject_hash=wrong_hash, source_hash=study.to_dict()["data_binding"]["code_hash"])


if __name__ == "__main__":
    unittest.main()
