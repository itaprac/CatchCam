from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Iterable


Color = tuple[int, int, int]

NEON_CYAN: Color = (255, 220, 90)
NEON_GOLD: Color = (90, 210, 255)
NEON_ICE: Color = (255, 240, 140)
NEON_RED: Color = (90, 90, 255)
NEON_WHITE: Color = (245, 245, 245)


class GameMode(str, Enum):
    WAITING_FOR_PLAYER = "waiting_for_player"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    PAUSED_TRACKING_LOST = "paused_tracking_lost"
    GAME_OVER = "game_over"


class ObjectKind(str, Enum):
    NORMAL = "normal"
    GOLD = "gold"
    BOMB = "bomb"
    FREEZE = "freeze"


SPECIAL_KINDS = (ObjectKind.GOLD, ObjectKind.FREEZE, ObjectKind.BOMB)


@dataclass(frozen=True)
class PhaseConfig:
    spawn_interval: float
    max_objects: int
    speed_range: tuple[int, int]
    weights: tuple[tuple[ObjectKind, float], ...]


PHASE_CONFIGS = {
    1: PhaseConfig(
        spawn_interval=0.65,
        max_objects=6,
        speed_range=(170, 270),
        weights=(
            (ObjectKind.NORMAL, 78.0),
            (ObjectKind.GOLD, 10.0),
            (ObjectKind.BOMB, 8.0),
            (ObjectKind.FREEZE, 4.0),
        ),
    ),
    2: PhaseConfig(
        spawn_interval=0.48,
        max_objects=8,
        speed_range=(210, 320),
        weights=(
            (ObjectKind.NORMAL, 70.0),
            (ObjectKind.GOLD, 12.0),
            (ObjectKind.BOMB, 11.0),
            (ObjectKind.FREEZE, 7.0),
        ),
    ),
    3: PhaseConfig(
        spawn_interval=0.36,
        max_objects=10,
        speed_range=(250, 390),
        weights=(
            (ObjectKind.NORMAL, 63.0),
            (ObjectKind.GOLD, 12.0),
            (ObjectKind.BOMB, 17.0),
            (ObjectKind.FREEZE, 8.0),
        ),
    ),
}


OBJECT_COLORS: dict[ObjectKind, Color] = {
    ObjectKind.NORMAL: NEON_CYAN,
    ObjectKind.GOLD: NEON_GOLD,
    ObjectKind.BOMB: NEON_RED,
    ObjectKind.FREEZE: NEON_ICE,
}


@dataclass
class FallingObject:
    id: int
    kind: ObjectKind
    x: float
    y: float
    radius: int
    speed: float


@dataclass
class HitEvent:
    kind: ObjectKind
    x: float
    y: float
    points: int
    combo_count: int
    combo_multiplier: int
    message: str
    penalty: bool = False


@dataclass
class GameStatsSnapshot:
    high_score: int = 0
    best_combo: int = 0
    games_played: int = 0
    last_score: int = 0


@dataclass
class FloatingText:
    text: str
    x: float
    y: float
    color: Color
    scale: float = 0.8
    duration: float = 0.8
    age: float = 0.0
    drift_y: float = 42.0


@dataclass
class RingEffect:
    x: float
    y: float
    color: Color
    start_radius: float = 14.0
    end_radius: float = 72.0
    duration: float = 0.35
    age: float = 0.0


@dataclass
class ScreenFlash:
    color: Color
    duration: float = 0.22
    max_alpha: float = 0.28
    age: float = 0.0


