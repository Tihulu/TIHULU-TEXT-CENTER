"""Read-only check that the 97 requirement source/test candidates have no false local paths.

No external network and no device access. External Flight Radar refs are pinned
GitHub SHAs and checked by its canonical repository workstream separately.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT/"apps/_coordination/REQUIREMENT_SOURCE_TEST_CANDIDATES.json"

class CandidatePathTests(unittest.TestCase):
    def test_all_97_ids_have_source_candidates_and_existing_local_paths(self):
        manifest=json.loads(MAP.read_text(encoding="utf-8"))
        entries=manifest["entries"]
        self.assertEqual(len(entries),97)
        self.assertEqual(len({r["id"] for r in entries}),97)
        self.assertEqual(manifest["summary"]["at_least_one_existing_source"],97)
        for row in entries:
            self.assertFalse(row["implementation_status"]=="verified")
            self.assertTrue(any(x["exists_at_ref"] for x in row["candidate_sources"]))
            for role in ("candidate_sources","candidate_tests"):
                for evidence in row[role]:
                    self.assertTrue(evidence["exists_at_ref"],(row["id"],evidence["path"]))
                    if evidence["repository"]=="Tihulu/TIHULU-TEXT-CENTER":
                        self.assertTrue((ROOT/evidence["path"]).is_file(),
                                        (row["id"],evidence["path"]))
                    if role=="candidate_tests":
                        self.assertEqual(evidence["test_execution_status"],
                                         "not_executed_for_this_requirement")

    def test_honest_gaps_and_unmerged_export_branch_protected(self):
        manifest=json.loads(MAP.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["at_least_one_existing_test"],86)
        self.assertEqual(len(manifest["summary"]["without_existing_test"]),11)
        self.assertEqual(manifest["summary"]["unresolved_paths"],[])
        doc=json.loads((ROOT/"apps/_coordination/UNMERGED_MEDIA_EXPORT_PROVENANCE.json").read_text())
        self.assertEqual(doc["source_commit_sha"],
                         "4e62e21cd5252df8a04f9ceadc429f4b116412ce")
        self.assertTrue(doc["branch_is_not_audit_doc_branch"])
        self.assertTrue(doc["not_merged_to_main"])
        self.assertEqual(len(doc["verified_files"]),6)
        self.assertFalse(any(e["executed_test"] for e in doc["verified_files"]))

if __name__=="__main__":
    unittest.main()
