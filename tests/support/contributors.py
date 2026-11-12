"""Contributor facts and history items for the tests of the Contributors card and its owner table."""


class ContributorsData:
    def facts(self):
        person = lambda i, n, t, c: {"id": i, "name": n, "type": t, "commits": c, "share_pct": 50.0, "first": "2025-01-01", "last": "2026-01-01",
                                     "recent_commits_12m": c, "assisted_commits": 0, "added": 10, "deleted": 2}
        return {"git": {"contributors": {"human": 1, "agent": 1, "bot": 0, "total": 2}, "commits_by_type": {"human": 5, "agent": 5, "bot": 0},
                        "agent_assisted_commits": 0, "agent_assisted_by": {}},
                "contributors": {"people": [person("ann@x.io", "Ann", "human", 5), person("claude@x.io", "Claude", "agent", 5)], "not_listed": 0},
                "ownership": None, "knowledge": None}

    def history(self, rule="one-human"):
        person = lambda i, n, t, c, oc, ol: {"kind": "person", "path": "", "person": i, "name": n, "type": t, "commits": c, "owned_commits": oc, "owned_lines": ol}
        return [{"kind": "meta", "owner_rule": rule}, person("ann@x.io", "Ann", "human", 5, 10, 100), person("claude@x.io", "Claude", "agent", 5, 0, 0),
                person("github:zed", "zed", "human", 0, 0, 0)]

    class Refs:
        def mark(self, cites):
            return ""