@dataclass
class GameState:
    width: int
    height: int
    duration_seconds: float = 60.0
    countdown_seconds: float = 3.0
    presence_hold_seconds: float = 1.0
    tracking_grace_seconds: float = 0.35
    combo_timeout_seconds: float = 1.2
    freeze_duration_seconds: float = 2.5
    freeze_speed_multiplier: float = 0.6
    freeze_spawn_multiplier: float = 1.35
    normal_collision_padding: float = 45.0
    bomb_collision_padding: float = 32.0
    radius_range: tuple[int, int] = (20, 35)
    rng: random.Random = field(default_factory=random.Random)
    score: int = 0
    elapsed_time: float = 0.0
    spawn_timer: float = 0.0
    mode: GameMode = GameMode.WAITING_FOR_PLAYER
    countdown_timer: float = 3.0
    presence_timer: float = 0.0
    tracking_lost_time: float = 0.0
    freeze_timer: float = 0.0
    combo_count: int = 0
    combo_multiplier: int = 1
    round_best_combo: int = 0
    high_score: int = 0
    best_combo: int = 0
    games_played: int = 0
    last_score: int = 0
    phase: int = 1
    objects: list[FallingObject] = field(default_factory=list)
    floating_texts: list[FloatingText] = field(default_factory=list)
    ring_effects: list[RingEffect] = field(default_factory=list)
    screen_flashes: list[ScreenFlash] = field(default_factory=list)
    special_hits: dict[ObjectKind, int] = field(
        default_factory=lambda: {kind: 0 for kind in SPECIAL_KINDS}
    )
    _last_hit_age: float | None = None
    _next_object_id: int = 0

    def set_dimensions(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def reset_for_new_round(self) -> None:
        self.score = 0
        self.elapsed_time = 0.0
        self.spawn_timer = 0.0
        self.mode = GameMode.WAITING_FOR_PLAYER
        self.countdown_timer = self.countdown_seconds
        self.presence_timer = 0.0
        self.tracking_lost_time = 0.0
        self.freeze_timer = 0.0
        self.combo_count = 0
        self.combo_multiplier = 1
        self.round_best_combo = 0
        self.phase = 1
        self.objects.clear()
        self.floating_texts.clear()
        self.ring_effects.clear()
        self.screen_flashes.clear()
        self.special_hits = {kind: 0 for kind in SPECIAL_KINDS}
        self._last_hit_age = None

    def start_countdown(self) -> None:
        self.mode = GameMode.COUNTDOWN
        self.countdown_timer = self.countdown_seconds
        self.presence_timer = 0.0
        self.tracking_lost_time = 0.0
        self.spawn_timer = 0.0

    def load_stats(self, snapshot: GameStatsSnapshot) -> None:
        self.high_score = snapshot.high_score
        self.best_combo = snapshot.best_combo
        self.games_played = snapshot.games_played
        self.last_score = snapshot.last_score

    def build_stats_snapshot(self) -> GameStatsSnapshot:
        return GameStatsSnapshot(
            high_score=self.high_score,
            best_combo=self.best_combo,
            games_played=self.games_played,
            last_score=self.last_score,
        )

    def current_phase(self) -> int:
        if self.elapsed_time >= 40.0:
            return 3
        if self.elapsed_time >= 20.0:
            return 2
        return 1

    def remaining_time(self) -> float:
        return max(0.0, self.duration_seconds - self.elapsed_time)

    def is_freeze_active(self) -> bool:
        return self.freeze_timer > 0.0

    def update(
        self,
        delta_time: float,
        touch_points: Iterable[tuple[float, float]],
        person_present: bool,
    ) -> list[HitEvent]:
        delta_time = max(0.0, min(delta_time, 0.1))
        self._update_effects(delta_time)

        if self.mode == GameMode.GAME_OVER or delta_time <= 0.0:
            return []

        if self.mode == GameMode.WAITING_FOR_PLAYER:
            self._update_waiting(delta_time, person_present)
            return []

        if self.mode == GameMode.COUNTDOWN:
            self._update_countdown(delta_time, person_present)
            return []

        if self.mode == GameMode.PAUSED_TRACKING_LOST:
            self._update_paused(person_present)
            return []

        return self._update_playing(delta_time, list(touch_points), person_present)

    def _update_waiting(self, delta_time: float, person_present: bool) -> None:
        self.phase = 1
        if person_present:
            self.presence_timer += delta_time
            if self.presence_timer >= self.presence_hold_seconds:
                self.start_countdown()
        else:
            self.presence_timer = 0.0

    def _update_countdown(self, delta_time: float, person_present: bool) -> None:
        if not person_present:
            self.tracking_lost_time += delta_time
            if self.tracking_lost_time > self.tracking_grace_seconds:
                self.reset_for_new_round()
            return

        self.tracking_lost_time = 0.0
        self.countdown_timer = max(0.0, self.countdown_timer - delta_time)
        if self.countdown_timer <= 0.0:
            self.mode = GameMode.PLAYING
            self.spawn_timer = 0.0

    def _update_paused(self, person_present: bool) -> None:
        if person_present:
            self.mode = GameMode.PLAYING
            self.tracking_lost_time = 0.0

    def _update_playing(
        self,
        delta_time: float,
        touch_points: list[tuple[float, float]],
        person_present: bool,
    ) -> list[HitEvent]:
        if not person_present:
            self.tracking_lost_time += delta_time
            if self.tracking_lost_time > self.tracking_grace_seconds:
                self.mode = GameMode.PAUSED_TRACKING_LOST
            return []

        self.tracking_lost_time = 0.0

        effective_delta = min(delta_time, self.remaining_time())
        if effective_delta <= 0.0:
            self._finish_round()
            return []

        if self.freeze_timer > 0.0:
            self.freeze_timer = max(0.0, self.freeze_timer - effective_delta)

        self.elapsed_time += effective_delta
        self.phase = self.current_phase()
        self._update_combo_timeout(effective_delta)
        self._move_objects(effective_delta)
        self._despawn_outside_objects()
        events = self._collect_hits(touch_points)
        self._spawn_objects(effective_delta)

        if self.elapsed_time >= self.duration_seconds:
            self.elapsed_time = self.duration_seconds
            self._finish_round()

        return events

    def _update_effects(self, delta_time: float) -> None:
        self.floating_texts = [
            effect
            for effect in self.floating_texts
            if self._advance_effect(effect, delta_time)
        ]
        self.ring_effects = [
            effect for effect in self.ring_effects if self._advance_effect(effect, delta_time)
        ]
        self.screen_flashes = [
            effect
            for effect in self.screen_flashes
            if self._advance_effect(effect, delta_time)
        ]

    @staticmethod
    def _advance_effect(effect: FloatingText | RingEffect | ScreenFlash, delta_time: float) -> bool:
        effect.age += delta_time
        return effect.age < effect.duration

    def _update_combo_timeout(self, delta_time: float) -> None:
        if self.combo_count <= 0 or self._last_hit_age is None:
            return

        self._last_hit_age += delta_time
        if self._last_hit_age > self.combo_timeout_seconds:
            self._reset_combo()

    def _move_objects(self, delta_time: float) -> None:
        speed_multiplier = self.freeze_speed_multiplier if self.is_freeze_active() else 1.0
        for falling_object in self.objects:
            falling_object.y += falling_object.speed * speed_multiplier * delta_time

    def _despawn_outside_objects(self) -> None:
        self.objects = [
            falling_object
            for falling_object in self.objects
            if falling_object.y - falling_object.radius <= self.height
        ]

    def _collect_hits(self, touch_points: list[tuple[float, float]]) -> list[HitEvent]:
        if not touch_points:
            return []

        events: list[HitEvent] = []
        remaining_objects: list[FallingObject] = []
        for falling_object in self.objects:
            collision_padding = self._collision_padding_for(falling_object.kind)
            hit = any(
                self._distance(falling_object.x, falling_object.y, point_x, point_y)
                <= falling_object.radius + collision_padding
                for point_x, point_y in touch_points
            )
            if hit:
                events.append(self._apply_hit(falling_object))
            else:
                remaining_objects.append(falling_object)

        self.objects = remaining_objects
        return events

    def _apply_hit(self, falling_object: FallingObject) -> HitEvent:
        if falling_object.kind == ObjectKind.BOMB:
            penalty = 2
            self.score = max(0, self.score - penalty)
            self.special_hits[ObjectKind.BOMB] += 1
            self._reset_combo()
            self.ring_effects.append(
                RingEffect(x=falling_object.x, y=falling_object.y, color=OBJECT_COLORS[ObjectKind.BOMB])
            )
            self.screen_flashes.append(ScreenFlash(color=OBJECT_COLORS[ObjectKind.BOMB], max_alpha=0.32))
            self.floating_texts.append(
                FloatingText(
                    text="OUCH -2",
                    x=falling_object.x,
                    y=falling_object.y,
                    color=OBJECT_COLORS[ObjectKind.BOMB],
                    scale=0.85,
                    duration=0.9,
                )
            )
            return HitEvent(
                kind=ObjectKind.BOMB,
                x=falling_object.x,
                y=falling_object.y,
                points=-penalty,
                combo_count=0,
                combo_multiplier=1,
                message="OUCH -2",
                penalty=True,
            )

        self.combo_count += 1
        self.combo_multiplier = self._combo_multiplier_for(self.combo_count)
        self.round_best_combo = max(self.round_best_combo, self.combo_count)
        self._last_hit_age = 0.0

        base_points = self._base_points_for(falling_object.kind)
        awarded_points = base_points * self.combo_multiplier
        self.score += awarded_points

        if falling_object.kind in SPECIAL_KINDS:
            self.special_hits[falling_object.kind] += 1

        if falling_object.kind == ObjectKind.FREEZE:
            self.freeze_timer = max(self.freeze_timer, self.freeze_duration_seconds)
            self.screen_flashes.append(
                ScreenFlash(color=OBJECT_COLORS[ObjectKind.FREEZE], duration=0.18, max_alpha=0.2)
            )

        color = OBJECT_COLORS[falling_object.kind]
        self.ring_effects.append(RingEffect(x=falling_object.x, y=falling_object.y, color=color))
        self.floating_texts.append(
            FloatingText(
                text=f"+{awarded_points}",
                x=falling_object.x,
                y=falling_object.y,
                color=color,
            )
        )
        if self.combo_multiplier > 1:
            self.floating_texts.append(
                FloatingText(
                    text=f"COMBO x{self.combo_multiplier}",
                    x=falling_object.x,
                    y=falling_object.y - 22.0,
                    color=NEON_WHITE,
                    scale=0.6,
                    duration=0.7,
                )
            )

        return HitEvent(
            kind=falling_object.kind,
            x=falling_object.x,
            y=falling_object.y,
            points=awarded_points,
            combo_count=self.combo_count,
            combo_multiplier=self.combo_multiplier,
            message=f"+{awarded_points}",
        )

    def _spawn_objects(self, delta_time: float) -> None:
        phase_config = self._phase_config()
        self.spawn_timer += delta_time
        spawn_interval = phase_config.spawn_interval
        if self.is_freeze_active():
            spawn_interval *= self.freeze_spawn_multiplier

        while (
            spawn_interval > 0.0
            and self.spawn_timer >= spawn_interval
            and len(self.objects) < phase_config.max_objects
            and self.width > 0
            and self.height > 0
        ):
            self.spawn_timer -= spawn_interval
            self.objects.append(self._create_object(phase_config))

    def _create_object(self, phase_config: PhaseConfig) -> FallingObject:
        min_radius, max_radius = self.radius_range
        radius = self.rng.randint(min_radius, max_radius)
        if self.width <= radius * 2:
            x = max(0.0, self.width / 2.0)
        else:
            x = self.rng.uniform(radius, self.width - radius)

        speed = self.rng.uniform(*phase_config.speed_range)
        kind = self._choose_object_kind(phase_config)

        self._next_object_id += 1
        return FallingObject(
            id=self._next_object_id,
            kind=kind,
            x=x,
            y=-radius,
            radius=radius,
            speed=speed,
        )

    def _choose_object_kind(self, phase_config: PhaseConfig) -> ObjectKind:
        weighted_kinds = []
        total_weight = 0.0
        for kind, weight in phase_config.weights:
            if kind == ObjectKind.BOMB and self.elapsed_time < 5.0:
                continue
            weighted_kinds.append((kind, weight))
            total_weight += weight

        if total_weight <= 0.0:
            return ObjectKind.NORMAL

        roll = self.rng.uniform(0.0, total_weight)
        cumulative = 0.0
        for kind, weight in weighted_kinds:
            cumulative += weight
            if roll <= cumulative:
                return kind
        return weighted_kinds[-1][0]

    def _finish_round(self) -> None:
        self.mode = GameMode.GAME_OVER
        self.last_score = self.score
        self.high_score = max(self.high_score, self.score)
        self.best_combo = max(self.best_combo, self.round_best_combo)
        self.games_played += 1
        self.combo_count = 0
        self.combo_multiplier = 1
        self._last_hit_age = None

    def _reset_combo(self) -> None:
        self.combo_count = 0
        self.combo_multiplier = 1
        self._last_hit_age = None

    def _phase_config(self) -> PhaseConfig:
        self.phase = self.current_phase()
        return PHASE_CONFIGS[self.phase]

    @staticmethod
    def _base_points_for(kind: ObjectKind) -> int:
        return {
            ObjectKind.NORMAL: 1,
            ObjectKind.GOLD: 3,
            ObjectKind.FREEZE: 2,
            ObjectKind.BOMB: -2,
        }[kind]

    def _collision_padding_for(self, kind: ObjectKind) -> float:
        if kind == ObjectKind.BOMB:
            return self.bomb_collision_padding
        return self.normal_collision_padding

    @staticmethod
    def _combo_multiplier_for(combo_count: int) -> int:
        if combo_count >= 10:
            return 4
        if combo_count >= 6:
            return 3
        if combo_count >= 3:
            return 2
        return 1

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
