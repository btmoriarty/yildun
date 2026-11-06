#!/usr/bin/env python3
"""Tests for do_sync against throwaway bare remotes. Standard library only; nothing leaves the temp dir.

Run: python3 /Users/moriarty/code/yildun/connector/test_sync.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402

LOG_LINE = '{"ts":"2026-11-06T10:00:00+00:00","verdict":"accept","since_prev_s":null}\n'


def git(cwd, *args, check=True):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8", newline="") as fh:
        fh.write(text)


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


class SyncCase(unittest.TestCase):
    """A bare remote, the writer's clone, and a mentor's clone."""
    DEFAULT = "main"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="yildun-sync-")
        self.addCleanup(shutil.rmtree, self.tmp)
        self.env = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.addCleanup(lambda: [os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in saved.items()])
        self.bare = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", self.DEFAULT, self.bare], check=True)
        seed = os.path.join(self.tmp, "seed")
        subprocess.run(["git", "init", "-q", "-b", self.DEFAULT, seed], check=True)
        write(os.path.join(seed, "README.md"), "study repo\n")
        write(os.path.join(seed, "students/sam/piece.md"), "one\ntwo\nthree\n")
        write(os.path.join(seed, "students/sam/piece.amr.jsonl"),
              "".join(LOG_LINE.replace("10:00", f"10:{m:02d}") for m in range(12)))
        git(seed, "add", "-A")
        git(seed, "commit", "-qm", "seed")
        git(seed, "push", "-q", self.bare, self.DEFAULT)
        self.writer = self.clone("writer")
        self.mentor = self.clone("mentor")
        self.drafts = os.path.join(self.writer, "students", "sam")
        self.log = os.path.join(self.drafts, "piece.amr.jsonl")
        drafts_before = server.DRAFTS
        self.addCleanup(lambda: setattr(server, "DRAFTS", drafts_before))
        server.DRAFTS = self.drafts

    def clone(self, name):
        path = os.path.join(self.tmp, name)
        subprocess.run(["git", "clone", "-q", self.bare, path], check=True, capture_output=True)
        return path

    def mentor_pushes(self, relpath="students/mentor-notes.md", text="a note\n"):
        write(os.path.join(self.mentor, relpath), text)
        git(self.mentor, "add", "-A")
        git(self.mentor, "commit", "-qm", "mentor push")
        git(self.mentor, "push", "-q", "origin", self.DEFAULT)

    def remote_file(self, relpath, ref=None):
        return subprocess.run(["git", "-C", self.bare, "show", f"{ref or self.DEFAULT}:{relpath}"],
                              capture_output=True, check=True).stdout

    def writer_appends_log(self, line=LOG_LINE):
        write(self.log, line, "a")

    def assert_no_rebase_open(self):
        for d in ("rebase-merge", "rebase-apply"):
            self.assertFalse(os.path.exists(os.path.join(self.writer, ".git", d)), d)


class TestCleanPullAndPush(SyncCase):
    def test_mentor_push_no_longer_strands_the_writer(self):
        self.mentor_pushes()
        self.writer_appends_log()
        before = read_bytes(self.log)
        out = server.do_sync("session")
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["committed"])
        self.assertTrue(out["pushed"])
        self.assertTrue(os.path.exists(os.path.join(self.writer, "students/mentor-notes.md")))
        self.assertEqual(read_bytes(self.log), before)
        self.assertEqual(self.remote_file("students/sam/piece.amr.jsonl"), before)
        self.assertEqual(self.remote_file("students/mentor-notes.md"), b"a note\n")
        git(self.writer, "merge-base", "--is-ancestor", "origin/main", "HEAD")
        self.assertEqual(git(self.writer, "log", "-1", "--format=%s"), "session")

    def test_no_mentor_push_is_a_plain_commit_and_push(self):
        write(os.path.join(self.drafts, "piece.md"), "one\ntwo\nthree\nfour\n")
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.remote_file("students/sam/piece.md"), b"one\ntwo\nthree\nfour\n")

    def test_writer_commit_keeps_its_author_date(self):
        self.mentor_pushes()
        self.writer_appends_log()
        env = dict(os.environ, GIT_AUTHOR_DATE="1793000000 +0000")
        git(self.writer, "add", "-A")
        subprocess.run(["git", "-C", self.writer, "commit", "-qm", "older"], env=env, check=True)
        self.assertTrue(server.do_sync()["ok"])
        self.assertEqual(git(self.writer, "log", "-1", "--format=%at"), "1793000000")

    def test_mentor_edit_elsewhere_in_the_same_piece_merges(self):
        self.mentor_pushes("students/sam/piece.md", "ONE\ntwo\nthree\n")
        write(os.path.join(self.drafts, "piece.md"), "one\ntwo\nTHREE\n")
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.remote_file("students/sam/piece.md"), b"ONE\ntwo\nTHREE\n")


class TestConflict(SyncCase):
    def assert_stopped_intact(self, out, wrote, expected_conflict):
        self.assertFalse(out["ok"], out)
        self.assertFalse(out["pushed"])
        self.assertIn("not sent", out["error"])
        self.assertEqual(out["conflicts"], [expected_conflict])
        self.assert_no_rebase_open()
        self.assertEqual(git(self.writer, "symbolic-ref", "--short", "HEAD"), "main")
        self.assertEqual(git(self.writer, "status", "--porcelain"), "")
        self.assertEqual(git(self.writer, "log", "-1", "--format=%s"), "session")
        self.assertEqual(read_bytes(os.path.join(self.writer, expected_conflict)), wrote)

    def test_real_conflict_in_the_piece(self):
        self.mentor_pushes("students/sam/piece.md", "mentor\ntwo\nthree\n")
        path = os.path.join(self.drafts, "piece.md")
        write(path, "writer\ntwo\nthree\n")
        out = server.do_sync("session")
        head_after = git(self.writer, "rev-parse", "HEAD")
        self.assert_stopped_intact(out, b"writer\ntwo\nthree\n", "students/sam/piece.md")
        self.assertEqual(git(self.writer, "show", "--format=", "--name-only", head_after),
                         "students/sam/piece.md")
        self.assertEqual(self.remote_file("students/sam/piece.md"), b"mentor\ntwo\nthree\n")

    def test_saving_again_after_a_conflict_stops_the_same_way(self):
        self.mentor_pushes("students/sam/piece.md", "mentor\ntwo\nthree\n")
        path = os.path.join(self.drafts, "piece.md")
        write(path, "writer\ntwo\nthree\n")
        server.do_sync("session")
        out = server.do_sync("again")
        self.assertFalse(out["committed"])
        self.assertTrue(out["nothing_new"])
        self.assert_stopped_intact(out, b"writer\ntwo\nthree\n", "students/sam/piece.md")

    def test_log_changed_on_both_sides_is_not_auto_merged(self):
        # The edits are on lines far apart, so git alone would merge them cleanly and rewrite the log.
        lines = read_bytes(self.log).decode().splitlines(True)
        lines[0] = lines[0].replace('"accept"', '"reject"')
        self.mentor_pushes("students/sam/piece.amr.jsonl", "".join(lines))
        self.writer_appends_log()
        wrote = read_bytes(self.log)
        head_before_sync = git(self.writer, "rev-parse", "HEAD")
        out = server.do_sync("session")
        self.assert_stopped_intact(out, wrote, "students/sam/piece.amr.jsonl")
        self.assertEqual(git(self.writer, "rev-parse", "HEAD~1"), head_before_sync)
        self.assertEqual(self.remote_file("students/sam/piece.amr.jsonl"), "".join(lines).encode())

    def test_non_ascii_log_name_is_still_caught(self):
        name = "students/sam/niño.amr.jsonl"
        write(os.path.join(self.writer, name), LOG_LINE)
        git(self.writer, "add", "-A")
        git(self.writer, "commit", "-qm", "add")
        git(self.writer, "push", "-q", "origin", "main")
        git(self.mentor, "pull", "-q")
        self.mentor_pushes(name, "mentor\n" + LOG_LINE)
        write(os.path.join(self.writer, name), LOG_LINE + LOG_LINE)
        out = server.do_sync("session")
        self.assertFalse(out["ok"], out)
        self.assertEqual(out["conflicts"], [name])
        self.assertEqual(read_bytes(os.path.join(self.writer, name)), (LOG_LINE + LOG_LINE).encode())


class TestWrongBranch(SyncCase):
    def test_other_branch_is_refused_before_any_commit(self):
        git(self.writer, "switch", "-qc", "my-experiment")
        self.writer_appends_log()
        head = git(self.writer, "rev-parse", "HEAD")
        wrote = read_bytes(self.log)
        out = server.do_sync()
        self.assertFalse(out["ok"], out)
        self.assertFalse(out["committed"])
        self.assertFalse(out["pushed"])
        self.assertIn("'my-experiment'", out["error"])
        self.assertIn("'main'", out["error"])
        self.assertEqual(git(self.writer, "rev-parse", "HEAD"), head)
        self.assertEqual(read_bytes(self.log), wrote)
        self.assertNotIn("my-experiment", git(self.bare, "branch", "--list"))

    def test_detached_head_is_refused(self):
        git(self.writer, "switch", "-q", "--detach")
        out = server.do_sync()
        self.assertFalse(out["ok"], out)
        self.assertIn("not on a branch", out["error"])

    def test_default_found_on_the_remote_when_the_clone_has_no_record(self):
        git(self.writer, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
        git(self.writer, "switch", "-qc", "my-experiment")
        out = server.do_sync()
        self.assertFalse(out["ok"], out)
        self.assertIn("'main'", out["error"])


class TestOtherDefaultName(SyncCase):
    DEFAULT = "trunk"

    def test_default_branch_name_is_not_hard_coded(self):
        self.mentor_pushes()
        self.writer_appends_log()
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.remote_file("students/mentor-notes.md"), b"a note\n")


class TestNothingNew(SyncCase):
    def test_nothing_new_and_nothing_upstream(self):
        head = git(self.writer, "rev-parse", "HEAD")
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["nothing_new"])
        self.assertFalse(out["committed"])
        self.assertEqual(git(self.writer, "rev-parse", "HEAD"), head)

    def test_nothing_new_still_brings_in_a_mentor_push(self):
        self.mentor_pushes()
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["nothing_new"])
        self.assertTrue(os.path.exists(os.path.join(self.writer, "students/mentor-notes.md")))


class TestOtherFailures(SyncCase):
    def test_unreachable_remote_keeps_the_local_commit(self):
        self.writer_appends_log()
        git(self.writer, "remote", "set-url", "origin", os.path.join(self.tmp, "gone.git"))
        out = server.do_sync("session")
        self.assertFalse(out["ok"], out)
        self.assertTrue(out["committed"])
        self.assertIn("could not be reached", out["error"])
        self.assertEqual(git(self.writer, "log", "-1", "--format=%s"), "session")

    def test_the_next_save_sends_what_an_unreachable_remote_held_back(self):
        self.writer_appends_log()
        git(self.writer, "remote", "set-url", "origin", os.path.join(self.tmp, "gone.git"))
        server.do_sync("session")
        wrote = read_bytes(self.log)
        git(self.writer, "remote", "set-url", "origin", self.bare)
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["nothing_new"])
        self.assertEqual(self.remote_file("students/sam/piece.amr.jsonl"), wrote)

    def test_a_push_lost_to_a_race_goes_through_on_the_next_save(self):
        self.writer_appends_log()
        wrote = read_bytes(self.log)
        write(os.path.join(self.mentor, "race.md"), "raced\n")
        git(self.mentor, "add", "-A")
        git(self.mentor, "commit", "-qm", "mentor race")
        hook = os.path.join(self.writer, ".git", "hooks", "pre-push")
        write(hook, f'#!/bin/sh\nunset GIT_DIR\ngit -C "{self.mentor}" push -q origin main\n')
        os.chmod(hook, 0o755)
        out = server.do_sync("session")
        self.assertFalse(out["ok"], out)
        self.assertTrue(out["committed"])
        self.assertIn("push to the study repo failed", out["error"])
        os.remove(hook)
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.remote_file("race.md"), b"raced\n")
        self.assertEqual(self.remote_file("students/sam/piece.amr.jsonl"), wrote)

    def test_failed_commit_is_reported_and_not_mistaken_for_a_conflict(self):
        self.writer_appends_log()
        hook = os.path.join(self.writer, ".git", "hooks", "pre-commit")
        write(hook, "#!/bin/sh\nexit 1\n")
        os.chmod(hook, 0o755)
        out = server.do_sync()
        self.assertFalse(out["ok"], out)
        self.assertFalse(out["committed"])
        self.assertIn("could not be committed", out["error"])

    def test_not_a_git_folder(self):
        server.DRAFTS = self.tmp
        out = server.do_sync()
        self.assertFalse(out["ok"], out)
        self.assertIn("not inside a git repository", out["error"])

    def test_first_push_to_an_empty_remote(self):
        empty = os.path.join(self.tmp, "empty.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", empty], check=True)
        fresh = os.path.join(self.tmp, "fresh")
        subprocess.run(["git", "clone", "-q", empty, fresh], check=True, capture_output=True)
        write(os.path.join(fresh, "students/sam/piece.md"), "one\n")
        server.DRAFTS = os.path.join(fresh, "students", "sam")
        out = server.do_sync()
        self.assertTrue(out["ok"], out)
        self.assertEqual(git(empty, "show", "main:students/sam/piece.md"), "one")


if __name__ == "__main__":
    unittest.main()
