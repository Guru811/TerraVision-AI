

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import rasterio
import rasterio.transform


# ──────────────────────────────────────────────────────────────────────────────
# 1. TUNEABLE PARAMETER SET
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DetectionParams:
    """All tuneable thresholds in one place.  Load from JSON with from_json()."""

    # Radiance delta thresholds (nW / cm² / sr)
    delta_min_flag: float = 2.5
    delta_agri_max: float = 9.0
    delta_wildfire_min: float = 14.0
    delta_encroach_max: float = 13.0
    delta_anomaly_min: float = 20.0

    # Cluster size (pixels)
    size_min_valid: int = 3
    size_encroach_max: int = 18
    size_agri_min: int = 25
    size_wildfire_min: int = 15
    size_anomaly_max: int = 20

    # Shape features
    aspect_agri_min: float = 1.8
    compactness_wildfire_max: float = 0.65
    compactness_agri_min: float = 0.55
    convexity_encroach_max: float = 0.80
    uniformity_agri_min: float = 0.55

    # Spread / growth proxy
    spread_rate_wildfire_min: float = 0.40

    # Scoring weights
    w_radiance: float = 0.35
    w_size: float = 0.25
    w_shape: float = 0.25
    w_context: float = 0.15

    @classmethod
    def from_json(cls, path: str) -> "DetectionParams":
        with open(path) as f:
            return cls(**json.load(f))


DEFAULT_PARAMS = DetectionParams()


# ──────────────────────────────────────────────────────────────────────────────
# 2. CONNECTED-COMPONENT CLUSTERING
# ──────────────────────────────────────────────────────────────────────────────

def _neighbors_8(r: int, c: int, rows: int, cols: int) -> List[Tuple[int, int]]:
    out = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                out.append((nr, nc))
    return out


def find_clusters(mask: np.ndarray) -> Tuple[np.ndarray, Dict[int, int]]:
    """Label 8-connected components; return (label_map, {label: size})."""
    rows, cols = mask.shape
    labels = np.zeros_like(mask, dtype=np.int32)
    current_label = 0
    sizes: Dict[int, int] = {}

    for r in range(rows):
        for c in range(cols):
            if mask[r, c] and labels[r, c] == 0:
                current_label += 1
                stack = [(r, c)]
                size = 0
                while stack:
                    cr, cc = stack.pop()
                    if labels[cr, cc] != 0:
                        continue
                    labels[cr, cc] = current_label
                    size += 1
                    for nr, nc in _neighbors_8(cr, cc, rows, cols):
                        if mask[nr, nc] and labels[nr, nc] == 0:
                            stack.append((nr, nc))
                sizes[current_label] = size

    return labels, sizes


# ──────────────────────────────────────────────────────────────────────────────
# 3. FEATURE EXTRACTION
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ClusterFeatures:
    label: int
    centroid_row: int
    centroid_col: int
    cluster_size: int
    delta_mean: float
    delta_max: float
    delta_std: float
    aspect_ratio: float       # max(W/H, H/W)  ≥ 1
    compactness: float        # 4π·A / P²  ∈ (0, 1]
    convexity: float          # A / convex_hull_area  ∈ (0, 1]
    edge_ratio: float         # boundary pixels / total pixels
    spread_rate: float        # size / bbox_diagonal²
    interior_uniformity: float  # 1 – cv  (higher = more uniform burn)
    bbox_area: int


