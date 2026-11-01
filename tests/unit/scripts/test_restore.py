import restore

TOOLS = {"restore": [
    {"ecosystem": "python", "lockfile": "uv.lock", "command": ["uv", "sync", "--frozen"], "enabled": True},
    {"ecosystem": "npm", "lockfile": "package-lock.json", "command": ["npm", "ci"], "enabled": False},
]}
TRUSTED = {"trusted": True, "why": "tag v1", "default_branch": None}
UNTRUSTED = {"trusted": False, "why": "not a tag and not on the default branch main", "default_branch": "main"}
PLAN = [{"ecosystem": "python", "lockfile": "uv.lock", "command": ["x"], "enabled": True}]


def decide(plans=PLAN, state=None, answer=None, no_restore=False, trust=TRUSTED, allow_ref=False):
    return restore.decide(plans, state=state or {}, answer=answer, no_restore=no_restore, trust=trust, allow_ref=allow_ref)


class TestPlans:
    def test_only_root_lockfiles_in_the_tree(self):
        got = restore.plans(frozenset({"uv.lock", "sub/package-lock.json"}), TOOLS)

        assert [p["ecosystem"] for p in got] == ["python"]


class TestDecide:
    def test_no_plans_skips(self):
        assert "no lockfile" in decide(plans=[])["reason"]

    def test_no_restore_skips(self):
        assert "--no-restore" in decide(no_restore=True)["reason"]

    def test_untrusted_ref_skips_without_allow_ref(self):
        d = decide(trust=UNTRUSTED, answer="yes")

        assert (d["action"], "--allow-ref" in d["reason"]) == ("skip", True)

    def test_untrusted_ref_runs_with_allow_ref(self):
        assert decide(trust=UNTRUSTED, answer="yes", allow_ref=True)["action"] == "run"

    def test_answer_yes_runs_and_is_stored(self):
        d = decide(answer="yes")

        assert (d["action"], d["store"]) == ("run", "yes")

    def test_answer_no_skips_and_is_stored(self):
        d = decide(answer="no")

        assert (d["action"], d["store"]) == ("skip", "no")

    def test_stored_no_skips_with_hint(self):
        d = decide(state={"restore": {"answer": "no"}})

        assert d["action"] == "skip" and "--restore yes" in d["reason"]

    def test_stored_yes_covering_the_ecosystem_runs(self):
        assert decide(state={"restore": {"answer": "yes", "ecosystems": ["python"]}})["action"] == "run"

    def test_stored_yes_not_covering_a_new_ecosystem_asks_again(self):
        assert decide(state={"restore": {"answer": "yes", "ecosystems": ["npm"]}})["action"] == "ask"

    def test_nothing_stored_asks(self):
        assert decide()["action"] == "ask"
