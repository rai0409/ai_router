"""Analyze image and video assets to extract face embeddings and quality metrics."""

from __future__ import annotations

import base64
import csv
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from insightface.app import FaceAnalysis
from tqdm import tqdm

import scripts.config as config


ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"
IMAGES_DIR = ASSETS_ROOT / "images"
VIDEOS_DIR = ASSETS_ROOT / "videos"
ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"
MANIFEST_PATH = ASSETS_ROOT / "manifest.csv"


def ensure_dirs() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


def ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except Exception:
        return False


def load_manifest() -> Dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    mapping: Dict[str, str] = {}
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            path_val = row.get("path")
            pid_val = row.get("person_id")
            if path_val and pid_val:
                mapping[Path(path_val).as_posix()] = pid_val
    return mapping


def resolve_person_id(file_path: Path, manifest: Dict[str, str], base_dir: Path) -> str:
    rel_posix = file_path.relative_to(ASSETS_ROOT).as_posix()
    if rel_posix in manifest:
        return manifest[rel_posix]

    if file_path.parent != base_dir:
        return file_path.parent.name

    match = re.match(r"^([A-Za-z0-9]+)_", file_path.name)
    if match:
        return match.group(1)

    return "UNKNOWN"


def encode_embedding(embedding: Optional[np.ndarray]) -> str:
    if embedding is None:
        return ""
    emb = embedding.astype(np.float32)
    emb = emb / (np.linalg.norm(emb) + 1e-12)
    return base64.b64encode(emb.tobytes()).decode("utf-8")


def compute_pose_from_landmarks(
    kps: Optional[np.ndarray], bbox: np.ndarray
) -> Tuple[float, float, float]:
    if kps is None or len(kps) < 5:
        return 0.0, 0.0, 0.0
    left_eye, right_eye, nose, left_mouth, right_mouth = kps
    eye_center = (left_eye + right_eye) / 2.0
    mouth_center = (left_mouth + right_mouth) / 2.0
    face_w = max(bbox[2] - bbox[0], 1.0)
    face_h = max(bbox[3] - bbox[1], 1.0)

    yaw = np.degrees(np.arctan2(nose[0] - eye_center[0], face_w))
    pitch = np.degrees(np.arctan2(nose[1] - ((eye_center[1] + mouth_center[1]) / 2.0), face_h))
    roll = np.degrees(np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))
    return float(yaw), float(pitch), float(roll)


def compute_expression_scores(kps: Optional[np.ndarray]) -> Tuple[float, float]:
    if kps is None or len(kps) < 5:
        return 0.0, 0.0
    left_eye, right_eye, nose, left_mouth, right_mouth = kps
    eye_dist = np.linalg.norm(right_eye - left_eye) + 1e-6
    mouth_height = abs(left_mouth[1] - right_mouth[1])
    mouth_width = np.linalg.norm(right_mouth - left_mouth)
    mouth_openness = float(mouth_height / eye_dist)
    smile_proxy = float(mouth_width / eye_dist)
    return mouth_openness, smile_proxy


def compute_quality_metrics(image_bgr: np.ndarray, bbox: Optional[np.ndarray]) -> Dict[str, float]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    h, w = gray.shape
    area = float(h * w)

    brightness_mean = float(np.mean(gray))
    highlight_clipping_ratio = float(np.mean(gray >= 250))
    sharpness_laplacian = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    saturation_mean = float(np.mean(hsv[:, :, 1]))

    if bbox is not None:
        x1, y1, x2, y2 = bbox.astype(int)
        x1 = max(x1, 0)
        y1 = max(y1, 0)
        x2 = min(x2, w - 1)
        y2 = min(y2, h - 1)
        face_area = float(max(0, x2 - x1) * max(0, y2 - y1))
        mask = np.ones_like(gray, dtype=np.uint8)
        mask[y1:y2, x1:x2] = 0
    else:
        face_area = 0.0
        mask = np.ones_like(gray, dtype=np.uint8)

    face_area_ratio = face_area / area if area > 0 else 0.0

    edges = cv2.Canny(gray, 100, 200)
    background_edges = edges * mask
    background_edge_density = float(np.mean(background_edges > 0))

    return {
        "face_area_ratio": face_area_ratio,
        "brightness_mean": brightness_mean,
        "highlight_clipping_ratio": highlight_clipping_ratio,
        "sharpness_laplacian": sharpness_laplacian,
        "saturation_mean": saturation_mean,
        "background_edge_density": background_edge_density,
    }


