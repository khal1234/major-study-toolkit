import tempfile
import unittest
from pathlib import Path
from feedback_lifecycle import linkage_issues, triage_issues


class FeedbackLifecycleTest(unittest.TestCase):
    def test_new_workorder_needs_real_inbox_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'data/전전/ch01-change.workorder.md'
            work.parent.mkdir(parents=True)
            work.write_text('# change\n', encoding='utf-8')
            rel = 'data/전전/ch01-change.workorder.md'
            self.assertTrue(linkage_issues(root, [rel], [rel]))
            work.write_text('Feedback-Inbox: data/전전/ch01-review-inbox.md#E08\n', encoding='utf-8')
            inbox = root / 'data/전전/ch01-review-inbox.md'
            inbox.write_text('- ☐ E08 · open | 분류=부류 | 범위=동일 절 | 원인=절차 중복\n', encoding='utf-8')
            self.assertEqual(linkage_issues(root, [rel], [rel]), [])
            inbox.write_text('- ☐ E09 · other\n', encoding='utf-8')
            self.assertTrue(linkage_issues(root, [rel], [rel]))

    def test_new_issue_must_classify_before_workorder(self):
        self.assertTrue(triage_issues(['- ☐ E08 · fix this']))
        self.assertEqual(triage_issues(['- ☐ E08 · fix this | 분류=시스템 | 범위=전 과목 | 원인=게이트 누락']), [])
        self.assertEqual(triage_issues(['- ☑ E07 · prior closure']), [])

    def test_common_workorder_needs_classified_common_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / 'docs/system.workorder.md'
            work.parent.mkdir(parents=True)
            work.write_text('Feedback-Inbox: docs/받은것-인박스.md#SYS-1\n', encoding='utf-8')
            inbox = root / 'docs/받은것-인박스.md'
            inbox.write_text('- ☐ SYS-1 · recurrence | 분류=시스템 | 범위=전 과목 | 원인=접수 선행 검사 부재\n', encoding='utf-8')
            self.assertEqual(linkage_issues(root, ['docs/system.workorder.md'], ['docs/system.workorder.md']), [])
            inbox.write_text('- ☐ SYS-1 · recurrence\n', encoding='utf-8')
            self.assertTrue(linkage_issues(root, ['docs/system.workorder.md'], ['docs/system.workorder.md']))

    def test_chapter_edit_must_reconcile_open_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / 'data/전전/ch01-review-inbox.md'
            inbox.parent.mkdir(parents=True)
            inbox.write_text('- ☐ E08 · open\n', encoding='utf-8')
            chapter = 'data/전전/ch01.json'
            self.assertTrue(linkage_issues(root, [chapter], []))
            self.assertEqual(linkage_issues(root, [chapter, 'data/전전/ch01-review-inbox.md'], []), [])
            inbox.write_text('- ☑ E08 · fixed, verified\n', encoding='utf-8')
            self.assertEqual(linkage_issues(root, [chapter], []), [])


if __name__ == '__main__':
    unittest.main()
