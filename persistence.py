from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from game_logic import GameStatsSnapshot


def load_stats(path: Path) -> GameStatsSnapshot:
    if not path.exists():
        return GameStatsSnapshot()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return GameStatsSnapshot()

    if not isinstance(data, dict):
        return GameStatsSnapshot()

    return GameStatsSnapshot(
        high_score=_safe_int(data.get("high_score")),
        best_combo=_safe_int(data.get("best_combo")),
        games_played=_safe_int(data.get("games_played")),
        last_score=_safe_int(data.get("last_score")),
    )


def save_stats(path: Path, snapshot: GameStatsSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(snapshot), indent=2, ensure_ascii=True)
    path.write_text(payload + "\n", encoding="utf-8")


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
