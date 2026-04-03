import streamlit as st
import folium
from streamlit_folium import st_folium
from detect import detect_encroachments
import os
import time

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TerraVision AI — Forest Guardian",
    layout="wide",
    page_icon="🌿",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS — nature/forest theme ──────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Root palette ── */
:root {
    --forest-deep:   #0a1a0f;
    --forest-dark:   #0f2418;
    --forest-mid:    #1a3a25;
    --forest-light:  #2d5a3d;
    --teal-primary:  #2dd4a0;
    --teal-soft:     #1db888;
    --teal-dim:      #0f6e52;
    --leaf-gold:     #a8d08d;
    --mist:          #c8e6d4;
    --bark:          #8fbc8f;
    --alert-red:     #ff5252;
    --alert-orange:  #ff9800;
    --alert-blue:    #4fc3f7;
    --alert-green:   #69f0ae;
}

/* ── Global reset ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: var(--forest-deep) !important;
    color: var(--mist) !important;
}

/* ── Animated leaf-particle background ── */
.stApp {
    background:
        radial-gradient(ellipse at 20% 50%, rgba(45,212,160,0.04) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 20%, rgba(29,184,136,0.05) 0%, transparent 50%),
        var(--forest-deep) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--forest-dark) 0%, var(--forest-deep) 100%) !important;
    border-right: 1px solid rgba(45,212,160,0.15) !important;
}
[data-testid="stSidebar"] * { color: var(--mist) !important; }

/* ── Header banner ── */
.terra-header {
    background: linear-gradient(135deg, var(--forest-mid) 0%, var(--forest-dark) 60%, rgba(45,212,160,0.08) 100%);
    border: 1px solid rgba(45,212,160,0.2);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.terra-header::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(45,212,160,0.08) 0%, transparent 70%);
    border-radius: 50%;
    animation: breathe 4s ease-in-out infinite;
}
.terra-header::after {
    content: '';
    position: absolute;
    bottom: -60px; left: 30%;
    width: 300px; height: 120px;
    background: radial-gradient(ellipse, rgba(29,184,136,0.05) 0%, transparent 70%);
    animation: breathe 6s ease-in-out infinite reverse;
}
@keyframes breathe {
    0%, 100% { transform: scale(1); opacity: 0.6; }
    50%       { transform: scale(1.15); opacity: 1; }
}
.terra-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.2rem;
    font-weight: 600;
    color: var(--teal-primary) !important;
    margin: 0 0 4px 0;
    letter-spacing: -0.5px;
}
.terra-subtitle {
    font-size: 0.95rem;
    color: var(--bark) !important;
    font-weight: 300;
    letter-spacing: 0.5px;
}
.terra-tagline {
    font-size: 0.8rem;
    color: rgba(45,212,160,0.6) !important;
    margin-top: 10px;
    font-style: italic;
}

/* ── Live pulse indicator ── */
.live-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(45,212,160,0.1);
    border: 1px solid rgba(45,212,160,0.3);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.75rem;
    color: var(--teal-primary) !important;
    margin-top: 12px;
}
.pulse-dot {
    width: 7px; height: 7px;
    background: var(--teal-primary);
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(45,212,160,0.7); }
    50%       { box-shadow: 0 0 0 6px rgba(45,212,160,0); }
}

/* ── Metric cards ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 20px 0;
}
.metric-card {
    background: var(--forest-mid);
    border: 1px solid rgba(45,212,160,0.15);
    border-radius: 12px;
    padding: 16px 18px;
    transition: border-color 0.3s, transform 0.2s;
}
.metric-card:hover {
    border-color: rgba(45,212,160,0.4);
    transform: translateY(-2px);
}
.metric-val {
    font-family: 'Playfair Display', serif;
    font-size: 1.8rem;
    font-weight: 600;
    line-height: 1;
    margin-bottom: 4px;
}
.metric-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--bark) !important;
}

/* ── Legend cards ── */
.legend-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin: 16px 0;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(15,36,24,0.8);
    border: 1px solid rgba(45,212,160,0.1);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.78rem;
}
.legend-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ── Scan button ── */
.stButton > button {
    background: linear-gradient(135deg, var(--teal-dim) 0%, var(--forest-light) 100%) !important;
    color: var(--teal-primary) !important;
    border: 1px solid rgba(45,212,160,0.4) !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.5px !important;
    padding: 0.6rem 1.2rem !important;
    transition: all 0.25s ease !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1a7a5a 0%, var(--teal-dim) 100%) !important;
    border-color: var(--teal-primary) !important;
    box-shadow: 0 0 20px rgba(45,212,160,0.2) !important;
    transform: translateY(-1px) !important;
}

/* ── Select / Slider labels ── */
.stSelectbox label, .stSlider label,
[data-testid="stSidebar"] label {
    color: var(--bark) !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
}

/* ── Slider accent ── */
[data-testid="stSlider"] [role="slider"] {
    background: var(--teal-primary) !important;
}