def detect_primary_face(
    app: FaceAnalysis, image_bgr: np.ndarray
) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray], Tuple[float, float, float], Tuple[float, float]]:
    faces = app.get(image_bgr)
    if not faces:
        return False, None, None, (0.0, 0.0, 0.0), (0.0, 0.0)

    faces = sorted(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )
    face = faces[0]
    bbox = np.array(face.bbox, dtype=np.float32)
    kps = np.array(face.kps, dtype=np.float32) if getattr(face, "kps", None) is not None else None
    yaw, pitch, roll = compute_pose_from_landmarks(kps, bbox)
    mouth_open, smile_proxy = compute_expression_scores(kps)
    embedding = getattr(face, "normed_embedding", None)
    if embedding is None and getattr(face, "embedding", None) is not None:
        raw_emb = np.array(face.embedding, dtype=np.float32)
        norm = np.linalg.norm(raw_emb) + 1e-12
        embedding = raw_emb / norm

    return True, bbox, embedding, (yaw, pitch, roll), (mouth_open, smile_proxy)


def process_image_file(
    app: FaceAnalysis,
    file_path: Path,
    person_id: str,
    source_type: str,
    image_bgr: Optional[np.ndarray] = None,
) -> Dict[str, object]:
    if image_bgr is None:
        image_bgr = cv2.imread(str(file_path))
    if image_bgr is None:
        return {}

    face_detected, bbox, embedding, pose, expressions = detect_primary_face(app, image_bgr)
    metrics = compute_quality_metrics(image_bgr, bbox)

    record = {
        "image_id": file_path.stem,
        "person_id": person_id,
        "source_type": source_type,
        "face_detected": bool(face_detected),
        "face_bbox": "" if bbox is None else ",".join(str(round(float(x), 4)) for x in bbox.tolist()),
        "face_area_ratio": metrics["face_area_ratio"],
        "face_embedding": encode_embedding(embedding),
        "yaw": pose[0],
        "pitch": pose[1],
        "roll": pose[2],
        "brightness_mean": metrics["brightness_mean"],
        "highlight_clipping_ratio": metrics["highlight_clipping_ratio"],
        "sharpness_laplacian": metrics["sharpness_laplacian"],
        "saturation_mean": metrics["saturation_mean"],
        "background_edge_density": metrics["background_edge_density"],
        "mouth_openness": expressions[0],
        "smile_score_proxy": expressions[1],
    }
    return record


def iterate_video_frames(video_path: Path, interval_sec: float):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 30.0
    frame_interval = max(int(round(fps * interval_sec)), 1)
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            yield frame_idx, frame
        frame_idx += 1
    cap.release()


def main() -> None:
    ensure_dirs()
    manifest = load_manifest()

    app = FaceAnalysis(
        name=config.INSIGHTFACE_MODEL_NAME,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=(640, 640))

    records: List[Dict[str, object]] = []

    image_files = sorted(
        [p for p in IMAGES_DIR.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}]
    )

    for img_path in tqdm(image_files, desc="Images"):
        person_id = resolve_person_id(img_path, manifest, IMAGES_DIR)
        record = process_image_file(app, img_path, person_id, "image")
        if record:
            records.append(record)

    videos_processed = False
    video_warning = ""
    video_files = sorted(
        [p for p in VIDEOS_DIR.rglob("*") if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi"}]
    )

    if video_files:
        if ffmpeg_available():
            videos_processed = True
            for vid_path in tqdm(video_files, desc="Videos"):
                person_id = resolve_person_id(vid_path, manifest, VIDEOS_DIR)
                for frame_idx, frame in iterate_video_frames(vid_path, config.VIDEO_FRAME_INTERVAL):
                    frame_id = f"{vid_path.stem}_frame_{frame_idx}"
                    record = process_image_file(
                        app,
                        vid_path.with_name(frame_id),
                        person_id,
                        "video_frame",
                        frame,
                    )
                    if record:
                        record["image_id"] = frame_id
                        records.append(record)
        else:
            video_warning = "ffmpeg not available; video processing skipped."

    if not records:
        print("No assets processed; exiting.")
        return

    df = pd.DataFrame(records)
    df.to_csv(ANALYSIS_DIR / "analysis.csv", index=False)

    meta_lines: List[str] = []
    if video_warning:
        meta_lines.append(video_warning)
    if videos_processed:
        meta_lines.append(f"Video frames processed every {config.VIDEO_FRAME_INTERVAL} seconds.")
    if meta_lines:
        (ANALYSIS_DIR / "analysis_notes.txt").write_text("\n".join(meta_lines), encoding="utf-8")

    print(f"Saved analysis to {ANALYSIS_DIR / 'analysis.csv'}")


if __name__ == "__main__":
    main()
