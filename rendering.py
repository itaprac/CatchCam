from __future__ import annotations

import math

import cv2
import numpy as np

from game_logic import (
    GameMode,
    GameState,
    NEON_CYAN,
    NEON_GOLD,
    NEON_ICE,
    NEON_RED,
    NEON_WHITE,
    OBJECT_COLORS,
    ObjectKind,
)


TEXT_COLOR = NEON_WHITE
TEXT_SHADOW = (18, 22, 28)
PANEL_FILL = (26, 31, 38)
PANEL_BORDER = (70, 95, 120)
TIME_BG = (46, 52, 62)
HUD_ACCENT = (120, 185, 255)


def draw_text(
    frame: np.ndarray,
    text: str,
    position: tuple[int, int],
    scale: float = 0.8,
    color: tuple[int, int, int] = TEXT_COLOR,
    thickness: int = 2,
) -> None:
    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_DUPLEX,
        scale,
        TEXT_SHADOW,
        thickness + 2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_DUPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_background_hud(frame: np.ndarray, state: GameState, person_present: bool) -> None:
    frame_height, frame_width = frame.shape[:2]
    _draw_panel(frame, (18, 16), (frame_width - 18, 126), alpha=0.36)
    _draw_time_bar(frame, state, (30, 86), frame_width - 60)

    draw_text(frame, f"WYNIK {state.score}", (34, 54), scale=0.95)
    draw_text(frame, f"REKORD {state.high_score}", (250, 54), scale=0.72, color=HUD_ACCENT)

    combo_label = f"COMBO x{state.combo_multiplier}" if state.combo_count > 0 else "COMBO READY"
    combo_color = NEON_GOLD if state.combo_multiplier > 1 else (200, 210, 220)
    draw_text(frame, combo_label, (34, 116), scale=0.68, color=combo_color)
    draw_text(frame, f"SERIA {state.combo_count}", (250, 116), scale=0.68)
    draw_text(frame, f"CZAS {int(math.ceil(state.remaining_time()))}", (frame_width - 180, 54), scale=0.9)
    draw_text(frame, f"FAZA {state.phase}", (frame_width - 150, 116), scale=0.68, color=_phase_color(state.phase))

    status_text, status_color = _status_label(state, person_present)
    draw_text(frame, status_text, (frame_width - 330, 54), scale=0.68, color=status_color)

    if state.is_freeze_active():
        _draw_badge(frame, "FREEZE", (frame_width - 310, 82), NEON_ICE)

    if state.combo_count >= 3:
        _draw_badge(frame, f"x{state.combo_multiplier}", (frame_width - 210, 82), NEON_GOLD)

    draw_text(frame, "R restart   Q / ESC wyjscie", (28, frame_height - 22), scale=0.5, color=(205, 210, 220), thickness=1)