/* ── Success / info / warning alerts ── */
.stAlert { border-radius: 10px !important; border-left-width: 3px !important; }

/* ── Expander ── */
.streamlit-expanderHeader {
    background: var(--forest-mid) !important;
    border-radius: 8px !important;
    color: var(--teal-primary) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--forest-dark); }
::-webkit-scrollbar-thumb { background: var(--teal-dim); border-radius: 4px; }

/* ── Divider ── */
hr { border-color: rgba(45,212,160,0.1) !important; }

/* ── Section header ── */
.section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    color: var(--teal-primary) !important;
    border-bottom: 1px solid rgba(45,212,160,0.15);
    padding-bottom: 6px;
    margin: 18px 0 12px 0;
}
</style>
""", unsafe_allow_html=True)

# ─── Helper: coloured map markers per category ─────────────────────────────────
CATEGORY_STYLE = {
    "illegal_encroachment": {"color": "#ff5252", "icon": "exclamation-triangle", "label": "Illegal encroachment"},
    "natural_wildfire":     {"color": "#4fc3f7", "icon": "fire",                 "label": "Natural wildfire"},
    "agricultural_burn":    {"color": "#ff9800", "icon": "leaf",                 "label": "Agricultural burn"},
    "anomaly":              {"color": "#b0bec5", "icon": "question-circle",       "label": "Unclassified anomaly"},
}

# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-title">Forest Region</div>', unsafe_allow_html=True)
    region = st.selectbox("Select region", [
        "Western Ghats, India",
        "Amazon Basin, Brazil",
        "Borneo Rainforest",
        "Congo Basin, Africa",
        "Sundarbans, Bangladesh",
    ], label_visibility="collapsed")

    st.markdown('<div class="section-title">Detection Settings</div>', unsafe_allow_html=True)
    threshold = st.slider(
        "Alert threshold (nW/cm²/sr)",
        min_value=1.0, max_value=15.0, value=5.0, step=0.5,
        help="Higher = fewer but more certain alerts. Recommended: 5–8 to reduce noise."
    )
    min_cluster = st.slider(
        "Min cluster size (pixels)",
        min_value=1, max_value=20, value=1,
        help="Filter out lone pixels. Camps typically appear as 2–8 pixel clusters."
    )

    st.markdown('<div class="section-title">Filter by Type</div>', unsafe_allow_html=True)
    show_encroachment = st.checkbox("Illegal encroachment", value=True)
    show_wildfire     = st.checkbox("Natural wildfires",    value=True)
    show_agri         = st.checkbox("Agricultural burns",   value=True)
    show_anomaly      = st.checkbox("Unclassified anomaly", value=False)

    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.72rem; color: #4a7a5a; line-height: 1.7;'>
    📡 Data source: NASA VIIRS DNB<br>
    📅 Baseline: 5-yr median 2019–2023<br>
    🛰️ Resolution: 500m per pixel<br>
    🔄 Updated: Daily
    </div>
    """, unsafe_allow_html=True)

# ─── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="terra-header">
    <div class="terra-title">🌿 TerraVision AI</div>
    <div class="terra-subtitle">Satellite Forest Guardian · Illegal Encroachment Detection</div>
    <div class="terra-tagline">"Every tree that falls in silence, we hear from space."</div>
    <div class="live-badge">
        <div class="pulse-dot"></div>
        VIIRS satellite feed · Live
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Legend ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="legend-grid">
    <div class="legend-item">
        <div class="legend-dot" style="background:#ff5252"></div>
        <span>Illegal encroachment — small persistent cluster, moderate radiance</span>
    </div>
    <div class="legend-item">
        <div class="legend-dot" style="background:#4fc3f7"></div>
        <span>Natural wildfire — large cluster, very high radiance spike</span>
    </div>
    <div class="legend-item">
        <div class="legend-dot" style="background:#ff9800"></div>
        <span>Agricultural burn — large seasonal cluster, moderate radiance</span>
    </div>
    <div class="legend-item">
        <div class="legend-dot" style="background:#b0bec5"></div>
        <span>Unclassified anomaly — does not match known patterns</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Scan button ───────────────────────────────────────────────────────────────
col_btn, col_space = st.columns([1, 3])
with col_btn:
    scan = st.button("🔍  Run Satellite Scan", use_container_width=True)

# ─── Map + results ─────────────────────────────────────────────────────────────
region_coords = {
    "Western Ghats, India":    [12.0, 76.5],
    "Amazon Basin, Brazil":    [-3.5, -60.0],
    "Borneo Rainforest":       [1.5,  114.0],
    "Congo Basin, Africa":     [-1.0, 24.0],
    "Sundarbans, Bangladesh":  [21.9, 89.2],
}
center = region_coords.get(region, [12.0, 76.5])

m = folium.Map(
    location=center,
    zoom_start=7,
    tiles="CartoDB dark_matter",
    prefer_canvas=True,
)