def _extract_features(label_map: np.ndarray, lbl: int,
                      delta: np.ndarray) -> ClusterFeatures:
    pixels = np.argwhere(label_map == lbl)
    rows_px = pixels[:, 0]
    cols_px = pixels[:, 1]
    size = len(pixels)

    cr = int(rows_px.mean())
    cc = int(cols_px.mean())

    vals = delta[rows_px, cols_px]
    d_mean = float(vals.mean())
    d_max  = float(vals.max())
    d_std  = float(vals.std()) if size > 1 else 0.0

    r_min, r_max = int(rows_px.min()), int(rows_px.max())
    c_min, c_max = int(cols_px.min()), int(cols_px.max())
    bb_h = max(r_max - r_min + 1, 1)
    bb_w = max(c_max - c_min + 1, 1)
    bbox_area = bb_h * bb_w

    aspect_ratio = max(bb_w / bb_h, bb_h / bb_w)
    spread_rate = size / bbox_area

    # Perimeter: count pixels with at least one background 8-neighbour
    r_off, c_off = r_min, c_min
    local = np.zeros((bb_h, bb_w), dtype=bool)
    local[rows_px - r_off, cols_px - c_off] = True
    perimeter = 0
    for pr, pc in zip(rows_px - r_off, cols_px - c_off):
        is_boundary = False
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr2, nc2 = pr + dr, pc + dc
                if not (0 <= nr2 < bb_h and 0 <= nc2 < bb_w) or not local[nr2, nc2]:
                    is_boundary = True
                    break
            if is_boundary:
                break
        if is_boundary:
            perimeter += 1

    perimeter = max(perimeter, 1)
    edge_ratio = perimeter / size

    # Compactness: 4π·A / P²  (circle = 1, elongated/spiky shapes approach 0)
    compactness = min(1.0, (4 * math.pi * size) / (perimeter ** 2))

    # Convexity: use scipy ConvexHull when available; fall back to bounding-box area
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(pixels)
        hull_area = hull.volume   # 2-D: volume == area
    except Exception:
        hull_area = float(bbox_area)
    convexity = min(1.0, size / max(hull_area, 1))

    # Interior uniformity: 1 – coefficient of variation (σ/μ)
    if d_mean > 0:
        interior_uniformity = max(0.0, 1.0 - (d_std / d_mean))
    else:
        interior_uniformity = 0.0

    return ClusterFeatures(
        label=lbl,
        centroid_row=cr,
        centroid_col=cc,
        cluster_size=size,
        delta_mean=d_mean,
        delta_max=d_max,
        delta_std=d_std,
        aspect_ratio=aspect_ratio,
        compactness=compactness,
        convexity=convexity,
        edge_ratio=edge_ratio,
        spread_rate=spread_rate,
        interior_uniformity=interior_uniformity,
        bbox_area=bbox_area,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4. MULTI-STAGE RULE ENGINE WITH WEIGHTED SCORING
# ──────────────────────────────────────────────────────────────────────────────

def _score_natural_wildfire(f: ClusterFeatures, p: DetectionParams) -> float:
    """
    Wildfire signatures:
      • Very high peak radiance
      • Large, spreading cluster
      • Irregular shape (low compactness, low convexity)
      • Fills bounding box well (high spread_rate)
      • High radiance variance (fire front vs interior)
    """
    r_score = min(1.0, max(0.0, (f.delta_max - p.delta_wildfire_min) /
                                 (p.delta_wildfire_min * 1.5)))
    s_score = min(1.0, max(0.0, (f.cluster_size - p.size_wildfire_min) /
                                 (p.size_wildfire_min * 4)))
    shape_score = (
        (1.0 - f.compactness) * 0.5 +
        min(1.0, f.spread_rate / p.spread_rate_wildfire_min) * 0.3 +
        (1.0 - f.convexity) * 0.2
    )
    # Coefficient of variation captures the radiance gradient across the fire front
    cv = f.delta_std / max(f.delta_mean, 0.001)
    ctx_score = min(1.0, cv / 0.5)

    score = (p.w_radiance * r_score +
             p.w_size    * s_score +
             p.w_shape   * shape_score +
             p.w_context * ctx_score)

    if f.delta_max < p.delta_wildfire_min * 0.7:
        score *= 0.3
    if f.cluster_size < p.size_wildfire_min:
        score *= 0.4

    return round(score, 4)


def _score_agricultural_burn(f: ClusterFeatures, p: DetectionParams) -> float:
    """
    Agricultural burn signatures:
      • Moderate radiance (controlled fire)
      • Large cluster, rectangular/elongated shape
      • High interior uniformity (even burn across field)
    """
    if f.delta_mean <= p.delta_min_flag:
        r_score = 0.0
    elif f.delta_mean <= p.delta_agri_max:
        r_score = (f.delta_mean - p.delta_min_flag) / (p.delta_agri_max - p.delta_min_flag)
    else:
        # Penalise radiance exceeding the agricultural ceiling
        r_score = max(0.0, 1.0 - (f.delta_mean - p.delta_agri_max) / p.delta_agri_max)

    s_score = min(1.0, max(0.0, (f.cluster_size - p.size_agri_min) /
                                 (p.size_agri_min * 3)))

    shape_score = (
        min(1.0, (f.aspect_ratio - 1.0) / (p.aspect_agri_min - 1.0 + 0.01)) * 0.4 +
        min(1.0, f.compactness / p.compactness_agri_min) * 0.3 +
        f.interior_uniformity * 0.3
    )

    ctx_score = f.interior_uniformity

    score = (p.w_radiance * r_score +
             p.w_size    * s_score +
             p.w_shape   * shape_score +
             p.w_context * ctx_score)

    if f.delta_max > p.delta_wildfire_min:
        score *= 0.5
    if f.cluster_size < p.size_agri_min:
        score *= 0.3

    return round(score, 4)


def _score_illegal_encroachment(f: ClusterFeatures, p: DetectionParams) -> float:
    """
    Illegal encroachment signatures (camps, logging, charcoal kilns):
      • Small cluster
      • Low-to-moderate radiance (campfire / kiln range)
      • High edge_ratio (small clusters are predominantly boundary pixels)
    """
    if f.delta_mean < p.delta_min_flag:
        r_score = 0.0
    elif f.delta_mean <= p.delta_encroach_max:
        r_score = 0.6 + 0.4 * ((f.delta_mean - p.delta_min_flag) /
                                (p.delta_encroach_max - p.delta_min_flag))
    else:
        r_score = max(0.0, 1.0 - (f.delta_mean - p.delta_encroach_max) /
                      p.delta_encroach_max)

    if f.cluster_size <= p.size_encroach_max:
        s_score = 1.0 - (f.cluster_size - 1) / (p.size_encroach_max * 1.5)
        s_score = max(0.0, s_score)
    else:
        s_score = max(0.0, 1.0 - (f.cluster_size - p.size_encroach_max) /
                      (p.size_agri_min - p.size_encroach_max + 1))

    shape_score = (
        f.edge_ratio * 0.5 +
        (1.0 - abs(f.spread_rate - 0.5)) * 0.5
    )

    # Without a land-cover map, contextual discrimination is limited
    ctx_score = 0.5

    score = (p.w_radiance * r_score +
             p.w_size    * s_score +
             p.w_shape   * shape_score +
             p.w_context * ctx_score)

    if f.cluster_size > p.size_agri_min:
        score *= 0.3
    if f.delta_max > p.delta_wildfire_min:
        score *= 0.4

    return round(score, 4)


def _score_anomaly(f: ClusterFeatures, p: DetectionParams) -> float:
    """
    Anomaly signatures (industrial flare, gas burn-off, sensor artifact):
      • Extreme radiance spike
      • Very small, pinpoint cluster
      • High compactness or high interior uniformity (sensor artifact)
    """
    r_score = min(1.0, max(0.0, (f.delta_max - p.delta_anomaly_min) /
                                 p.delta_anomaly_min))
    s_score = max(0.0, 1.0 - f.cluster_size / (p.size_anomaly_max * 2))
    shape_score = (
        f.compactness * 0.5 +
        f.interior_uniformity * 0.5
    )
    ctx_score = min(1.0, f.delta_max / (p.delta_anomaly_min * 2))

    score = (p.w_radiance * r_score +
             p.w_size    * s_score +
             p.w_shape   * shape_score +
             p.w_context * ctx_score)

    return round(score, 4)


# ──────────────────────────────────────────────────────────────────────────────
# 5. CLASSIFICATION ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_LABELS = [
    "natural_wildfire",
    "agricultural_burn",
    "illegal_encroachment",
    "anomaly",
]

