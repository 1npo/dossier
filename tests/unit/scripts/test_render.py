import json

import render
import viewer


def cite(raw):
    return render.parse_cite(raw)


class TestCitesViewable:
    def test_source_file_is_viewable(self, make_cites):
        cites = make_cites({"src/app.py": b"print(1)\nprint(2)\n"})

        ok, reason = cites.viewable(cite("src/app.py:1-2"))

        assert ok
        assert reason == ""

    def test_commit_is_not_viewable(self, make_cites):
        cites = make_cites({})

        ok, _ = cites.viewable(cite("commit:" + "b" * 40))

        assert not ok

    def test_facts_citation_is_not_viewable(self, make_cites):
        cites = make_cites({})

        ok, _ = cites.viewable(cite("facts:git"))

        assert not ok

    def test_directory_is_not_viewable(self, make_cites):
        cites = make_cites({"src/app.py": b"x\n"}, dirs=["src"])

        ok, reason = cites.viewable(cite("src"))

        assert not ok
        assert reason == "directory"

    def test_unresolved_path_is_not_viewable(self, make_cites):
        cites = make_cites({})

        ok, reason = cites.viewable(cite("missing.py"))

        assert not ok
        assert reason == "unresolved"

    def test_binary_file_is_not_viewable(self, make_cites):
        cites = make_cites({"logo.dat": b"GIF89a\x00\x01\x02 rest"})

        ok, reason = cites.viewable(cite("logo.dat"))

        assert not ok
        assert reason == "binary file"

    def test_minified_file_is_not_viewable(self, make_cites):
        cites = make_cites({"dist/app.js": b"var a=1;" * 200 + b"\n"})

        ok, reason = cites.viewable(cite("dist/app.js"))

        assert not ok
        assert reason == "minified file"

    def test_empty_file_is_not_viewable(self, make_cites):
        cites = make_cites({"empty.py": b""})

        ok, reason = cites.viewable(cite("empty.py"))

        assert not ok
        assert reason == "empty file"

    def test_env_file_is_not_viewable(self, make_cites):
        cites = make_cites({".env": b"API_KEY=hunter2\n"})

        ok, reason = cites.viewable(cite(".env:1"))

        assert not ok
        assert reason == "may hold secrets"

    def test_key_file_in_a_subdirectory_is_not_viewable(self, make_cites):
        cites = make_cites({"deploy/server.pem": b"-----BEGIN PRIVATE KEY-----\nabc\n"})

        ok, _ = cites.viewable(cite("deploy/server.pem"))

        assert not ok

    def test_env_example_is_viewable(self, make_cites):
        cites = make_cites({".env.example": b"API_KEY=\n"})

        ok, _ = cites.viewable(cite(".env.example"))

        assert ok

    def test_public_key_is_viewable(self, make_cites):
        cites = make_cites({"keys/deploy.key.pub": b"ssh-ed25519 AAAA\n"})

        ok, _ = cites.viewable(cite("keys/deploy.key.pub"))

        assert ok

    def test_file_with_a_secret_hit_in_the_facts_is_not_viewable(self, make_cites):
        cites = make_cites({"src/config.py": b"TOKEN = 'abc'\n"}, secret_signals={"hits": [{"path": "src/config.py", "line": 1, "kind": "token"}], "sensitive_files": []})

        ok, reason = cites.viewable(cite("src/config.py:1"))

        assert not ok
        assert reason == "may hold secrets"

    def test_file_listed_as_sensitive_in_the_facts_is_not_viewable(self, make_cites):
        cites = make_cites({"conf/prod.ini": b"x=1\n"}, secret_signals={"hits": [], "sensitive_files": [{"path": "conf/prod.ini", "verdict": "x"}]})

        ok, _ = cites.viewable(cite("conf/prod.ini"))

        assert not ok

    def test_secret_prone_file_is_not_loaded_for_embedding(self, make_cites):
        cites = make_cites({".env": b"API_KEY=hunter2\n"})

        result = cites.source(".env")

        assert result == (None, "may hold secrets")
        assert cites.repo.reads == []


