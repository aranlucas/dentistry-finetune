"""Append-only review decisions must reject mutation without modifying prior bytes."""
import json
import tempfile
import unittest
from pathlib import Path

from judgment_journal import append, verified_rows


class JournalChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.review = Path(temporary.name)
        self.path = self.review / 'judgments.jsonl'

    def test_append_preserves_prior_bytes_and_links_new_decision(self):
        append(self.review, [{'id': 'a', 'decision': 'pass'}])
        original = self.path.read_bytes()
        append(self.review, [{'id': 'b', 'decision': 'fail'}])
        self.assertTrue(self.path.read_bytes().startswith(original))
        decisions = verified_rows(self.path)
        self.assertEqual([r['id'] for r in decisions], ['a', 'b'])
        self.assertEqual(decisions[1]['previous_sha256'], decisions[0]['entry_sha256'])
        self.assertEqual(decisions[1]['sequence'], 2)

    def test_duplicate_later_in_batch_leaves_journal_unchanged(self):
        append(self.review, [{'id': 'a'}])
        original = self.path.read_bytes()
        for entries in [[{'id': 'b'}, {'id': 'a'}], [{'id': 'b'}, {'id': 'b'}]]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                append(self.review, entries)
            self.assertEqual(self.path.read_bytes(), original)

    def test_mutation_and_reordering_are_rejected_before_append(self):
        append(self.review, [{'id': 'a', 'decision': 'pass'}, {'id': 'b'}])
        original = self.path.read_text().splitlines()
        changed = json.loads(original[0]); changed['decision'] = 'fail'
        for lines in [[json.dumps(changed), original[1]], original[::-1]]:
            self.path.write_text('\n'.join(lines) + '\n')
            corrupted = self.path.read_bytes()
            with self.assertRaises(ValueError):
                verified_rows(self.path)
            with self.assertRaises(ValueError):
                append(self.review, [{'id': 'c'}])
            self.assertEqual(self.path.read_bytes(), corrupted)

    def test_legacy_serialized_record_is_read_unchanged(self):
        raw = '{"id": "legacy", "decision": "pass", "sequence": 1, "previous_sha256": null, "time_unix": 123.0, "entry_sha256": "14a1036f707243154d8597005f5a504ff3bceedb1009e315a71a30910e79ae81"}\n'
        self.path.write_text(raw)
        self.assertEqual(verified_rows(self.path)[0]["id"], "legacy")
        self.assertEqual(self.path.read_text(), raw)

    def test_concurrent_append_preserves_both_decisions(self):
        # Pause writer A after reading its tail; B must not read a stale tail.
        import concurrent.futures
        import threading
        from unittest.mock import patch
        import judgment_journal

        original = judgment_journal.verified_rows
        read_a = threading.Event()
        release_a = threading.Event()
        start_b = threading.Event()

        def paused_read(path):
            result = original(path)
            if threading.current_thread().name.startswith('writer-a'):
                read_a.set()
                if not release_a.wait(3):
                    raise RuntimeError('Writer release timed out')
            return result

        def second_writer():
            start_b.set()
            append(self.review, [{'id': 'b'}])

        with patch.object(judgment_journal, 'verified_rows', paused_read), \
             concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix='writer-a') as first, \
             concurrent.futures.ThreadPoolExecutor(1, thread_name_prefix='writer-b') as second:
            a = first.submit(append, self.review, [{'id': 'a'}])
            try:
                self.assertTrue(read_a.wait(2))
                b = second.submit(second_writer)
                self.assertTrue(start_b.wait(2))
                try:
                    b.result(timeout=0.3)
                except concurrent.futures.TimeoutError:
                    pass
            finally:
                release_a.set()
            a.result(timeout=2)
            b.result(timeout=2)
        self.assertEqual({r['id'] for r in verified_rows(self.path)}, {'a', 'b'})