SEVERITY_MAP = {
    "natural_wildfire":     "critical",
    "agricultural_burn":    "warning",
    "illegal_encroachment": "high",
    "anomaly":              "medium",
    "unclassified":         "low",
}


def classify_cluster(f: ClusterFeatures,
                     p: DetectionParams = DEFAULT_PARAMS
                     ) -> Tuple[str, str, int, Dict[str, float]]:
    """
    Run all four scoring functions and pick the winner.

    Returns
    -------
    category : str
    severity : str
    confidence : int  (0–100)
    scores   : dict  (raw scores for all categories)
    """
    if f.cluster_size < p.size_min_valid:
        return "unclassified", "low", 10, {}

    scores = {
        "natural_wildfire":     _score_natural_wildfire(f, p),
        "agricultural_burn":    _score_agricultural_burn(f, p),
        "illegal_encroachment": _score_illegal_encroachment(f, p),
        "anomaly":              _score_anomaly(f, p),
    }

    best_cat = max(scores, key=lambda k: scores[k])
    best_score = scores[best_cat]

    sorted_scores = sorted(scores.values(), reverse=True)
    margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else sorted_scores[0]

    # Sigmoid-like mapping; penalise when top two scores are close (ambiguous classification)
    base_conf = int(min(97, max(20, best_score * 120)))
    margin_penalty = int(max(0, (0.15 - margin) / 0.15 * 20))
    confidence = max(15, base_conf - margin_penalty)

    if best_score < 0.20:
        return "unclassified", "low", confidence, scores

    severity = SEVERITY_MAP.get(best_cat, "low")
    return best_cat, severity, confidence, scores


# ──────────────────────────────────────────────────────────────────────────────
# 6. MAIN DETECTION PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