class TestNeverEmbedded:
    def build(self, make_cites):
        blobs = {".env": b"API_KEY=hunter2-planted\n", "id_rsa": b"-----BEGIN OPENSSH PRIVATE KEY-----\nplanted-key\n",
                 "logo.bin": b"\x00\x01planted-binary", "dist/app.min.js": b"var planted=1;" * 200 + b"\n",
                 "src/config.py": b"TOKEN = 'planted-token'\n", "src/app.py": b"print('fine')\n"}
        facts_secrets = {"hits": [{"path": "src/config.py", "line": 1, "kind": "token"}], "sensitive_files": []}
        cites = make_cites(blobs, dirs=["src"], secret_signals=facts_secrets)
        refs = render.Refs("overview", cites)
        refs.mark([".env:1", "id_rsa", "logo.bin", "dist/app.min.js", "src/config.py:1", "src", "src/app.py:1"])
        return cites

    def test_only_the_ordinary_source_file_is_planned(self, make_cites):
        cites = self.build(make_cites)

        cites.plan_view()

        assert list(cites.windows) == ["src/app.py"]

    def test_every_excluded_kind_is_counted_as_not_viewable(self, make_cites):
        cites = self.build(make_cites)

        cites.plan_view()
        refs = render.Refs("overview", cites)
        refs.mark([".env:1", "id_rsa", "logo.bin", "dist/app.min.js", "src/config.py:1", "src", "src/app.py:1"])

        assert cites.view_counts() == {"viewable": 1, "not_viewable": 6, "files_dropped_for_size": 0}

    def test_planted_contents_do_not_reach_the_embedded_data(self, make_cites):
        cites = self.build(make_cites)

        cites.plan_view()
        text = viewer.embed({p: {"lines": cites.source(p)[0]} for p in cites.windows}, cites.windows)

        assert "planted" not in text
        assert "hunter2" not in text
        assert "fine" in text

    def test_excluded_citations_carry_no_view_attributes_or_contents(self, make_cites):
        cites = self.build(make_cites)
        cites.plan_view()
        refs = render.Refs("overview", cites)

        markup = refs.mark([".env:1", "id_rsa", "logo.bin", "dist/app.min.js", "src/config.py:1", "src"]) + refs.listing()

        assert "data-view" not in markup
        assert "planted" not in markup


class TestRefsMark:
    def test_viewable_citation_carries_its_path_and_range(self, make_cites):
        cites = make_cites({"src/app.py": b"a\nb\nc\n"})
        refs = render.Refs("overview", cites)

        html = refs.mark(["src/app.py:2-3"])

        assert 'data-view="src/app.py" data-a="2" data-b="3"' in html

    def test_citation_without_lines_has_empty_range_attributes(self, make_cites):
        cites = make_cites({"src/app.py": b"a\nb\n"})
        refs = render.Refs("overview", cites)

        html = refs.mark(["src/app.py"])

        assert 'data-view="src/app.py" data-a="" data-b=""' in html

    def test_directory_tooltip_is_relative_and_does_not_open(self, make_cites):
        cites = make_cites({"src/app.py": b"a\n"}, dirs=["src"])
        refs = render.Refs("overview", cites)

        html = refs.mark(["src"])

        assert 'data-tip="directory src/, relative to the repo root"' in html
        assert "data-view" not in html
        assert "/repo" not in html

    def test_commit_keeps_its_anchor_and_does_not_open(self, make_cites):
        cites = make_cites({})
        refs = render.Refs("overview", cites)

        html = refs.mark(["commit:" + "b" * 40])

        assert 'href="#ref-overview-1"' in html
        assert "data-view" not in html

    def test_range_outside_the_embedded_window_does_not_open(self, make_cites):
        text = "".join(f"line {i}\n" for i in range(1, 4001)).encode()
        cites = make_cites({"big.py": text})
        refs = render.Refs("overview", cites)
        refs.mark(["big.py:10-20", "big.py:3000-3010", "big.py:3100-3110"])
        cites.plan_view()
        again = render.Refs("overview", cites)

        html = again.mark(["big.py:10-20", "big.py:3000-3010", "big.py:3100-3110"])

        assert cites.windows["big.py"] == (3000, 4000)
        assert html.count("data-view") == 2
        assert 'data-a="10"' not in html


class TestRefsListing:
    def test_listing_entry_carries_the_view_attributes_and_a_button(self, make_cites):
        cites = make_cites({"src/app.py": b"a\nb\n"})
        refs = render.Refs("overview", cites)
        refs.mark(["src/app.py:1-2"])

        html = refs.listing()

        assert '<li id="ref-overview-1" data-view="src/app.py" data-a="1" data-b="2">' in html
        assert 'data-open="overview-1"' in html

    def test_local_path_is_not_linked_for_a_directory(self, make_cites):
        cites = make_cites({"src/app.py": b"a\n"}, dirs=["src"])
        refs = render.Refs("overview", cites)
        refs.mark(["src"])

        html = refs.listing()

        assert "file://" not in html
        assert "/repo" not in html


class TestPlanView:
    def test_whole_files_need_no_second_pass(self, make_cites):
        cites = make_cites({"a.py": b"a\nb\n"})
        render.Refs("overview", cites).mark(["a.py:1"])

        dropped, stale = cites.plan_view()

        assert dropped == []
        assert not stale

    def test_uncovered_range_needs_a_second_pass(self, make_cites):
        text = "".join(f"line {i}\n" for i in range(1, 4001)).encode()
        cites = make_cites({"big.py": text})
        render.Refs("overview", cites).mark(["big.py:10-20", "big.py:3000-3010", "big.py:3100-3110"])

        dropped, stale = cites.plan_view()

        assert dropped == []
        assert stale

    def test_embedded_data_is_valid_json(self, make_cites):
        cites = make_cites({"a.html": b"<script>1</script>\n<!-- x -->\n"})
        render.Refs("overview", cites).mark(["a.html:1"])
        cites.plan_view()

        text = viewer.embed({p: {"lines": cites.source(p)[0]} for p in cites.windows}, cites.windows)

        assert json.loads(text)["a.html"]["lines"] == ["&lt;<i class=nt>script</i>&gt;<i class=m>1</i>&lt;/<i class=nt>script</i>&gt;", "<i class=c>&lt;!-- x --&gt;</i>"]
