import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2].parent / "scripts"))
import components  # noqa: E402


class TestChunkLines:
    CHUNKS = {"chunks": [{"files": [{"path": "a.py", "lines": 10}, {"path": "big.py", "lines": 5}]},
                         {"files": [{"path": "big.py", "lines": 7}]}]}

    def test_sums_the_segments_of_a_file_split_across_chunks(self):
        assert components.chunk_lines(self.CHUNKS) == {"a.py": 10, "big.py": 12}

    def test_missing_chunks_give_no_lines(self):
        assert components.chunk_lines({}) == {}

    def test_file_lines_prefers_the_lines_filled_in_when_the_dossier_is_loaded(self):
        facts = {"file_lines": {"a.py": 3}, "chunks": {"mode": "single"}}

        assert components.file_lines(facts) == {"a.py": 3}


class TestBracketedPaths:
    def test_a_next_folder_matches_as_a_directory(self):
        assert components.match_score("apps/a/[id]/page.tsx", "apps/a/[id]/") == (1, 3)

    def test_a_next_folder_matches_a_glob_beneath_it(self):
        assert components.match_score("apps/a/[id]/page.tsx", "apps/a/[id]/*") == (2, len("apps/a/[id]/*"))

    def test_the_file_itself_matches_exactly(self):
        assert components.match_score("apps/a/[id]/page.tsx", "apps/a/[id]/page.tsx") == (3, len("apps/a/[id]/page.tsx"))

    def test_a_real_character_class_still_works(self):
        assert components.match_score("src/a.py", "src/[ab].py") == (2, len("src/[ab].py"))
        assert components.match_score("src/c.py", "src/[ab].py") is None

    def test_python_patterns_score_as_before(self):
        assert components.match_score("src/app/x.py", "src/app/") == (1, 2)
        assert components.match_score("scripts/a.sh", "scripts/*.sh") == (2, len("scripts/*.sh"))
        assert components.match_score("src/app/x.py", "src/other/") is None

    def test_a_citation_with_brackets_in_its_path_is_parsed(self):
        assert components.parse_paths("[[apps/a/[id]/page.tsx:1-5|page]], `src/`") == ["apps/a/[id]/page.tsx", "src/"]

    def test_two_citations_in_one_cell_are_not_run_together(self):
        assert components.parse_paths("[[a.py]] [[b.py]]") == ["[[a.py]] [[b.py]]"]

    def test_plain_citations_parse_as_before(self):
        assert components.parse_paths("[[src/a.py:3|a]], [[src/b.py]]") == ["src/a.py", "src/b.py"]