def detect_encroachments(
    baseline_path: str,
    current_path:  str,
    params: DetectionParams = DEFAULT_PARAMS,
    params_json: Optional[str] = None,
    verbose: bool = True,
) -> List[Dict]:
    """
    Full detection pipeline.

    Parameters
    ----------
    baseline_path : path to baseline radiance GeoTIFF
    current_path  : path to current radiance GeoTIFF
    params        : DetectionParams (override defaults programmatically)
    params_json   : path to JSON config (overrides `params` if given)
    verbose       : print summary table

    Returns
    -------
    List of alert dicts, one per cluster, sorted by severity then confidence.
    """
    if params_json:
        params = DetectionParams.from_json(params_json)

    with rasterio.open(baseline_path) as src:
        baseline  = src.read(1).astype(float)
        transform = src.transform

    with rasterio.open(current_path) as src:
        current = src.read(1).astype(float)

    delta = current - baseline
    suspicious_mask = (delta > params.delta_min_flag) & np.isfinite(delta)

    labels, cluster_sizes = find_clusters(suspicious_mask)

    unique_labels = [lbl for lbl, sz in cluster_sizes.items()
                     if sz >= params.size_min_valid]

    alerts = []
    for lbl in unique_labels:
        features = _extract_features(labels, lbl, delta)
        category, severity, confidence, raw_scores = classify_cluster(features, params)

        lon, lat = rasterio.transform.xy(
            transform, features.centroid_row, features.centroid_col
        )

        alerts.append({
            "lat":          float(lat),
            "lon":          float(lon),
            "delta_mean":   round(features.delta_mean, 3),
            "delta_max":    round(features.delta_max, 3),
            "severity":     severity,
            "category":     category,
            "cluster_size": features.cluster_size,
            "confidence":   confidence,
            "shape": {
                "aspect_ratio":          round(features.aspect_ratio, 3),
                "compactness":           round(features.compactness, 3),
                "convexity":             round(features.convexity, 3),
                "edge_ratio":            round(features.edge_ratio, 3),
                "spread_rate":           round(features.spread_rate, 3),
                "interior_uniformity":   round(features.interior_uniformity, 3),
            },
            "scores": {k: round(v, 4) for k, v in raw_scores.items()},
        })

    severity_rank = {"critical": 0, "high": 1, "warning": 2, "medium": 3, "low": 4}
    alerts.sort(key=lambda a: (severity_rank.get(a["severity"], 99),
                                -a["confidence"]))

    if verbose:
        _print_summary(suspicious_mask, alerts)

    return alerts


# ──────────────────────────────────────────────────────────────────────────────
# 7. SUMMARY DISPLAY
# ──────────────────────────────────────────────────────────────────────────────

def _print_summary(suspicious_mask: np.ndarray, alerts: List[Dict]) -> None:
    categories: Dict[str, int] = {}
    for a in alerts:
        categories[a["category"]] = categories.get(a["category"], 0) + 1

    SEV_ICONS = {
        "critical": "🔴",
        "high":     "🟠",
        "warning":  "🟡",
        "medium":   "🔵",
        "low":      "⚪",
    }

    print(f"\n{'═'*58}")
    print(f"  TerraVision  ·  Advanced Fire & Anomaly Classifier")
    print(f"{'═'*58}")
    print(f"  Suspicious pixels flagged : {suspicious_mask.sum()}")
    print(f"  Unique clusters detected  : {len(alerts)}")
    print(f"{'─'*58}")
    print(f"  {'Category':<28}  {'Count':>5}  {'Avg Conf':>8}")
    print(f"{'─'*58}")
    for cat in ["natural_wildfire", "agricultural_burn",
                "illegal_encroachment", "anomaly", "unclassified"]:
        cat_alerts = [a for a in alerts if a["category"] == cat]
        if not cat_alerts:
            continue
        avg_conf = sum(a["confidence"] for a in cat_alerts) / len(cat_alerts)
        sev = SEVERITY_MAP.get(cat, "low")
        icon = SEV_ICONS.get(sev, "  ")
        print(f"  {icon} {cat:<26}  {len(cat_alerts):>5}  {avg_conf:>7.0f}%")
    print(f"{'═'*58}\n")

    print(f"  Top alerts (highest severity + confidence):")
    print(f"  {'#':<3}  {'Category':<22}  {'Sev':<8}  {'Conf':>5}  {'Lat':>9}  {'Lon':>10}")
    print(f"  {'─'*70}")
    for i, a in enumerate(alerts[:5], 1):
        print(f"  {i:<3}  {a['category']:<22}  {a['severity']:<8}  "
              f"{a['confidence']:>4}%  {a['lat']:>9.4f}  {a['lon']:>10.4f}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# 8. ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json as _json

    parser = argparse.ArgumentParser(description="TerraVision fire classifier")
    parser.add_argument("baseline", help="Baseline radiance GeoTIFF")
    parser.add_argument("current",  help="Current radiance GeoTIFF")
    parser.add_argument("--params", default=None, help="JSON params file")
    parser.add_argument("--out",    default=None, help="Save alerts JSON to file")
    args = parser.parse_args()

    results = detect_encroachments(
        args.baseline,
        args.current,
        params_json=args.params,
        verbose=True,
    )

    if args.out:
        Path(args.out).write_text(_json.dumps(results, indent=2))
        print(f"  Alerts written to {args.out}")