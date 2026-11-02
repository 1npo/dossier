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
