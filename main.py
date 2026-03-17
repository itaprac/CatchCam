from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import time
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
import numpy as np

from game_logic import GameMode, GameState
from persistence import load_stats, save_stats
from rendering import (
    draw_background_hud,
    draw_falling_objects,
    draw_game_state_overlays,
    draw_hit_effects,
    draw_text,
)


WINDOW_NAME = "Spadajace kulki"
MODEL_DIR = Path(__file__).parent / "models"
DATA_DIR = Path(__file__).parent / "data"
STATS_PATH = DATA_DIR / "stats.json"
HAND_MODEL_PATH = MODEL_DIR / "hand_landmarker.task"
POSE_MODEL_PATH = MODEL_DIR / "pose_landmarker_lite.task"
HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)


@dataclass
class FrameDetections:
    pose_landmarks: list | None
    hand_landmarks: list[list]


@dataclass
class CameraProbeResult:
    index: int
    backend_name: str
    opened: bool
    readable: bool
    width: int = 0
    height: int = 0
    mean_brightness: float = 0.0
    std_brightness: float = 0.0
    usable: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gra arcade z kamerka, combo i specjalnymi obiektami sterowana dlonmi."
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Indeks kamery do otwarcia (domyslnie 0).",
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="Sprawdza kilka indeksow kamer i wypisuje, ktore daja sensowny obraz.",
    )
    return parser.parse_args()


def ensure_model(model_path: Path, download_url: str) -> Path:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if not model_path.exists():
        print(f"Pobieram model MediaPipe: {model_path.name}...")
        urlretrieve(download_url, model_path)
    return model_path


