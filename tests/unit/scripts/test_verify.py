import verify

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
