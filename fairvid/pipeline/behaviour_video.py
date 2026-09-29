"""Real MediaPipe behaviour analysis for a single interview video.

This is a faithful port of the "Multimodal Behaviour Analysis" notebook: it runs
the MediaPipe Face Landmarker over the video and returns the same metrics dict
(composite stability score, reading probability, gaze aversion, blink rate,
smiling, speaking) the notebook writes. Used by the web app on the video you
record. If MediaPipe/OpenCV are missing it raises, and the caller falls back.

The Face Landmarker model file is downloaded once on first use.
"""

from __future__ import annotations

import os
import urllib.request
from collections import deque, defaultdict

import numpy as np

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")
MODEL_PATH = "/tmp/face_landmarker_v2_with_blendshapes.task"


def ensure_model() -> str:
    if not os.path.exists(MODEL_PATH):
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def _reading_behavior(h, head_stability):
    if not h.get('eyeLookOutLeft'):
        return {"Gaze Aversion": 0.0, "Avg Vertical Gaze": 0.0,
                "Horizontal Variance": 0.0, "Reading Probability": 0}
    look_left = np.array(h['eyeLookOutLeft']) + np.array(h['eyeLookInRight'])
    look_right = np.array(h['eyeLookInLeft']) + np.array(h['eyeLookOutRight'])
    gaze_x = (look_right - look_left) / 2.0
    look_down = np.array(h['eyeLookDownLeft']) + np.array(h['eyeLookDownRight'])
    look_up = np.array(h['eyeLookUpLeft']) + np.array(h['eyeLookUpRight'])
    gaze_y = (look_down - look_up) / 2.0
    mag = np.sqrt(gaze_x ** 2 + gaze_y ** 2)
    aversion = float(np.sum(mag > 0.15) / len(mag)) if len(mag) else 0.0
    x_var, y_var = float(np.var(gaze_x)), float(np.var(gaze_y))
    is_scanning = (x_var > 0.02) and (x_var > y_var * 2)
    avg_vertical = float(np.mean(gaze_y)) if len(gaze_y) else 0.0
    prob = 0
    if avg_vertical > 0.3:
        prob += 60
    elif avg_vertical > 0.15:
        prob += 30
    if is_scanning:
        prob += 40
    if head_stability < 40:
        prob -= 30
    prob = max(0, min(100, prob))
    return {"Gaze Aversion": aversion, "Avg Vertical Gaze": avg_vertical,
            "Horizontal Variance": x_var, "Reading Probability": prob}


def _blink_rate(h, ts):
    avg = (np.array(h['eyeBlinkLeft']) + np.array(h['eyeBlinkRight'])) / 2.0
    count, closed = 0, False
    for v in avg:
        if v > 0.5 and not closed:
            count += 1; closed = True
        elif v <= 0.5:
            closed = False
    minutes = (ts[-1] - ts[0]) / 60.0 if len(ts) > 1 else 0
    return count / minutes if minutes > 0 else 0.0


def _smiling(h):
    s = (np.array(h['mouthSmileLeft']) + np.array(h['mouthSmileRight'])) / 2.0
    return float(np.mean(s)), float(np.sum(s > 0.5) / len(s) * 100) if len(s) else (0.0, 0.0)


def analyse_video(video_path: str) -> dict:
    """Return the notebook's behaviour-metrics dict for one video."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    model_path = ensure_model()
    h = defaultdict(list)
    ts = []

    def rot(M):
        R = M[:3, :3]
        return np.degrees(np.array([np.arctan2(R[1, 0], R[0, 0]),
                                    np.arctan2(-R[2, 0], np.sqrt(R[2, 1] ** 2 + R[2, 2] ** 2)),
                                    np.arctan2(R[2, 1], R[2, 2])]))

    opts = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_path),
        output_facial_transformation_matrixes=True,
        output_face_blendshapes=True, num_faces=1,
        running_mode=vision.RunningMode.VIDEO)
    detector = vision.FaceLandmarker.create_from_options(opts)

    cap = cv2.VideoCapture(video_path)
    # Derive timestamps from the frame index, not the file's POS_MSEC: real
    # browser recordings often report 0/non-monotonic POS_MSEC, which makes
    # MediaPipe's VIDEO mode raise. A frame counter is always monotonic.
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps != fps or fps <= 0:   # 0 or NaN
        fps = 15.0
    dt = 1.0 / fps
    prev_rot, frame_idx, last_ms = None, 0, -1
    speeds, win = [], deque(maxlen=5)
    rapid = total = 0
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            t_ms = int(frame_idx * 1000.0 / fps)
            if t_ms <= last_ms:
                t_ms = last_ms + 1
            last_ms = t_ms
            frame_idx += 1
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
                res = detector.detect_for_video(img, t_ms)
            except Exception:
                continue  # skip a bad frame rather than abort the whole video
            if res.facial_transformation_matrixes and res.face_landmarks:
                r = rot(res.facial_transformation_matrixes[0])
                if prev_rot is not None:
                    sp = np.linalg.norm(r - prev_rot) / dt
                    win.append(sp); sm = float(np.mean(win))
                    speeds.append(sm); total += 1
                    if sm >= 8.0:
                        rapid += 1
                prev_rot = r
            if res.face_blendshapes:
                ts.append(t_ms / 1000.0)
                for c in res.face_blendshapes[0]:
                    h[c.category_name].append(c.score)
    finally:
        cap.release(); detector.close()

    mean_speed = float(np.mean(speeds)) if speeds else 0.0
    rapid_ratio = rapid / total if total else 0.0
    composite = max(0, min(100, 100 - 2.5 * mean_speed - 40 * rapid_ratio))
    reading = _reading_behavior(h, composite)
    bpm = _blink_rate(h, ts) if ts else 0.0
    avg_smile, smile_freq = _smiling(h) if h.get('mouthSmileLeft') else (0.0, 0.0)
    jaw_var = float(np.std(h['jawOpen'])) if h.get('jawOpen') else 0.0

    return {
        "Mean head speed": round(mean_speed, 1),
        "Rapid movement": round(rapid_ratio * 100, 1),
        "Composite score": round(composite, 1),
        "Gaze Aversion": round(reading["Gaze Aversion"], 2),
        "Reading Prob": round(reading["Reading Probability"], 1),
        "Look Down Intensity": round(reading["Avg Vertical Gaze"], 2),
        "Blink Rate (BPM)": round(bpm, 1),
        "Smile Frequency": round(smile_freq, 1),
        "Average Smile Intensity": round(avg_smile, 3),
        "Is Speaking": bool(jaw_var > 0.05),
        "Jaw Variance": round(jaw_var, 3),
    }