class VisionDetectors:
    def __init__(self) -> None:
        self.base_options_cls = mp.tasks.BaseOptions
        self.vision = mp.tasks.vision
        self.running_mode = self.vision.RunningMode.VIDEO
        self.image_format = mp.ImageFormat.SRGB
        self.pose_landmarker = None
        self.hand_landmarker = None

    def __enter__(self) -> "VisionDetectors":
        hand_model = ensure_model(HAND_MODEL_PATH, HAND_MODEL_URL)
        pose_model = ensure_model(POSE_MODEL_PATH, POSE_MODEL_URL)

        hand_options = self.vision.HandLandmarkerOptions(
            base_options=self.base_options_cls(model_asset_path=str(hand_model)),
            running_mode=self.running_mode,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        pose_options = self.vision.PoseLandmarkerOptions(
            base_options=self.base_options_cls(model_asset_path=str(pose_model)),
            running_mode=self.running_mode,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_segmentation_masks=False,
        )

        self.hand_landmarker = self.vision.HandLandmarker.create_from_options(hand_options)
        self.pose_landmarker = self.vision.PoseLandmarker.create_from_options(pose_options)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self.hand_landmarker is not None:
            self.hand_landmarker.close()
        if self.pose_landmarker is not None:
            self.pose_landmarker.close()

    def detect(self, rgb_frame: np.ndarray, timestamp_ms: int) -> FrameDetections:
        mp_image = mp.Image(image_format=self.image_format, data=rgb_frame)
        pose_result = self.pose_landmarker.detect_for_video(mp_image, timestamp_ms)
        hand_result = self.hand_landmarker.detect_for_video(mp_image, timestamp_ms)

        pose_landmarks = pose_result.pose_landmarks[0] if pose_result.pose_landmarks else None
        hand_landmarks = hand_result.hand_landmarks if hand_result.hand_landmarks else []
        return FrameDetections(
            pose_landmarks=pose_landmarks,
            hand_landmarks=hand_landmarks,
        )


def person_is_present(pose_landmarks: list | None) -> bool:
    if not pose_landmarks:
        return False

    pose_enum = mp.tasks.vision.PoseLandmark
    required_landmarks = (
        pose_enum.LEFT_SHOULDER,
        pose_enum.RIGHT_SHOULDER,
        pose_enum.LEFT_HIP,
        pose_enum.RIGHT_HIP,
    )

    visible_points = 0
    for landmark_id in required_landmarks:
        landmark = pose_landmarks[landmark_id.value]
        visibility = landmark.visibility if landmark.visibility is not None else 0.0
        if visibility >= 0.5:
            visible_points += 1

    return visible_points >= 2


def collect_touch_points(
    hand_landmarks_list: list[list],
    frame_width: int,
    frame_height: int,
) -> list[tuple[float, float]]:
    all_points: list[tuple[float, float]] = []
    hand_indices = {
        "wrist": 0,
        "index_mcp": 5,
        "pinky_mcp": 17,
        "index_tip": 8,
        "middle_tip": 12,
    }

    for hand_landmarks in hand_landmarks_list:
        wrist = hand_landmarks[hand_indices["wrist"]]
        index_mcp = hand_landmarks[hand_indices["index_mcp"]]
        pinky_mcp = hand_landmarks[hand_indices["pinky_mcp"]]
        index_tip = hand_landmarks[hand_indices["index_tip"]]
        middle_tip = hand_landmarks[hand_indices["middle_tip"]]

        palm_center_x = (wrist.x + index_mcp.x + pinky_mcp.x) / 3.0
        palm_center_y = (wrist.y + index_mcp.y + pinky_mcp.y) / 3.0

        normalized_points = [
            (palm_center_x, palm_center_y),
            (index_tip.x, index_tip.y),
            (middle_tip.x, middle_tip.y),
        ]
        for point_x, point_y in normalized_points:
            all_points.append(
                (
                    min(max(point_x * frame_width, 0.0), frame_width - 1.0),
                    min(max(point_y * frame_height, 0.0), frame_height - 1.0),
                )
            )

    return all_points


def smooth_touch_points(
    previous_points: list[tuple[float, float]],
    current_points: list[tuple[float, float]],
    blend: float = 0.35,
) -> list[tuple[float, float]]:
    if not current_points:
        return []

    if not previous_points or len(previous_points) != len(current_points):
        return current_points

    smoothed_points: list[tuple[float, float]] = []
    for previous_point, current_point in zip(previous_points, current_points):
        prev_x, prev_y = previous_point
        current_x, current_y = current_point
        smoothed_points.append(
            (
                prev_x * blend + current_x * (1.0 - blend),
                prev_y * blend + current_y * (1.0 - blend),
            )
        )
    return smoothed_points


def draw_landmarks(frame: np.ndarray, detections: FrameDetections) -> None:
    drawing_utils = mp.tasks.vision.drawing_utils
    pose_connections = mp.tasks.vision.PoseLandmarksConnections.POSE_LANDMARKS
    hand_connections = mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS

    pose_style = drawing_utils.DrawingSpec(color=(120, 210, 120), thickness=2, circle_radius=2)
    hand_style = drawing_utils.DrawingSpec(color=(255, 200, 90), thickness=2, circle_radius=2)
    hand_connection_style = drawing_utils.DrawingSpec(color=(90, 180, 255), thickness=2, circle_radius=2)

    if detections.pose_landmarks:
        drawing_utils.draw_landmarks(
            frame,
            detections.pose_landmarks,
            pose_connections,
            landmark_drawing_spec=pose_style,
            connection_drawing_spec=pose_style,
        )

    for hand_landmarks in detections.hand_landmarks:
        drawing_utils.draw_landmarks(
            frame,
            hand_landmarks,
            hand_connections,
            landmark_drawing_spec=hand_style,
            connection_drawing_spec=hand_connection_style,
        )


def frame_has_signal(frame: np.ndarray) -> bool:
    if frame is None or frame.size == 0:
        return False
    mean_brightness = float(frame.mean())
    std_brightness = float(frame.std())
    return mean_brightness >= 8.0 or std_brightness >= 6.0


def warm_up_capture(capture: cv2.VideoCapture, frames: int = 20) -> np.ndarray | None:
    last_frame: np.ndarray | None = None
    for _ in range(frames):
        ok, frame = capture.read()
        if ok and frame is not None and frame.size > 0:
            last_frame = frame
        time.sleep(0.02)
    return last_frame


def probe_camera_index(camera_index: int) -> list[CameraProbeResult]:
    results: list[CameraProbeResult] = []
    backends = [("AVFOUNDATION", cv2.CAP_AVFOUNDATION), ("DEFAULT", cv2.CAP_ANY)]

    for backend_name, backend_id in backends:
        capture = cv2.VideoCapture(camera_index, backend_id)
        if not capture.isOpened():
            capture.release()
            results.append(
                CameraProbeResult(
                    index=camera_index,
                    backend_name=backend_name,
                    opened=False,
                    readable=False,
                )
            )
            continue

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        capture.set(cv2.CAP_PROP_FPS, 30)

        frame = warm_up_capture(capture)
        opened = True
        readable = frame is not None
        width = int(frame.shape[1]) if readable else 0
        height = int(frame.shape[0]) if readable else 0
        mean_brightness = float(frame.mean()) if readable else 0.0
        std_brightness = float(frame.std()) if readable else 0.0
        usable = readable and frame_has_signal(frame)

        results.append(
            CameraProbeResult(
                index=camera_index,
                backend_name=backend_name,
                opened=opened,
                readable=readable,
                width=width,
                height=height,
                mean_brightness=mean_brightness,
                std_brightness=std_brightness,
                usable=usable,
            )
        )
        capture.release()

    return results


def print_camera_report(max_index: int = 5) -> None:
    print("Sprawdzam kamery...")
    for camera_index in range(max_index + 1):
        for result in probe_camera_index(camera_index):
            print(
                f"index={result.index} backend={result.backend_name} "
                f"opened={result.opened} readable={result.readable} usable={result.usable} "
                f"size={result.width}x{result.height} "
                f"mean={result.mean_brightness:.1f} std={result.std_brightness:.1f}"
            )


def open_camera(camera_index: int) -> tuple[cv2.VideoCapture, str, np.ndarray | None]:
    candidate_indices = [camera_index]
    candidate_indices.extend(index for index in range(6) if index != camera_index)

    best_fallback: tuple[cv2.VideoCapture, str, np.ndarray | None] | None = None
    best_fallback_score = -1.0

    for index in candidate_indices:
        backend_pairs = [("AVFOUNDATION", cv2.CAP_AVFOUNDATION), ("DEFAULT", cv2.CAP_ANY)]
        for backend_name, backend_id in backend_pairs:
            capture = cv2.VideoCapture(index, backend_id)
            if not capture.isOpened():
                capture.release()
                continue

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            capture.set(cv2.CAP_PROP_FPS, 30)

            frame = warm_up_capture(capture)
            if frame is not None and frame_has_signal(frame):
                return capture, f"{index}:{backend_name}", frame

            fallback_score = float(frame.std()) if frame is not None else 0.0
            if fallback_score > best_fallback_score:
                if best_fallback is not None:
                    best_fallback[0].release()
                best_fallback = (capture, f"{index}:{backend_name}", frame)
                best_fallback_score = fallback_score
            else:
                capture.release()

    if best_fallback is not None:
        return best_fallback

    raise RuntimeError(
        f"Nie udalo sie otworzyc kamery o indeksie {camera_index}. "
        "Uruchom `python3 main.py --list-cameras`, zeby zobaczyc dostepne indeksy."
    )


def add_camera_warning(frame: np.ndarray, camera_label: str, frame_ok: bool) -> None:
    if frame_ok:
        return
    draw_text(
        frame,
        f"Uwaga: obraz z kamery wyglada na czarny ({camera_label})",
        (30, 156),
        scale=0.55,
        color=(210, 225, 255),
        thickness=1,
    )
    draw_text(
        frame,
        "Sprobuj `--camera 1` albo `--list-cameras`.",
        (30, 182),
        scale=0.55,
        color=(210, 225, 255),
        thickness=1,
    )


def run(camera_index: int) -> None:
    capture, camera_label, initial_frame = open_camera(camera_index)
    state = GameState(width=0, height=0)
    state.load_stats(load_stats(STATS_PATH))

    previous_tick = time.perf_counter()
    frame_signal_ok = initial_frame is not None and frame_has_signal(initial_frame)
    smoothed_touch_points: list[tuple[float, float]] = []
    saved_game_over = False

    try:
        with VisionDetectors() as detectors:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Nie udalo sie pobrac klatki z kamery.")

                if not frame_signal_ok:
                    frame_signal_ok = frame_has_signal(frame)

                frame = cv2.flip(frame, 1)
                frame_height, frame_width = frame.shape[:2]
                state.set_dimensions(frame_width, frame_height)

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp_ms = int(time.perf_counter() * 1000)
                detections = detectors.detect(rgb_frame, timestamp_ms)

                now = time.perf_counter()
                delta_time = min(now - previous_tick, 0.1)
                previous_tick = now

                person_present = person_is_present(detections.pose_landmarks)
                raw_touch_points = (
                    collect_touch_points(
                        detections.hand_landmarks,
                        frame_width,
                        frame_height,
                    )
                    if person_present
                    else []
                )
                smoothed_touch_points = smooth_touch_points(smoothed_touch_points, raw_touch_points)

                previous_mode = state.mode
                state.update(delta_time, smoothed_touch_points, person_present)

                if state.mode == GameMode.GAME_OVER and not saved_game_over:
                    save_stats(STATS_PATH, state.build_stats_snapshot())
                    saved_game_over = True
                elif state.mode != GameMode.GAME_OVER:
                    saved_game_over = False

                if previous_mode == GameMode.PAUSED_TRACKING_LOST and state.mode == GameMode.PLAYING:
                    previous_tick = time.perf_counter()

                draw_landmarks(frame, detections)
                draw_falling_objects(frame, state)
                draw_hit_effects(frame, state)
                draw_background_hud(frame, state, person_present)
                draw_game_state_overlays(frame, state, person_present)
                add_camera_warning(frame, camera_label, frame_signal_ok)

                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF

                if key in (ord("q"), ord("Q"), 27):
                    break
                if key in (ord("r"), ord("R")):
                    state.reset_for_new_round()
                    smoothed_touch_points = []
                    saved_game_over = False
                    previous_tick = time.perf_counter()
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    if args.list_cameras:
        print_camera_report()
        return
    run(args.camera)


if __name__ == "__main__":
    main()
