"""Unit tests for tools/golden.py: the masks, the compare verdict and the gatherer review file."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))  # until E1 puts tools/ on pytest's pythonpath

import golden  # noqa: E402

MASK = golden.MASK


def code_data(entries: dict) -> str:
    return '<script type="application/json" id="code-data">' + json.dumps(entries) + "</script>"


def write_capture(root: Path, skill: str, cases: dict, codes=None) -> Path:
    """A capture folder: manifest.json plus, per case, {relative path: text}."""
    root.mkdir(parents=True)
    manifest = {"skill": skill, "set": "fast", "cases": {c: (codes or {}).get(c, {"prepare": 0, "render": 0}) for c in cases}}
    (root / "manifest.json").write_text(json.dumps(manifest))
    for case, files in cases.items():
        for rel, text in files.items():
            p = root / case / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
    return root


class TestMaskPaths:
    def test_each_skill_path_becomes_a_placeholder(self):
        text = "ran /a/base/scripts/dossier.py and /b/skill/src"

        out = golden.mask_paths(text, ["/a/base", "/b/skill"])

        assert out == "ran <SKILL>/scripts/dossier.py and <SKILL>/src"

    def test_longer_path_is_replaced_before_its_prefix(self):
        out = golden.mask_paths("/x/skill-two/f", ["/x/skill", "/x/skill-two"])

        assert out == "<SKILL>/f"

    def test_empty_paths_are_ignored(self):
        assert golden.mask_paths("abc", [None, ""]) == "abc"


class TestMaskJson:
    def test_time_keys_are_masked_at_any_depth(self):
        obj = {"started": "t1", "a": [{"ended": "t2", "seconds": 1.5, "date": "d", "generated_at": "g", "checked_at": "c", "keep": 1}]}

        out = golden.mask_json(obj)

        assert out == {"started": MASK, "a": [{"ended": MASK, "seconds": MASK, "date": MASK, "generated_at": MASK, "checked_at": MASK, "keep": 1}]}

    def test_skill_object_is_masked_but_a_skill_string_is_kept(self):
        out = golden.mask_json({"details": {"skill": {"path": "/p", "commit": "abc", "dirty": False}}, "skill": "named"})

        assert out == {"details": {"skill": MASK}, "skill": "named"}

    def test_code_key_is_masked_only_in_extract_files(self):
        obj = {"adapters": {"python": {"code": "digest", "items": [1]}}}

        assert golden.mask_json(obj, extract=True) == {"adapters": {"python": {"code": MASK, "items": [1]}}}
        assert golden.mask_json(obj) == obj

    def test_input_is_not_changed(self):
        obj = {"started": "t"}

        golden.mask_json(obj)

        assert obj == {"started": "t"}


class TestReduceBuild:
    def test_records_keep_only_the_compared_keys(self):
        build = {"build_id": "x", "records": [{"step": "pin", "by": "prepare", "status": "ok", "reason": None, "started": "t",
                                               "tools": [{"name": "git"}], "details": {"checked_at": "c", "sha": "s"}}]}

        out = golden.reduce_build(build)

        assert out["records"] == [{"step": "pin", "status": "ok", "reason": None, "details": {"checked_at": MASK, "sha": "s"}}]
        assert out["build_id"] == "x"

    def test_build_id_time_is_masked_and_its_sha_kept(self):
        out = golden.reduce_build({"build_id": "20261111T214259Z-9a19743", "records": []})

        assert out["build_id"] == f"{MASK}-9a19743"


class TestMaskHtml:
    def test_build_stamps_are_masked(self):
        text = "<dd>2026-11-11 04:40 PM</dd><div class=\"muted\">09:05 AM</div><span>Last built 2026-01-02 11:00 AM</span>"

        out, _ = golden.mask_html(text)

        assert out == f"<dd>{MASK}</dd><div class=\"muted\">{MASK}</div><span>Last built {MASK}</span>"

    def test_portfolio_built_attribute_is_masked(self):
        out, _ = golden.mask_html('<a class="card" data-built="2026-11-11T21:43:21Z" data-name="p">')

        assert out == f'<a class="card" data-built="{MASK}" data-name="p">'

    def test_skill_line_is_masked_in_both_forms(self):
        text = "Done. Skill: abcdef1, uncommitted changes. <dt>Skill</dt><dd>1234567, UNMERGED</dd>"

        out, _ = golden.mask_html(text)

        assert out == f"Done. Skill: {MASK}. <dt>Skill</dt><dd>{MASK}</dd>"

    def test_gatherer_line_attributes_are_masked_and_others_kept(self):
        text = ('<li data-view="dossier-gatherer/gather.py" data-a="391" data-b="451">x</li>'
                '<li data-view="src/app.py" data-a="3" data-b="4">y</li>')

        out, _ = golden.mask_html(text)

        assert f'data-view="dossier-gatherer/gather.py" data-a="{MASK}" data-b="{MASK}"' in out
        assert 'data-view="src/app.py" data-a="3" data-b="4"' in out

    def test_gatherer_bodies_are_masked_and_returned_as_text(self):
        entries = {"dossier-gatherer/gather.py": {"total": 2, "start": 1, "lines": ['<span class="k">import</span> os', "x = 1 &lt; 2"]},
                   "src/app.py": {"total": 1, "start": 1, "lines": ["print()"]}}

        out, bodies = golden.mask_html(code_data(entries))

        assert bodies == {"dossier-gatherer/gather.py": ["(start 1, total 2)", "import os", "x = 1 < 2"]}
        data = json.loads(out[out.index(">") + 1:out.rindex("</script>")])
        assert data == {"dossier-gatherer/gather.py": MASK, "src/app.py": entries["src/app.py"]}


class TestCompare:
    def test_equal_captures_print_same_and_return_true(self, tmp_path):
        files = {"pyrepo": {"home/pyrepo/facts.json": '{"a": 1}', "home/pyrepo/dossier-pyrepo.html": "<p>x</p>"}}
        a = write_capture(tmp_path / "a", "/skill/a", files)
        b = write_capture(tmp_path / "b", "/skill/b", files)
        out = io.StringIO()

        same = golden.compare(a, b, out=out)

        assert same is True
        assert out.getvalue().splitlines() == ["SAME pyrepo", "SAME"]

    def test_masked_differences_are_the_same(self, tmp_path):
        a = write_capture(tmp_path / "a", "/skill/a", {"c": {"home/build.json": json.dumps({"records": [{"step": "pin", "status": "ok", "started": "1", "by": "x"}]}),
                                                             "home/x/extract/graph.json": '{"adapters": {"py": {"code": "aaa", "path": "/skill/a/scripts"}}}'}})
        b = write_capture(tmp_path / "b", "/skill/b", {"c": {"home/build.json": json.dumps({"records": [{"step": "pin", "status": "ok", "started": "2", "by": "y"}]}),
                                                             "home/x/extract/graph.json": '{"adapters": {"py": {"code": "bbb", "path": "/skill/b/scripts"}}}'}})

        assert golden.compare(a, b, out=io.StringIO()) is True

    def test_a_changed_value_is_reported_and_returns_false(self, tmp_path):
        a = write_capture(tmp_path / "a", "/s/a", {"c": {"home/facts.json": '{"files": 3}'}})
        b = write_capture(tmp_path / "b", "/s/b", {"c": {"home/facts.json": '{"files": 4}'}})
        out = io.StringIO()

        same = golden.compare(a, b, out=out)

        assert same is False
        text = out.getvalue()
        assert "DIFF c" in text and "differs: home/facts.json" in text and '- "files": 3' in text and '+ "files": 4' in text
        assert text.splitlines()[-1] == "DIFFERENT"

    def test_a_file_on_one_side_only_is_reported(self, tmp_path):
        a = write_capture(tmp_path / "a", "/s/a", {"c": {"home/one.json": "{}"}})
        b = write_capture(tmp_path / "b", "/s/b", {"c": {"home/one.json": "{}", "home/two.json": "{}"}})
        out = io.StringIO()

        assert golden.compare(a, b, out=out) is False
        assert "only in B: home/two.json" in out.getvalue()

    def test_different_exit_codes_are_reported(self, tmp_path):
        a = write_capture(tmp_path / "a", "/s/a", {"c": {}}, codes={"c": {"prepare": 0, "render": 0}})
        b = write_capture(tmp_path / "b", "/s/b", {"c": {}}, codes={"c": {"prepare": 0, "render": 1}})
        out = io.StringIO()

        assert golden.compare(a, b, out=out) is False
        assert "exit codes differ" in out.getvalue()


class TestCompareReview:
    def test_review_file_holds_the_unmasked_gatherer_diff(self, tmp_path):
        def page(first):
            return code_data({"dossier-gatherer/deps.py": {"total": 2, "start": 1, "lines": [first, "def f(): pass"]}})

        a = write_capture(tmp_path / "a", "/s/a", {"c": {"home/p.html": page("import os")}})
        b = write_capture(tmp_path / "b", "/s/b", {"c": {"home/p.html": page("from dossier.core import config")}})
        review = tmp_path / "review.diff"

        same = golden.compare(a, b, review, out=io.StringIO())

        assert same is True
        text = review.read_text()
        assert "-import os" in text and "+from dossier.core import config" in text and "def f(): pass" in text

    def test_review_defaults_to_a_file_in_b_and_is_empty_without_changes(self, tmp_path):
        a = write_capture(tmp_path / "a", "/s/a", {"c": {"home/p.html": "<p></p>"}})
        b = write_capture(tmp_path / "b", "/s/b", {"c": {"home/p.html": "<p></p>"}})

        golden.compare(a, b, out=io.StringIO())

        assert (b / "gatherer-review.diff").read_text() == ""


class TestMain:
    def test_compare_exit_codes(self, tmp_path):
        a = write_capture(tmp_path / "a", "/s/a", {"c": {"home/f.json": "1"}})
        b = write_capture(tmp_path / "b", "/s/b", {"c": {"home/f.json": "1"}})
        c = write_capture(tmp_path / "c", "/s/c", {"c": {"home/f.json": "2"}})

        assert golden.main(["compare", str(a), str(b)]) == 0
        assert golden.main(["compare", str(a), str(c)]) == 1