# Add a subtle forest-boundary rectangle (demo boundary)
folium.Rectangle(
    bounds=[[center[0]-3, center[1]-3], [center[0]+3, center[1]+3]],
    color="#2dd4a0",
    weight=1.5,
    fill=True,
    fill_color="#2dd4a0",
    fill_opacity=0.04,
    tooltip="Protected forest boundary",
).add_to(m)

if scan:
    baseline_file = "viirs_baseline.tif"
    current_file  = "viirs_current.tif"

    if not os.path.exists(baseline_file) or not os.path.exists(current_file):
        st.error("⚠️  TIF files not found. Run `gee_export.py` first and place viirs_baseline.tif and viirs_current.tif in this folder.")
    else:
        with st.spinner("🛰️  Analysing VIIRS satellite data — comparing against 5-year baseline..."):
            time.sleep(0.5)
            all_alerts = detect_encroachments(baseline_file, current_file, threshold)

        # Apply cluster size filter
        all_alerts = [a for a in all_alerts if a["cluster_size"] >= min_cluster]

        # Apply category filters
        active_cats = set()
        if show_encroachment: active_cats.add("illegal_encroachment")
        if show_wildfire:     active_cats.add("natural_wildfire")
        if show_agri:         active_cats.add("agricultural_burn")
        if show_anomaly:      active_cats.add("anomaly")
        alerts = [a for a in all_alerts if a["category"] in active_cats]

        # ── Metrics ──────────────────────────────────────────────────────────
        n_enc  = len([a for a in alerts if a["category"] == "illegal_encroachment"])
        n_fire = len([a for a in alerts if a["category"] == "natural_wildfire"])
        n_agri = len([a for a in alerts if a["category"] == "agricultural_burn"])
        n_anm  = len([a for a in alerts if a["category"] == "anomaly"])
        avg_conf = int(sum(a["confidence"] for a in alerts) / len(alerts)) if alerts else 0

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-val" style="color:#ff5252">{n_enc}</div>
                <div class="metric-label">Illegal encroachments</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color:#4fc3f7">{n_fire}</div>
                <div class="metric-label">Natural wildfires</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color:#ff9800">{n_agri}</div>
                <div class="metric-label">Agricultural burns</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color:#2dd4a0">{avg_conf}%</div>
                <div class="metric-label">Avg confidence</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if n_enc > 0:
            st.warning(f"🚨  {n_enc} illegal encroachment cluster(s) detected inside protected boundaries. Immediate verification recommended.")
        else:
            st.success("✅  No illegal encroachments detected in this scan.")

        # ── Plot markers ─────────────────────────────────────────────────────
        for alert in alerts:
            style   = CATEGORY_STYLE.get(alert["category"], CATEGORY_STYLE["anomaly"])
            color   = style["color"]
            radius  = 10 if alert["category"] == "illegal_encroachment" else 7
            opacity = 0.9 if alert["severity"] in ("high", "info") else 0.65

            popup_html = f"""
            <div style='font-family:sans-serif;font-size:13px;min-width:200px;'>
                <b style='color:{color}'>{style["label"].upper()}</b><br>
                <hr style='margin:6px 0;border-color:#333'>
                📍 {alert['lat']:.4f}°N, {alert['lon']:.4f}°E<br>
                ⚡ Radiance delta: <b>{alert['delta']} nW/cm²/sr</b><br>
                🔲 Cluster size: {alert['cluster_size']} pixels<br>
                🎯 Confidence: <b>{alert['confidence']}%</b><br>
                ⚠️ Severity: {alert['severity'].upper()}
            </div>
            """

            folium.CircleMarker(
                location=[alert["lat"], alert["lon"]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=opacity,
                weight=1.5,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{style['label']} · {alert['confidence']}% confidence",
            ).add_to(m)

        # ── Alert detail table ────────────────────────────────────────────────
        enc_alerts = [a for a in alerts if a["category"] == "illegal_encroachment"]
        if enc_alerts:
            with st.expander(f"📋  Illegal encroachment detail log ({len(enc_alerts)} clusters)"):
                st.markdown("""
                | # | Coordinates | Δ Radiance | Cluster Size | Confidence | Severity |
                |---|-------------|-----------|--------------|------------|----------|
                """ + "\n".join([
                    f"| {i+1} | {a['lat']:.4f}°N {a['lon']:.4f}°E "
                    f"| {a['delta']} nW | {a['cluster_size']} px "
                    f"| {a['confidence']}% | {a['severity'].upper()} |"
                    for i, a in enumerate(enc_alerts[:50])
                ]))

# ── Render map ─────────────────────────────────────────────────────────────────
st_folium(m, width="100%", height=540, returned_objects=[])

# ─── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center; font-size:0.75rem; color:#2d5a3d; padding: 8px 0;'>
    TerraVision AI · Built with NASA VIIRS · Protecting forests from space 🛰️
</div>
""", unsafe_allow_html=True)