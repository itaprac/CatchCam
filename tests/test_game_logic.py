import random
import unittest

from game_logic import (
    FallingObject,
    GameMode,
    GameState,
    GameStatsSnapshot,
    ObjectKind,
)


class GameStateTests(unittest.TestCase):
    def make_state(self) -> GameState:
        return GameState(width=640, height=480, rng=random.Random(123))

    def step(
        self,
        state: GameState,
        total_time: float,
        touch_points: list[tuple[float, float]] | None = None,
        person_present: bool = True,
    ) -> None:
        remaining = total_time
        while remaining > 0:
            delta = min(0.1, remaining)
            state.update(delta, touch_points or [], person_present)
            remaining -= delta

    def start_playing(self, state: GameState) -> None:
        state.start_countdown()
        self.step(state, state.countdown_seconds + 0.05, person_present=True)
        self.assertEqual(state.mode, GameMode.PLAYING)

    def test_waiting_to_countdown_to_playing(self) -> None:
        state = self.make_state()

        self.step(state, 0.6, person_present=True)
        self.assertEqual(state.mode, GameMode.WAITING_FOR_PLAYER)

        self.step(state, 0.5, person_present=True)
        self.assertEqual(state.mode, GameMode.COUNTDOWN)

        self.step(state, 3.1, person_present=True)
        self.assertEqual(state.mode, GameMode.PLAYING)

    def test_no_spawns_outside_playing_mode(self) -> None:
        state = self.make_state()

        self.step(state, 2.0, person_present=False)
        self.assertEqual(state.objects, [])

        state.start_countdown()
        self.step(state, 1.0, person_present=True)
        self.assertEqual(state.mode, GameMode.COUNTDOWN)
        self.assertEqual(state.objects, [])

        state.mode = GameMode.GAME_OVER
        self.step(state, 2.0, person_present=True)
        self.assertEqual(state.objects, [])

    def test_scores_by_object_type(self) -> None:
        state = self.make_state()
        self.start_playing(state)

        state.objects = [
            FallingObject(id=1, kind=ObjectKind.NORMAL, x=100.0, y=100.0, radius=20, speed=0.0),
            FallingObject(id=2, kind=ObjectKind.GOLD, x=180.0, y=100.0, radius=20, speed=0.0),
            FallingObject(id=3, kind=ObjectKind.FREEZE, x=260.0, y=100.0, radius=20, speed=0.0),
        ]

        state.update(0.1, [(100.0, 100.0)], person_present=True)
        self.assertEqual(state.score, 1)

        state.update(0.1, [(180.0, 100.0)], person_present=True)
        self.assertEqual(state.score, 4)

        state.update(0.1, [(260.0, 100.0)], person_present=True)
        self.assertEqual(state.score, 8)
        self.assertGreater(state.freeze_timer, 0.0)

    def test_combo_resets_after_timeout(self) -> None:
        state = self.make_state()
        self.start_playing(state)
        state.objects = [
            FallingObject(id=1, kind=ObjectKind.NORMAL, x=100.0, y=100.0, radius=20, speed=0.0)
        ]

        state.update(0.1, [(100.0, 100.0)], person_present=True)
        self.assertEqual(state.combo_count, 1)

        self.step(state, 1.25, person_present=True)
        self.assertEqual(state.combo_count, 0)
        self.assertEqual(state.combo_multiplier, 1)

    def test_bomb_applies_penalty_and_resets_combo(self) -> None:
        state = self.make_state()
        self.start_playing(state)
        state.score = 10
        state.combo_count = 4
        state.combo_multiplier = 2
        state._last_hit_age = 0.0
        state.objects = [
            FallingObject(id=1, kind=ObjectKind.BOMB, x=100.0, y=100.0, radius=20, speed=0.0)
        ]

        events = state.update(0.1, [(100.0, 100.0)], person_present=True)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, ObjectKind.BOMB)
        self.assertEqual(state.score, 8)
        self.assertEqual(state.combo_count, 0)
        self.assertEqual(state.special_hits[ObjectKind.BOMB], 1)

    def test_freeze_effect_expires(self) -> None:
        state = self.make_state()
        self.start_playing(state)
        state.objects = [
            FallingObject(id=1, kind=ObjectKind.FREEZE, x=100.0, y=100.0, radius=20, speed=0.0)
        ]

        state.update(0.1, [(100.0, 100.0)], person_present=True)
        self.assertTrue(state.is_freeze_active())

        self.step(state, 2.6, person_present=True)
        self.assertFalse(state.is_freeze_active())

    def test_phase_progression_depends_on_elapsed_time(self) -> None:
        state = self.make_state()
        self.start_playing(state)

        self.step(state, 20.1, person_present=True)
        self.assertEqual(state.current_phase(), 2)

        self.step(state, 20.0, person_present=True)
        self.assertEqual(state.current_phase(), 3)

    def test_tracking_loss_pauses_and_resumes_round(self) -> None:
        state = self.make_state()
        self.start_playing(state)

        state.update(0.1, [], person_present=False)
        self.assertEqual(state.mode, GameMode.PLAYING)

        state.update(0.1, [], person_present=False)
        state.update(0.1, [], person_present=False)
        state.update(0.1, [], person_present=False)
        self.assertEqual(state.mode, GameMode.PAUSED_TRACKING_LOST)

        state.update(0.1, [], person_present=True)
        self.assertEqual(state.mode, GameMode.PLAYING)

    def test_finishing_round_updates_high_score_and_best_combo(self) -> None:
        state = self.make_state()
        state.load_stats(GameStatsSnapshot(high_score=3, best_combo=2, games_played=7, last_score=1))
        self.start_playing(state)
        state.elapsed_time = 59.95
        state.objects = [
            FallingObject(id=1, kind=ObjectKind.NORMAL, x=100.0, y=100.0, radius=20, speed=0.0),
            FallingObject(id=2, kind=ObjectKind.NORMAL, x=180.0, y=100.0, radius=20, speed=0.0),
            FallingObject(id=3, kind=ObjectKind.NORMAL, x=260.0, y=100.0, radius=20, speed=0.0),
        ]

        state.update(0.1, [(100.0, 100.0), (180.0, 100.0), (260.0, 100.0)], person_present=True)

        self.assertEqual(state.mode, GameMode.GAME_OVER)
        self.assertGreaterEqual(state.high_score, 4)
        self.assertEqual(state.best_combo, 3)
        self.assertEqual(state.games_played, 8)
        self.assertEqual(state.last_score, state.score)

    def test_spawn_is_deterministic_for_seeded_rng(self) -> None:
        left = GameState(width=640, height=480, rng=random.Random(999))
        right = GameState(width=640, height=480, rng=random.Random(999))

        self.start_playing(left)
        self.start_playing(right)
        self.step(left, 0.7, person_present=True)
        self.step(right, 0.7, person_present=True)

        self.assertEqual(len(left.objects), 1)
        self.assertEqual(len(right.objects), 1)
        self.assertEqual(left.objects[0].kind, right.objects[0].kind)
        self.assertEqual(left.objects[0].radius, right.objects[0].radius)
        self.assertAlmostEqual(left.objects[0].x, right.objects[0].x)
        self.assertAlmostEqual(left.objects[0].speed, right.objects[0].speed)


if __name__ == "__main__":
    unittest.main()
