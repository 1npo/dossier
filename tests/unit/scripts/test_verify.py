import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import buildlog
import verify

SCRIPT = Path(verify.__file__).resolve().parent / "dossier.py"

BLOB = b"".join(f"line {i}\n".encode() for i in range(1, 21))


def text(t, conf="confirmed", cite=("a.py:2-4",), **kw):
    return {"type": "text", "text": t, "conf": conf, "cite": list(cite), **kw}


def report(*blocks):
    return {"blocks": list(blocks)}


def reports_of(n=8, **kw):
    return {"entry": report(*[text(f"Claim {i}.", **kw) for i in range(n)])}


class TestEligible:
    def test_cited_file_range_is_eligible(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.eligible({"entry": report(text("It runs."))}, cites)

        assert [c["text"] for c in got["entry"]] == ["It runs."]

    def test_facts_only_claim_is_not_eligible(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.eligible({"entry": report(text("x", cite=["facts:git"]))}, cites)

        assert got == {}

    def test_directory_citation_is_not_eligible(self, make_cites):
        cites = make_cites({"src/a.py": BLOB}, dirs=["src"])

        got = verify.eligible({"entry": report(text("x", cite=["src"]))}, cites)

        assert got == {}

    def test_file_without_lines_is_not_eligible(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.eligible({"entry": report(text("x", cite=["a.py"]))}, cites)

        assert got == {}

    def test_unknown_claim_is_not_eligible(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.eligible({"entry": report(text("x", conf="unknown"))}, cites)

        assert got == {}

    def test_gaps_report_is_not_sampled(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.eligible({"gaps": report(text("x"))}, cites)

        assert got == {}


class TestSample:
    def test_same_seed_gives_same_sample(self, make_cites):
        cites = make_cites({"a.py": BLOB})
        elig = verify.eligible(reports_of(), cites)

        a = verify.sample(elig, "s1", 3, cites)
        b = verify.sample(elig, "s1", 3, cites)

        assert a == b
        assert len(a) == 3

    def test_different_seed_gives_different_sample(self, make_cites):
        cites = make_cites({"a.py": BLOB})
        elig = verify.eligible(reports_of(20), cites)

        a = [i["key"] for i in verify.sample(elig, "s1", 5, cites)]
        b = [i["key"] for i in verify.sample(elig, "s2", 5, cites)]

        assert a != b

    def test_fewer_claims_than_limit_gives_all(self, make_cites):
        cites = make_cites({"a.py": BLOB})
        elig = verify.eligible(reports_of(2), cites)

        got = verify.sample(elig, "s", 5, cites)

        assert len(got) == 2
        assert [i["id"] for i in got] == ["V01", "V02"]

    def test_claim_has_no_citation_marker_or_confidence_word(self, make_cites):
        cites = make_cites({"a.py": BLOB})
        rep = {"entry": report(text("It runs [[a.py:2-4]] here.", conf="inferred"))}

        got = verify.sample(verify.eligible(rep, cites), "s", 5, cites)

        assert got[0]["claim"] == "It runs here."
        assert "inferred" not in str(got[0])

    def test_item_holds_no_report_or_card_text(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.sample(verify.eligible(reports_of(1), cites), "s", 5, cites)

        assert set(got[0]) == {"id", "report", "card", "key", "claim", "code"}


class TestExcerpt:
    def test_lines_are_numbered(self, make_cites):
        cites = make_cites({"a.py": BLOB})

        got = verify.excerpt(cites, "a.py:2-3")

        assert got == "2: line 2\n3: line 3"


class TestCheckResults:
    SAMPLE = {"details": {"items": [{"id": "V01"}, {"id": "V02"}]}}

    def ok(self, i, verdict="supported"):
        return {"id": i, "verdict": verdict, "reason": "r"}

    def test_complete_answers_have_no_problems(self):
        got = verify.check_results(self.SAMPLE, [self.ok("V01"), self.ok("V02", "cannot tell")])

        assert got == []

    def test_missing_id_is_reported(self):
        got = verify.check_results(self.SAMPLE, [self.ok("V01")])

        assert got == ["V02: no answer."]

    def test_duplicate_id_is_reported(self):
        got = verify.check_results(self.SAMPLE, [self.ok("V01"), self.ok("V01"), self.ok("V02")])

        assert any("V01: answered more than once" in p for p in got)

    def test_unknown_id_is_reported(self):
        got = verify.check_results(self.SAMPLE, [self.ok("V01"), self.ok("V02"), self.ok("V09")])

        assert any(p.startswith("V09") for p in got)

    def test_bad_verdict_is_reported(self):
        got = verify.check_results(self.SAMPLE, [self.ok("V01", "maybe"), self.ok("V02")])

        assert any("V01" in p and "maybe" in p for p in got)


class TestCli:
    @pytest.fixture
    def world(self, tmp_path):
        repo = tmp_path / "proj"
        repo.mkdir()
        (repo / "a.py").write_bytes(BLOB)
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x.io", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x.io"}
        for args in (["init", "-b", "main"], ["add", "-A"], ["commit", "-m", "one"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, env=env).stdout.strip()
        out = tmp_path / "home" / "proj"
        (out / "reports").mkdir(parents=True)
        (out / "facts.json").write_text(json.dumps({"repo": {"sha": sha, "path": str(repo), "remote": None}}))
        (out / "reports" / "entry.json").write_text(json.dumps(reports_of(4)["entry"]))
        buildlog.start(out, repo="proj", sha=sha, ref="main", version="1.0.0", options={})
        denv = {**env, "DOSSIER_HOME": str(tmp_path / "home"), "DOSSIER_CONFIG": str(tmp_path / "cfg.json"),
                "DOSSIER_CACHE": str(tmp_path / "cache")}

        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args, ], capture_output=True, text=True, env=denv, cwd=repo)

        return type("W", (), {"run": staticmethod(run), "out": out})

    def sample(self, world, *args):
        r = world.run("verify-sample", *args)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    def answers(self, world, sample, verdict="supported"):
        path = world.out / "answers.json"
        path.write_text(json.dumps([{"id": i["id"], "verdict": verdict, "reason": "r"} for i in sample["items"]]))
        return path

    def test_verify_sample_prints_items_and_records_the_seed(self, world):
        got = self.sample(world, "--per-report", "2")

        build = buildlog.load(world.out)
        rec = buildlog.latest(build, "check", "verify-sample")
        assert len(got["items"]) == 2
        assert got["items"][0]["code"][0]["text"].startswith("2: line 2")
        assert rec["details"]["seed"] == got["seed"]
        assert [i["id"] for i in rec["details"]["items"]] == ["V01", "V02"]

    def test_same_seed_gives_same_ids_and_claims(self, world):
        first = self.sample(world, "--per-report", "2")

        again = self.sample(world, "--per-report", "2", "--seed", first["seed"])

        assert [i["key"] for i in again["items"]] == [i["key"] for i in first["items"]]

    def test_verify_record_with_good_file_appends_results(self, world):
        sample = self.sample(world, "--per-report", "2")
        path = self.answers(world, sample)

        r = world.run("verify-record", "--results", str(path))

        rec = buildlog.latest(buildlog.load(world.out), "check", "verify")
        assert r.returncode == 0
        assert rec["counts"] == {"sampled": 2, "supported": 2, "not_supported": 0, "cannot_tell": 0}

    def test_verify_record_with_bad_file_exits_1_and_writes_nothing(self, world):
        sample = self.sample(world, "--per-report", "2")
        path = world.out / "answers.json"
        path.write_text(json.dumps([{"id": "V01", "verdict": "maybe", "reason": "r"}]))

        r = world.run("verify-record", "--results", str(path))

        assert r.returncode == 1
        assert "V01" in r.stderr and "V02" in r.stderr
        assert buildlog.latest(buildlog.load(world.out), "check", "verify") is None
