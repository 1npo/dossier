import json
import re

import gather
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


class TestCommitCalendar:
    PAL = {"a": "lang-1", "b": "lang-2"}

    def facts(self, daily):
        return {"daily": daily}

    def test_single_contributor_day_is_one_solid_colour(self):
        cell = render.day_cell({"a": 2}, 2, self.PAL, "day")
        assert "linear-gradient" not in cell and "var(--l1)" in cell

    def test_shared_day_is_striped_in_both_colours(self):
        cell = render.day_cell({"a": 1, "b": 1}, 1, self.PAL, "day")
        assert "linear-gradient" in cell and "var(--l1)" in cell and "var(--l2)" in cell

    def test_unknown_contributor_gets_the_grey(self):
        assert "var(--l8)" in render.day_cell({"zz": 1}, 1, self.PAL, "day")

    def test_empty_day_has_no_colour(self):
        assert "background" not in render.day_cell({}, 1, self.PAL, "day")

    DAILY = {"2026-01-05": {"a": 1}, "2026-03-09": {"a": 2, "b": 1}}

    def test_calendar_has_two_zoom_levels_and_starts_on_days(self):
        html = render.calendar_html(self.facts(self.DAILY), {"a": "A", "b": "B"}, self.PAL)
        assert html.count("data-zoom-level=") == 2
        assert 'data-zoom-start="1"' in html
        assert 'data-zoom-level="0" hidden' in html and 'data-zoom-level="1">' in html

    def test_legend_and_zoom_buttons_come_after_the_calendar(self):
        html = render.calendar_html(self.facts(self.DAILY), {"a": "A", "b": "B"}, self.PAL)
        assert html.rindex("data-zoom-level=") < html.index("llegend") < html.index("zoom-bar")

    def test_day_view_boxes_each_week(self):
        html = render.calendar_html(self.facts(self.DAILY), {"a": "A"}, self.PAL)
        level1 = html.split('data-zoom-level="1">')[1].split('class="llegend"')[0]
        assert level1.count('<div class="wk">') in (53, 54)
        assert all(w.count("<span class=\"cc") == 7 for w in level1.split('<div class="wk">')[1:])

    def test_cells_get_their_tooltip_from_the_calendar_data(self):
        html = render.calendar_html(self.facts(self.DAILY), {"a": "A"}, self.PAL)
        assert 'data-cal="2026-03-09"' in html and 'data-cal="2026-03"' in html

    def test_calendar_data_has_commits_and_lines_per_person_per_day(self):
        f = {"git": {"daily": {"2026-03-09": {"a": 2}}, "daily_lines": {"2026-03-09": {"a": [10, 4]}}, "tags": [{"name": "v1", "date": "2026-03-09"}]},
             "contributors": {"people": [{"id": "a", "name": "Ann"}]}}
        data = render.calendar_data(f)
        assert data["days"] == {"2026-03-09": {"a": [2, 10, 4]}} and data["people"]["a"][0] == "Ann" and data["tags"] == {"2026-03-09": ["v1"]}

    def test_calendar_without_daily_history_says_to_prepare_again(self):
        assert "prepare again" in render.calendar_html({}, {}, self.PAL)