def draw_falling_objects(frame: np.ndarray, state: GameState) -> None:
    glow_overlay = frame.copy()

    for falling_object in state.objects:
        color = OBJECT_COLORS[falling_object.kind]
        center = (int(falling_object.x), int(falling_object.y))
        if falling_object.kind == ObjectKind.BOMB:
            cv2.circle(glow_overlay, center, falling_object.radius + 12, color, -1, cv2.LINE_AA)
            cv2.circle(frame, center, falling_object.radius, (18, 22, 26), -1, cv2.LINE_AA)
            cv2.circle(frame, center, falling_object.radius + 2, color, 3, cv2.LINE_AA)
            cv2.line(
                frame,
                (center[0] - falling_object.radius // 2, center[1] - falling_object.radius // 2),
                (center[0] + falling_object.radius // 2, center[1] + falling_object.radius // 2),
                color,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (center[0] - falling_object.radius // 2, center[1] + falling_object.radius // 2),
                (center[0] + falling_object.radius // 2, center[1] - falling_object.radius // 2),
                color,
                2,
                cv2.LINE_AA,
            )
            continue

        glow_radius = falling_object.radius + (16 if falling_object.kind != ObjectKind.NORMAL else 10)
        cv2.circle(glow_overlay, center, glow_radius, color, -1, cv2.LINE_AA)
        cv2.circle(frame, center, falling_object.radius, color, -1, cv2.LINE_AA)
        cv2.circle(frame, center, falling_object.radius, NEON_WHITE, 2, cv2.LINE_AA)
        highlight_center = (
            int(falling_object.x - falling_object.radius * 0.35),
            int(falling_object.y - falling_object.radius * 0.35),
        )
        cv2.circle(frame, highlight_center, max(3, falling_object.radius // 4), (255, 255, 255), -1, cv2.LINE_AA)

    cv2.addWeighted(glow_overlay, 0.14, frame, 0.86, 0.0, frame)


def draw_hit_effects(frame: np.ndarray, state: GameState) -> None:
    for flash in state.screen_flashes:
        intensity = (1.0 - (flash.age / flash.duration)) * flash.max_alpha
        overlay = frame.copy()
        overlay[:] = flash.color
        cv2.addWeighted(overlay, intensity, frame, 1.0 - intensity, 0.0, frame)

    for ring in state.ring_effects:
        progress = ring.age / ring.duration
        radius = int(ring.start_radius + (ring.end_radius - ring.start_radius) * progress)
        thickness = max(1, int(4 * (1.0 - progress)))
        overlay = frame.copy()
        cv2.circle(overlay, (int(ring.x), int(ring.y)), radius, ring.color, thickness, cv2.LINE_AA)
        alpha = max(0.0, 0.4 * (1.0 - progress))
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0.0, frame)

    for floating_text in state.floating_texts:
        progress = floating_text.age / floating_text.duration
        y = int(floating_text.y - floating_text.drift_y * progress)
        draw_text(
            frame,
            floating_text.text,
            (int(floating_text.x - 28), y),
            scale=floating_text.scale,
            color=floating_text.color,
            thickness=2 if floating_text.scale >= 0.75 else 1,
        )


def draw_game_state_overlays(frame: np.ndarray, state: GameState, person_present: bool) -> None:
    if state.mode == GameMode.WAITING_FOR_PLAYER:
        _draw_waiting_overlay(frame, state, person_present)
    elif state.mode == GameMode.COUNTDOWN:
        _draw_countdown_overlay(frame, state)
    elif state.mode == GameMode.PAUSED_TRACKING_LOST:
        _draw_paused_overlay(frame)
    elif state.mode == GameMode.GAME_OVER:
        _draw_game_over_overlay(frame, state)


def _draw_time_bar(frame: np.ndarray, state: GameState, position: tuple[int, int], width: int) -> None:
    x, y = position
    bar_height = 18
    remaining_ratio = 1.0 if state.duration_seconds <= 0 else state.remaining_time() / state.duration_seconds
    color = _phase_color(state.phase)

    cv2.rectangle(frame, (x, y), (x + width, y + bar_height), TIME_BG, -1, cv2.LINE_AA)
    cv2.rectangle(
        frame,
        (x, y),
        (x + int(width * remaining_ratio), y + bar_height),
        color,
        -1,
        cv2.LINE_AA,
    )
    cv2.rectangle(frame, (x, y), (x + width, y + bar_height), (210, 220, 230), 1, cv2.LINE_AA)


def _draw_waiting_overlay(frame: np.ndarray, state: GameState, person_present: bool) -> None:
    progress = min(1.0, state.presence_timer / max(state.presence_hold_seconds, 0.001))
    _draw_center_panel(frame, 620, 270)
    draw_text(frame, "SPADAJACE KULKI", _centered_text(frame, "SPADAJACE KULKI", 1.1, -78), scale=1.1, color=NEON_CYAN)
    draw_text(frame, "LAP kulki dlonmi. UNIKAJ bomb. Zlap freeze, zeby zwolnic tempo.", _centered_text(frame, "LAP kulki dlonmi. UNIKAJ bomb. Zlap freeze, zeby zwolnic tempo.", 0.56, -18), scale=0.56)
    draw_text(frame, f"Rekord: {state.high_score}   Najlepsze combo: {state.best_combo}", _centered_text(frame, f"Rekord: {state.high_score}   Najlepsze combo: {state.best_combo}", 0.62, 24), scale=0.62, color=HUD_ACCENT)
    instruction = "Stoj w kadrze, aby zaczac" if not person_present else "Kalibracja gracza..."
    draw_text(frame, instruction, _centered_text(frame, instruction, 0.72, 74), scale=0.72, color=NEON_GOLD if person_present else TEXT_COLOR)
    _draw_progress_bar(frame, progress, y_offset=104)


def _draw_countdown_overlay(frame: np.ndarray, state: GameState) -> None:
    number = max(1, int(math.ceil(state.countdown_timer)))
    pulse = 1.0 + 0.18 * math.sin((state.countdown_seconds - state.countdown_timer) * 8.0)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), (18, 22, 28), -1)
    cv2.addWeighted(overlay, 0.18, frame, 0.82, 0.0, frame)
    draw_text(frame, "PRZYGOTUJ SIE", _centered_text(frame, "PRZYGOTUJ SIE", 0.8, -110), scale=0.8, color=NEON_GOLD)
    draw_text(frame, str(number), _centered_text(frame, str(number), 2.5 * pulse, 10), scale=2.5 * pulse, color=NEON_CYAN, thickness=4)


def _draw_paused_overlay(frame: np.ndarray) -> None:
    _draw_center_panel(frame, 470, 180)
    draw_text(frame, "PAUZA TRACKINGU", _centered_text(frame, "PAUZA TRACKINGU", 0.9, -24), scale=0.9, color=NEON_RED)
    draw_text(frame, "Wroc do kadru, a runda ruszy dalej.", _centered_text(frame, "Wroc do kadru, a runda ruszy dalej.", 0.62, 30), scale=0.62)


def _draw_game_over_overlay(frame: np.ndarray, state: GameState) -> None:
    _draw_center_panel(frame, 640, 320)
    draw_text(frame, "KONIEC GRY", _centered_text(frame, "KONIEC GRY", 1.1, -102), scale=1.1, color=NEON_RED)
    draw_text(frame, f"Wynik: {state.score}", _centered_text(frame, f"Wynik: {state.score}", 0.92, -34), scale=0.92, color=NEON_WHITE)
    draw_text(frame, f"Rekord: {state.high_score}", _centered_text(frame, f"Rekord: {state.high_score}", 0.72, 14), scale=0.72, color=HUD_ACCENT)
    draw_text(frame, f"Najlepsze combo rundy: {state.round_best_combo}", _centered_text(frame, f"Najlepsze combo rundy: {state.round_best_combo}", 0.62, 56), scale=0.62, color=NEON_GOLD)
    draw_text(
        frame,
        f"Gold {state.special_hits[ObjectKind.GOLD]}   Freeze {state.special_hits[ObjectKind.FREEZE]}   Bomby {state.special_hits[ObjectKind.BOMB]}",
        _centered_text(
            frame,
            f"Gold {state.special_hits[ObjectKind.GOLD]}   Freeze {state.special_hits[ObjectKind.FREEZE]}   Bomby {state.special_hits[ObjectKind.BOMB]}",
            0.58,
            96,
        ),
        scale=0.58,
    )
    draw_text(frame, "R - nowa gra", _centered_text(frame, "R - nowa gra", 0.74, 146), scale=0.74, color=NEON_CYAN)


def _draw_center_panel(frame: np.ndarray, width: int, height: int) -> None:
    frame_height, frame_width = frame.shape[:2]
    x1 = max(18, (frame_width - width) // 2)
    y1 = max(18, (frame_height - height) // 2)
    x2 = min(frame_width - 18, x1 + width)
    y2 = min(frame_height - 18, y1 + height)
    _draw_panel(frame, (x1, y1), (x2, y2), alpha=0.42)
    cv2.rectangle(frame, (x1, y1), (x2, y2), PANEL_BORDER, 2, cv2.LINE_AA)


def _draw_panel(
    frame: np.ndarray,
    top_left: tuple[int, int],
    bottom_right: tuple[int, int],
    alpha: float = 0.35,
    fill: tuple[int, int, int] = PANEL_FILL,
) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, top_left, bottom_right, fill, -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0.0, frame)
    cv2.rectangle(frame, top_left, bottom_right, PANEL_BORDER, 1, cv2.LINE_AA)


def _draw_badge(frame: np.ndarray, text: str, position: tuple[int, int], color: tuple[int, int, int]) -> None:
    x, y = position
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
    _draw_panel(frame, (x, y), (x + size[0] + 18, y + 24), alpha=0.44, fill=(18, 22, 28))
    draw_text(frame, text, (x + 9, y + 18), scale=0.55, color=color, thickness=1)


def _draw_progress_bar(frame: np.ndarray, progress: float, y_offset: int) -> None:
    frame_height, frame_width = frame.shape[:2]
    width = 320
    x = (frame_width - width) // 2
    y = frame_height // 2 + y_offset
    progress = min(max(progress, 0.0), 1.0)
    cv2.rectangle(frame, (x, y), (x + width, y + 16), TIME_BG, -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x, y), (x + int(width * progress), y + 16), NEON_GOLD, -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x, y), (x + width, y + 16), (220, 225, 235), 1, cv2.LINE_AA)


def _centered_text(frame: np.ndarray, text: str, scale: float, offset_y: int) -> tuple[int, int]:
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, 2)
    x = (frame.shape[1] - size[0]) // 2
    y = (frame.shape[0] + size[1]) // 2 + offset_y
    return x, y


def _phase_color(phase: int) -> tuple[int, int, int]:
    if phase == 1:
        return NEON_CYAN
    if phase == 2:
        return NEON_GOLD
    return NEON_RED


def _status_label(state: GameState, person_present: bool) -> tuple[str, tuple[int, int, int]]:
    if state.mode == GameMode.GAME_OVER:
        return "FINAL", NEON_RED
    if state.mode == GameMode.PAUSED_TRACKING_LOST:
        return "TRACK LOST", NEON_RED
    if state.mode == GameMode.COUNTDOWN:
        return "COUNTDOWN", NEON_GOLD
    if state.mode == GameMode.WAITING_FOR_PLAYER:
        return ("PLAYER READY" if person_present else "WAITING"), HUD_ACCENT
    return "LIVE", NEON_CYAN
