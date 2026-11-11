"""Ensure sample legacy PR links are grounded and never forge approvals.

Metadata only; never fetch or distribute private chat or comment bodies.
"""
import json
from pathlib import Path
import unittest

AUDIT=Path(__file__).resolve().parents[1]/"apps/_coordination/PR_COMMENT_LINK_INDEX.json"

class OriginalDiscussionLinkTests(unittest.TestCase):
    def test_original_links_and_repo_ids_preserved(self):
        r=json.loads(AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(r["checked_pr_count"],13)
        self.assertEqual(r["confirmed_linked_comment_count"],8)
        self.assertFalse(r["all_history_export_complete"])
        self.assertFalse(r["review_threads_full_export_complete"])
        ids=set()
        for c in r["original_comment_refs"]:
            self.assertEqual(c["original_repository_id"],1447534043)
            self.assertEqual(c["original_pr_number"],13)
            self.assertIn(f"issuecomment-{c['comment_id']}",c["original_url"])
            self.assertNotIn(c["comment_id"],ids)
            ids.add(c["comment_id"])
            self.assertFalse(c["original_body_exported"])
            self.assertFalse(c["original_approval_recreated"])
            self.assertEqual(c["created_at"],c["updated_at"])

if __name__=="__main__":
    unittest.main()