class TestKnowledgeCard:
    def people(self, *names):
        return [{"id": f"{n}@x.io", "name": n, "short": n, "commits": 10, "last": "2026-05", "departed": False, "type": "human"} for n in names]

    def facts(self, people=None, files=None, **over):
        k = {"sha": "a" * 40, "date": "2026-06-01", "departed_months": 6, "recent_days": 365, "contributors": people or self.people("Ann", "Bob"), "others": None,
             "files": files if files is not None else [["src/a.py", 10, "2026-05", [[0, 10, 3, 1]]]], "trimmed": 0, "approx_files": 0, "attribute_excluded": 0, **over}
        return {"knowledge": k, "repo": {"short": "aaaaaaaaaa"}, "ownership": None,
                "contributors": {"people": [{"id": p["id"], "name": p["name"]} for p in k["contributors"]]}}

    def data(self, html):
        return json.loads(html.split('id="km-data">')[1].split("</script>")[0].replace("\\u003c", "<"))

    def test_card_without_knowledge_data_says_to_prepare_again(self):
        assert "prepare again" in render.knowledge_card({})

    def test_card_has_no_tiles_and_opens_on_the_files_view(self):
        html = render.knowledge_card(self.facts(), "<table id=people></table>")

        assert 'class="stats"' not in html
        assert html.index('id="km-pane-files"') < html.index('id="km-pane-people" hidden') < html.index("<table id=people>")
        assert re.findall(r'data-v="(people|files)" aria-pressed="(\w+)"', html) == [("files", "true"), ("people", "false")]

    def test_card_has_the_three_labelled_control_groups(self):
        html = render.knowledge_card(self.facts())

        assert all(f'aria-labelledby="km-{g}-l"' in html for g in ("metric", "view", "zoom"))
        assert html.count('data-v="99"') == 1 and html.count('data-v="mine"') == 1

    def test_data_is_embedded_as_json_with_every_less_than_escaped(self):
        html = render.knowledge_card(self.facts(files=[["a</script><b>.py", 1, "", []]]))

        body = html.split('id="km-data">')[1].split("</script>")[0]

        assert "<" not in body and self.data(html)["files"][0][0] == "a</script><b>.py"

    def test_people_get_the_chart_colours_by_number_and_others_the_grey(self):
        f = self.facts(others={"people": 3, "commits": 9})

        data = self.data(render.knowledge_card(f))

        assert [p["cls"] for p in data["contributors"]] == [1, 2] and data["others"]["cls"] == 8

    def test_a_person_keeps_the_colour_the_rest_of_the_page_gives_them(self):
        f = self.facts()
        f["ownership"] = {"people": [{"id": "Bob@x.io", "name": "Bob"}, {"id": "Ann@x.io", "name": "Ann"}]}

        data = self.data(render.knowledge_card(f))

        assert [p["cls"] for p in data["contributors"]] == [2, 1]

    def test_estimated_lines_are_announced_on_the_card(self):
        html = render.knowledge_card(self.facts(approx_files=1))

        assert "Estimated line shares" in html and "estimates for 1 of the 1 files" in html

    def test_dropped_files_are_announced_on_the_card(self):
        assert "Some files are not shown" in render.knowledge_card(self.facts(trimmed=4))

    def test_departed_and_at_risk_are_labelled_as_inferences_with_the_threshold(self):
        html = render.knowledge_card(self.facts())

        assert 'basis-inferred' in html and "6 months before HEAD (2026-06-01)" in html


class TestCompact:
    def test_numbers_are_shortened_to_k_and_m(self):
        assert [render.compact(n) for n in (999, 15_800, 2_500_000)] == ["999", "15.8k", "2.5M"]


class TestGathererFacts:
    def test_every_fact_key_points_at_gatherer_code(self):
        for key in render.FACT_INFO:
            a, b = render.gatherer_range(key)
            assert 1 <= a < b <= len(render.gatherer_source()), key

    def test_every_citable_fact_key_is_explained(self):
        assert set(render.FACT_KEYS) <= set(render.FACT_INFO)

    def test_fact_marker_opens_an_explanation_not_the_viewer(self, make_cites):
        refs = render.Refs("overview", make_cites({}))
        marker = refs.mark(["facts:git"])
        assert 'data-fact="git"' in marker and "data-view" not in marker

    def test_fact_reference_offers_the_gatherer_code(self, make_cites):
        refs = render.Refs("overview", make_cites({}))
        refs.mark(["facts:git"])
        assert f'data-view="{render.GATHERER_PATH}"' in refs.listing()


class TestReportLayout:
    def test_tracker_reports_have_no_summary_or_contents_card(self):
        assert set(render.BARE_REPORTS) == {"risks", "gaps", "corrections"}

    def test_renamed_reports_and_tracking_group(self):
        assert render.TITLES["overview"] == "This repository" and render.TITLES["risks"] == "Risks" and render.TITLES["gaps"] == "Gaps"
        assert dict(render.NAV_GROUPS)["Tracking"] == ["risks", "gaps", "corrections"]

    def test_knowledge_map_offers_lines_and_commits_only(self):
        assert [v for v, _ in render.KM_MEASURES] == ["lines", "commits"] and render.KM_START["metric"] == "lines"

    def test_cards_are_tinted_by_where_their_content_comes_from(self):
        assert 'class="card panel fact"' in render.card("T", "x")
        assert 'class="card panel llm"' in render.card("T", "x", kind="llm")
        assert 'class="card block llm ' in render.block_card("T", "x", "")


class TestManifestAuthor:
    def test_author_is_read_from_the_manifest(self):
        m = gather.parse_manifest("package.json", '{"name": "a", "author": {"name": "Ann"}}')
        assert m["author"] == "Ann"

    def test_zig_manifest_gives_name_and_version(self):
        m = gather.parse_manifest("build.zig.zon", '.{\n .name = .zapp,\n .version = "0.1.0",\n}\n')
        assert (m["ecosystem"], m["name"], m["version"]) == ("zig", "zapp", "0.1.0")
