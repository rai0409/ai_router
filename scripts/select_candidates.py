"""Select consistent face clusters based on deterministic, quantitative rules."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances

import scripts.config as config


ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"
ANALYSIS_CSV = ANALYSIS_DIR / "analysis.csv"
REPORT_MD = ANALYSIS_DIR / "report.md"
CANDIDATE_CSV = ANALYSIS_DIR / "candidate_cluster.csv"
NOTES_PATH = ANALYSIS_DIR / "analysis_notes.txt"


@dataclass
class PersonStats:
    person_id: str
    embeddings: List[np.ndarray]
    usable_image_count: int
    mean_embedding: np.ndarray
    intra_person_variance: float
    quality_score: float
    cluster_id: int | None = None
    mean_distance_to_centroid: float = 0.0
    mean_intra_person_variance: float = 0.0


def decode_embedding(emb_str: str) -> np.ndarray:
    raw = base64.b64decode(emb_str)
    emb = np.frombuffer(raw, dtype=np.float32)
    if emb.size == 0:
        return np.zeros(512, dtype=np.float32)
    norm = np.linalg.norm(emb) + 1e-12
    return emb / norm


def compute_person_stats(df: pd.DataFrame) -> Dict[str, PersonStats]:
    stats: Dict[str, PersonStats] = {}
    for pid, group in df.groupby("person_id"):
        embeddings = [decode_embedding(e) for e in group["face_embedding"] if isinstance(e, str) and e]
        if not embeddings:
            continue
        emb_stack = np.vstack(embeddings)
        mean_emb = emb_stack.mean(axis=0)
        mean_emb /= np.linalg.norm(mean_emb) + 1e-12
        distances = cosine_distances(emb_stack, mean_emb.reshape(1, -1)).flatten()
        intra_var = float(np.mean(distances))
        stats[pid] = PersonStats(
            person_id=pid,
            embeddings=embeddings,
            usable_image_count=len(embeddings),
            mean_embedding=mean_emb,
            intra_person_variance=intra_var,
            quality_score=0.0,
        )
    return stats


def robust_scale(series: pd.Series, lower: float = 5.0, upper: float = 95.0) -> pd.Series:
    if series.empty:
        return pd.Series(dtype=float)
    lo = np.percentile(series, lower)
    hi = np.percentile(series, upper)
    if hi - lo < 1e-9:
        return pd.Series(np.ones_like(series, dtype=float), index=series.index)
    scaled = (series - lo) / (hi - lo)
    return scaled.clip(0.0, 1.0)


def compute_quality_scores(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    exposure_center = (config.MAX_BRIGHTNESS + config.MIN_BRIGHTNESS) / 2.0
    exposure_score = 1.0 - np.abs(df["brightness_mean"] - exposure_center) / max(
        (config.MAX_BRIGHTNESS - config.MIN_BRIGHTNESS) / 2.0, 1e-6
    )
    exposure_score = np.clip(exposure_score, 0.0, 1.0)

    sharpness_scaled = robust_scale(df["sharpness_laplacian"])
    exposure_scaled = robust_scale(pd.Series(exposure_score, index=df.index))
    face_area_scaled = robust_scale(df["face_area_ratio"])
    background_simple = 1.0 - robust_scale(df["background_edge_density"])

    weights = {
        "sharpness": config.QUALITY_WEIGHT_SHARPNESS,
        "exposure": config.QUALITY_WEIGHT_EXPOSURE,
        "face_area": config.QUALITY_WEIGHT_FACE_AREA,
        "background": config.QUALITY_WEIGHT_BACKGROUND,
    }
    weighted = (
        sharpness_scaled * weights["sharpness"]
        + exposure_scaled * weights["exposure"]
        + face_area_scaled * weights["face_area"]
        + background_simple * weights["background"]
    )
    total_w = sum(weights.values())
    return (weighted / total_w * 100.0).clip(0.0, 100.0)


def cluster_persons(mean_embeddings: List[np.ndarray]) -> np.ndarray:
    if len(mean_embeddings) == 1:
        return np.array([0])

    X = np.vstack(mean_embeddings)
    try:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=config.FALLBACK_DISTANCE_THRESHOLD,
            metric="cosine",
            linkage="average",
        )
    except TypeError:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=config.FALLBACK_DISTANCE_THRESHOLD,
            affinity="cosine",
            linkage="average",
        )
    labels = clustering.fit_predict(X)
    return labels


def compute_cluster_stats(person_stats: Dict[str, PersonStats], labels: np.ndarray) -> Dict[int, Dict[str, float]]:
    cluster_stats: Dict[int, Dict[str, float]] = {}
    persons = [person_stats[k] for k in sorted(person_stats)]
    for label in np.unique(labels):
        member_indices = [i for i, l in enumerate(labels) if l == label]
        member_embs = np.vstack([persons[i].mean_embedding for i in member_indices])
        centroid = member_embs.mean(axis=0)
        centroid /= np.linalg.norm(centroid) + 1e-12
        distances = cosine_distances(member_embs, centroid.reshape(1, -1)).flatten()
        mean_intra_cluster_distance = float(np.mean(distances))
        cluster_variance = float(np.var(member_embs, axis=0).mean())
        mean_intra_person_var = float(np.mean([persons[i].intra_person_variance for i in member_indices]))
        cluster_stats[label] = {
            "centroid": centroid,
            "num_persons": len(member_indices),
            "mean_intra_cluster_distance": mean_intra_cluster_distance,
            "cluster_variance": cluster_variance,
            "mean_intra_person_variance": mean_intra_person_var,
            "member_indices": member_indices,
        }
        for local_idx, idx in enumerate(member_indices):
            persons[idx].cluster_id = int(label)
            persons[idx].mean_distance_to_centroid = float(distances[local_idx])
    return cluster_stats


def select_cluster(cluster_stats: Dict[int, Dict[str, float]]) -> Tuple[int | None, str]:
    if not cluster_stats:
        return None, "No clusters available."

    preferred = [
        cid for cid, s in cluster_stats.items() if s["mean_intra_cluster_distance"] <= config.PREFERRED_DISTANCE_THRESHOLD
    ]
    eligible = preferred if preferred else [
        cid for cid, s in cluster_stats.items() if s["mean_intra_cluster_distance"] <= config.FALLBACK_DISTANCE_THRESHOLD
    ]

    if not eligible:
        best = min(cluster_stats.items(), key=lambda kv: kv[1]["mean_intra_cluster_distance"])
        return None, (
            f"Threshold violation: best cluster {best[0]} mean distance "
            f"{best[1]['mean_intra_cluster_distance']:.4f}"
        )

    def key_fn(cid: int):
        stat = cluster_stats[cid]
        return (-stat["num_persons"], stat["mean_intra_cluster_distance"])

    eligible_sorted = sorted(eligible, key=key_fn)
    best_candidate = eligible_sorted[0]

    for cid in eligible_sorted:
        if cluster_stats[cid]["mean_intra_cluster_distance"] <= config.PREFERRED_DISTANCE_THRESHOLD:
            larger_candidates = [
                other for other in eligible if cluster_stats[other]["num_persons"] > cluster_stats[cid]["num_persons"]
            ]
            for larger in larger_candidates:
                larger_var = cluster_stats[larger]["cluster_variance"]
                cand_var = cluster_stats[cid]["cluster_variance"]
                improvement = (larger_var - cand_var) / max(larger_var, 1e-12)
                if (
                    cluster_stats[cid]["num_persons"] < cluster_stats[larger]["num_persons"]
                    and improvement >= config.VARIANCE_IMPROVEMENT_RATIO
                ):
                    best_candidate = cid
            break

    if len(eligible_sorted) > 1:
        tie_candidates = [
            cid
            for cid in eligible_sorted
            if cluster_stats[cid]["num_persons"] == cluster_stats[best_candidate]["num_persons"]
        ]
        if len(tie_candidates) > 1:
            best_candidate = min(
                tie_candidates,
                key=lambda cid: cluster_stats[cid]["mean_intra_person_variance"],
            )

    return best_candidate, ""


def aggregate_quality_scores(df: pd.DataFrame, person_stats: Dict[str, PersonStats]) -> None:
    quality = compute_quality_scores(df)
    if quality.empty:
        return
    df = df.copy()
    df["quality_score"] = quality
    person_quality = df.groupby("person_id")["quality_score"].mean()
    for pid, score in person_quality.items():
        if pid in person_stats:
            person_stats[pid].quality_score = float(score)


def build_video_quality_summary(df: pd.DataFrame) -> List[str]:
    video_df = df[df["source_type"] == "video_frame"].copy()
    if video_df.empty:
        return []
    video_df["face_detected"] = video_df["face_detected"].astype(bool)
    video_df["video_id"] = video_df["image_id"].apply(lambda x: str(x).split("_frame_")[0])
    lines: List[str] = []
    for vid, group in video_df.groupby("video_id"):
        detection_rate = float(group["face_detected"].mean())
        reasons = []
        if group["face_area_ratio"].mean() < config.MIN_FACE_AREA_RATIO:
            reasons.append("faces too small")
        if group["sharpness_laplacian"].mean() < config.MIN_SHARPNESS:
            reasons.append("motion blur")
        if group["brightness_mean"].mean() < config.MIN_BRIGHTNESS:
            reasons.append("underexposed")
        if group["brightness_mean"].mean() > config.MAX_BRIGHTNESS:
            reasons.append("overexposed")
        reason_text = ", ".join(reasons) if reasons else "no dominant failure patterns"
        lines.append(f"- Video {vid}: detection {detection_rate*100:.1f}% ; typical issues: {reason_text}")
    return lines


def generate_report(
    person_stats: Dict[str, PersonStats],
    cluster_stats: Dict[int, Dict[str, float]],
    selected_cluster: int | None,
    warnings: List[str],
    detection_rate: float,
    fail_reason: str,
    video_quality: List[str],
    distance_matrix: np.ndarray | None,
) -> None:
    lines: List[str] = []
    lines.append("# Asset Analysis Report")
    lines.append("")
    lines.append("## Dataset Quality Overview")
    lines.append(f"- Face detection rate (images): {detection_rate*100:.1f}%")
    if detection_rate < 0.7:
        lines.append("- Detection rate is low; likely causes: small faces, motion blur, heavy cropping.")
    lines.append(f"- Persons with usable images: {len(person_stats)}")
    if warnings:
        lines.append("- Warnings:")
        for w in warnings:
            lines.append(f"  - {w}")
    lines.append("")
    lines.append("## Clustering Method")
    lines.append(
        "- Agglomerative clustering (average linkage, cosine distance, threshold = FALLBACK_DISTANCE_THRESHOLD)"
    )
    lines.append("")
    lines.append("## Cluster Statistics")
    if not cluster_stats:
        lines.append("- No clusters formed.")
    for cid, stat in sorted(cluster_stats.items()):
        lines.append(
            f"- Cluster {cid}: persons={stat['num_persons']}, "
            f"mean_intra_cluster_distance={stat['mean_intra_cluster_distance']:.4f}, "
            f"variance={stat['cluster_variance']:.6f}"
        )
    lines.append("")
    lines.append("## Selected Cluster Rationale")
    if selected_cluster is None:
        lines.append(f"- No cluster selected. Reason: {fail_reason}")
    else:
        lines.append(f"- Selected cluster: {selected_cluster}")
        lines.append(
            "- Rationale: satisfies distance threshold with maximal person coverage; stability exception applied if needed."
        )
    lines.append("")
    lines.append("## Rejected Cluster Reasons")
    for cid, stat in sorted(cluster_stats.items()):
        if cid == selected_cluster:
            continue
        reason = []
        if stat["mean_intra_cluster_distance"] > config.PREFERRED_DISTANCE_THRESHOLD:
            reason.append("distance above preferred")
        if stat["mean_intra_cluster_distance"] > config.FALLBACK_DISTANCE_THRESHOLD:
            reason.append("distance above fallback")
        if not reason:
            reason.append("fewer persons than selected cluster")
        lines.append(f"- Cluster {cid}: {'; '.join(reason)}")
    lines.append("")
    lines.append("## Checklist")
    lines.append(f"- Thresholds satisfied: {'yes' if selected_cluster is not None else 'no'}")
    lines.append("- Why this cluster was optimal: maximizes persons under thresholds; stability exception considered.")
    if selected_cluster is not None:
        alt_clusters = [
            cid
            for cid, stat in cluster_stats.items()
            if cid != selected_cluster and stat["mean_intra_cluster_distance"] <= config.FALLBACK_DISTANCE_THRESHOLD
        ]
        if alt_clusters:
            lines.append(f"- Alternatives would lose persons: {', '.join(str(c) for c in alt_clusters)}")
        else:
            lines.append("- No eligible alternative clusters.")
    else:
        lines.append("- No cluster selected; see fail reason above.")
    lines.append("")
    lines.append("## Video Quality Summary")
    if video_quality:
        lines.extend(video_quality)
    elif any("video" in w.lower() for w in warnings):
        lines.append("- Video processing skipped due to missing ffmpeg.")
    else:
        lines.append("- No videos were processed.")
    lines.append("")
    lines.append("## Final Recommendation")
    if selected_cluster is not None:
        lines.append(f"- Persons in selected cluster: {cluster_stats[selected_cluster]['num_persons']}")
        lines.append(f"- Achieved mean cosine distance: {cluster_stats[selected_cluster]['mean_intra_cluster_distance']:.4f}")
    else:
        lines.append("- No selection; refer to fail reason above.")
    lines.append("")
    if distance_matrix is not None and distance_matrix.size > 0:
        lines.append("## Inter-Person Distance Matrix (cosine)")
        lines.append("- Matrix reported as JSON for reproducibility.")
        lines.append(f"`{distance_matrix.tolist()}`")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    if not ANALYSIS_CSV.exists():
        raise FileNotFoundError("analysis.csv not found. Run analyze_assets.py first.")

    df = pd.read_csv(ANALYSIS_CSV)
    notes = NOTES_PATH.read_text(encoding="utf-8").splitlines() if NOTES_PATH.exists() else []

    image_df = df[df["source_type"] == "image"].copy()
    if not image_df.empty:
        image_df["face_detected"] = image_df["face_detected"].astype(bool)
    detection_rate = float(image_df["face_detected"].mean()) if not image_df.empty else 0.0

    usable_mask = (
        (image_df["face_detected"] == True)
        & (image_df["face_area_ratio"] >= config.MIN_FACE_AREA_RATIO)
        & (image_df["sharpness_laplacian"] >= config.MIN_SHARPNESS)
        & (image_df["brightness_mean"] >= config.MIN_BRIGHTNESS)
        & (image_df["brightness_mean"] <= config.MAX_BRIGHTNESS)
    )
    usable_images = image_df[usable_mask].copy()
    usable_images = usable_images[usable_images["person_id"] != "UNKNOWN"]

    person_stats = compute_person_stats(usable_images)
    person_stats = {
        pid: stat for pid, stat in person_stats.items() if stat.usable_image_count >= config.MIN_IMAGES_PER_PERSON
    }

    aggregate_quality_scores(df[df["person_id"] != "UNKNOWN"], person_stats)

    fail_reason = ""
    if len(person_stats) < 3:
        fail_reason = "Insufficient valid persons (<3). Consider relaxing MIN_IMAGES_PER_PERSON."

    persons = [person_stats[k] for k in sorted(person_stats)]
    mean_embs = [p.mean_embedding for p in persons]
    distance_matrix = cosine_distances(mean_embs, mean_embs) if mean_embs else np.array([])

    if fail_reason:
        cluster_stats: Dict[int, Dict[str, float]] = {}
        video_quality = build_video_quality_summary(df)
        generate_report(
            person_stats,
            cluster_stats,
            None,
            notes,
            detection_rate,
            fail_reason,
            video_quality,
            distance_matrix,
        )
        pd.DataFrame(
            columns=[
                "person_id",
                "cluster_id",
                "mean_distance_to_centroid",
                "usable_image_count",
                "quality_score",
                "selected_cluster_flag",
            ]
        ).to_csv(CANDIDATE_CSV, index=False)
        return

    labels = cluster_persons(mean_embs)

    for person, label in zip(persons, labels):
        person.cluster_id = int(label)

    cluster_stats = compute_cluster_stats(person_stats, labels)

    selected_cluster, fail_reason = select_cluster(cluster_stats)

    video_quality = build_video_quality_summary(df)

    rows = []
    for pid, stat in sorted(person_stats.items()):
        rows.append(
            {
                "person_id": pid,
                "cluster_id": stat.cluster_id,
                "mean_distance_to_centroid": stat.mean_distance_to_centroid,
                "usable_image_count": stat.usable_image_count,
                "quality_score": stat.quality_score,
                "selected_cluster_flag": stat.cluster_id == selected_cluster if selected_cluster is not None else False,
            }
        )
    pd.DataFrame(rows).to_csv(CANDIDATE_CSV, index=False)

    generate_report(
        person_stats,
        cluster_stats,
        selected_cluster,
        notes,
        detection_rate,
        fail_reason,
        video_quality,
        distance_matrix,
    )


if __name__ == "__main__":
    main()
