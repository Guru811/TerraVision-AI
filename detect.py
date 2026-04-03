import rasterio
import numpy as np

# ─────────────────────────────────────────────
#  Fire classification thresholds
#  Based on VIIRS radiance characteristics:
#  - Natural wildfires: large clusters, brief, high radiance
#  - Agricultural burns: seasonal, medium radiance, edge-of-forest
#  - Illegal camps/logging: small persistent clusters, moderate radiance
# ─────────────────────────────────────────────

THRESHOLD          = 3.0    # minimum delta to flag (nW/cm²/sr)
WILDFIRE_RADIANCE  = 15.0   # very high spike = likely wildfire
CAMP_MAX_CLUSTER   = 12     # illegal camps are small (pixels)
AGRI_RADIANCE_MAX  = 8.0    # agricultural burns stay moderate


def get_neighbors(r, c, rows, cols):
    """Return valid 8-connected neighbors."""
    neighbors = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append((nr, nc))
    return neighbors


def find_clusters(mask):
    """Label connected components (pixel clusters) using flood fill."""
    rows, cols = mask.shape
    labels = np.zeros_like(mask, dtype=int)
    current_label = 0
    cluster_sizes = {}

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
                    for nr, nc in get_neighbors(cr, cc, rows, cols):
                        if mask[nr, nc] and labels[nr, nc] == 0:
                            stack.append((nr, nc))
                cluster_sizes[current_label] = size

    return labels, cluster_sizes


def classify_alert(delta_val, cluster_size):
    """
    Classify a suspicious light source into one of four categories.

    Returns: (category, severity, confidence_pct)

    Logic:
      1. Very high radiance spike + large cluster  → Natural wildfire
      2. Moderate radiance + very large cluster    → Agricultural burn
      3. Low-moderate radiance + small cluster     → Illegal encroachment
      4. Everything else                           → Unclassified anomaly
    """
    if delta_val >= WILDFIRE_RADIANCE and cluster_size > CAMP_MAX_CLUSTER:
        return "natural_wildfire", "info", 88

    if delta_val <= AGRI_RADIANCE_MAX and cluster_size > CAMP_MAX_CLUSTER * 3:
        return "agricultural_burn", "warning", 74

    if delta_val >= THRESHOLD and cluster_size <= CAMP_MAX_CLUSTER:
        severity = "high" if delta_val >= THRESHOLD * 2 else "medium"
        confidence = min(95, int(60 + (delta_val / WILDFIRE_RADIANCE) * 35
                                 + max(0, (CAMP_MAX_CLUSTER - cluster_size)) * 2))
        return "illegal_encroachment", severity, confidence

    return "anomaly", "low", 45


def detect_encroachments(baseline_path, current_path, threshold=THRESHOLD):
    """
    Main detection function.
    Returns list of alert dicts with classification, coordinates, severity.
    """
    with rasterio.open(baseline_path) as b:
        baseline  = b.read(1).astype(float)
        transform = b.transform

    with rasterio.open(current_path) as c:
        current = c.read(1).astype(float)

    # Radiance delta
    delta = current - baseline
    suspicious_mask = (delta > threshold) & np.isfinite(delta)

    # Cluster analysis
    labels, cluster_sizes = find_clusters(suspicious_mask)

    rows, cols = np.where(suspicious_mask)
    alerts = []
    seen_labels = set()

    for r, c in zip(rows, cols):
        lbl = labels[r, c]
        if lbl in seen_labels:
            continue          # one alert per cluster centroid
        seen_labels.add(lbl)

        cluster_size = cluster_sizes.get(lbl, 1)

        # Get centroid of cluster
        cluster_pixels = np.argwhere(labels == lbl)
        centroid_r = int(cluster_pixels[:, 0].mean())
        centroid_c = int(cluster_pixels[:, 1].mean())
        lon, lat = rasterio.transform.xy(transform, centroid_r, centroid_c)

        delta_val = float(delta[centroid_r, centroid_c])
        category, severity, confidence = classify_alert(delta_val, cluster_size)

        alerts.append({
            "lat":          lat,
            "lon":          lon,
            "delta":        round(delta_val, 2),
            "severity":     severity,
            "category":     category,
            "cluster_size": cluster_size,
            "confidence":   confidence,
        })

    # Summary
    categories = {}
    for a in alerts:
        categories[a["category"]] = categories.get(a["category"], 0) + 1

    print(f"\n{'='*50}")
    print(f"  TerraVision Detection Summary")
    print(f"{'='*50}")
    print(f"  Total suspicious pixels : {suspicious_mask.sum()}")
    print(f"  Unique clusters found   : {len(alerts)}")
    for cat, count in categories.items():
        print(f"  {cat:<28}: {count}")
    print(f"{'='*50}\n")

    return alerts