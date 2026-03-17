from pathlib import Path
import tempfile
import unittest

from game_logic import GameStatsSnapshot
from persistence import load_stats, save_stats


class PersistenceTests(unittest.TestCase):
    def test_missing_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "stats.json"
            snapshot = load_stats(path)

        self.assertEqual(snapshot, GameStatsSnapshot())

    def test_invalid_json_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "stats.json"
            path.write_text("{not-json", encoding="utf-8")
            snapshot = load_stats(path)

        self.assertEqual(snapshot, GameStatsSnapshot())

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "stats.json"
            expected = GameStatsSnapshot(
                high_score=42,
                best_combo=9,
                games_played=5,
                last_score=31,
            )

            save_stats(path, expected)
            actual = load_stats(path)

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
