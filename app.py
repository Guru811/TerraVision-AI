import streamlit as st
import folium
from streamlit_folium import st_folium
from detect import detect_encroachments, DetectionParams
import os
import time
import tempfile

# Page configuration for the TerraVision AI dashboard
st.set_page_config(
    page_title="TerraVision AI — Forest Guardian",
    layout="wide",
    page_icon="🌿",
    initial_sidebar_state="expanded",
)

# =============================================================================
# TIF FILE STRATEGY
# Locally: reads .tif files downloaded from Google Drive after running gee_export.py
# Streamlit Cloud: .tif files are too large for GitHub, so we pull rasters
# directly from GEE at scan time and write them to a temporary folder.
# =============================================================================

def get_tif_paths(region_name: str):
    """
    Return (baseline_path, current_path) for the selected region.
    Checks for local files first. If not found, downloads from GEE live.
    Returns (None, None) if both methods fail.
    """
    slug = region_name.lower().replace(" ", "_").replace(",", "")
    local_baseline = f"viirs_baseline_{slug}.tif"
    local_current  = f"viirs_current_{slug}.tif"

    # Check for original Western Ghats prototype files (no slug suffix)
    if region_name == "Western Ghats, India":
        if os.path.exists("viirs_baseline.tif") and os.path.exists("viirs_current.tif"):
            return "viirs_baseline.tif", "viirs_current.tif"

    # Check for region-specific local files
    if os.path.exists(local_baseline) and os.path.exists(local_current):
        return local_baseline, local_current

    # No local files found — pull directly from GEE (used on Streamlit Cloud)
    try:
        import ee
        import rasterio
        import io
        import urllib.request
        from gee_gateway import connect_gee
        from gee_export import FOREST_REGIONS

        connect_gee()

        if region_name not in FOREST_REGIONS:
            return None, None

        forest = FOREST_REGIONS[region_name]

        baseline_img = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterDate("2019-01-01", "2023-12-31")
            .filterBounds(forest)
            .select("avg_rad")
            .median()
        )
        current_img = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterDate("2026-01-01", "2026-03-01")
            .filterBounds(forest)
            .select("avg_rad")
            .mean()
        )

        def gee_to_tif(image, out_path):
            """Download a GEE image and save it as a local GeoTIFF."""
            url = image.getDownloadURL({
                "bands": ["avg_rad"],
                "region": forest,
                "scale": 500,
                "format": "GEO_TIFF",
            })
            with urllib.request.urlopen(url) as resp:
                data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)

        tmp = tempfile.gettempdir()
        baseline_path = os.path.join(tmp, local_baseline)
        current_path  = os.path.join(tmp, local_current)

        with st.spinner("Downloading satellite data from Earth Engine — this takes 1-2 minutes..."):
            gee_to_tif(baseline_img, baseline_path)
            gee_to_tif(current_img,  current_path)

        return baseline_path, current_path

    except Exception as e:
        st.error(f"Could not load satellite data: {e}")
        return None, None


# Store the current theme in session state
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

# Theme toggle button in the top-right corner
col_gap, col_toggle = st.columns([10, 1])
with col_toggle:
    toggle_label = "☀️" if st.session_state.dark_mode else "🌙"
    if st.button(toggle_label, help="Toggle light/dark mode", key="theme_toggle"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

is_dark = st.session_state.dark_mode

if is_dark:
    theme_css = """
    :root {
        --bg-deep:       #0a1a0f;
        --bg-dark:       #0f2418;
        --bg-mid:        #1a3a25;
        --bg-light:      #2d5a3d;
        --teal-primary:  #2dd4a0;
        --teal-soft:     #1db888;
        --teal-dim:      #0f6e52;
        --text-main:     #c8e6d4;
        --text-muted:    #8fbc8f;
        --text-subtle:   rgba(45,212,160,0.6);
        --border-color:  rgba(45,212,160,0.15);
        --border-hover:  rgba(45,212,160,0.4);
        --legend-bg:     rgba(15,36,24,0.8);
        --scrollbar-track: #0f2418;
        --scrollbar-thumb: #0f6e52;
        --sidebar-info-color: #4a7a5a;
        --footer-color:  #2d5a3d;
        --header-bg: linear-gradient(135deg, #1a3a25 0%, #0f2418 60%, rgba(45,212,160,0.08) 100%);
        --btn-bg: linear-gradient(135deg, #0f6e52 0%, #2d5a3d 100%);
        --btn-bg-hover: linear-gradient(135deg, #1a7a5a 0%, #0f6e52 100%);
        --expander-bg:   #1a3a25;
        --app-bg:        #0a1a0f;
        --input-bg:      #0f2418;
        --input-bg-hover:#1a3a25;
        --input-text:    #c8e6d4;
        --input-border:  rgba(45,212,160,0.25);
        --input-border-focus: rgba(45,212,160,0.6);
        --dropdown-bg:   #0f2418;
        --dropdown-hover:#1a3a25;
    }
    """
else:
    theme_css = """
    :root {
        --bg-deep:       #f0f7f2;
        --bg-dark:       #e0efe6;
        --bg-mid:        #d0e8d8;
        --bg-light:      #b8d9c4;
        --teal-primary:  #0d7a56;
        --teal-soft:     #0f9168;
        --teal-dim:      #1aab7a;
        --text-main:     #0f2418;
        --text-muted:    #2d5a3d;
        --text-subtle:   rgba(13,122,86,0.7);
        --border-color:  rgba(13,122,86,0.2);
        --border-hover:  rgba(13,122,86,0.5);
        --legend-bg:     rgba(208,232,216,0.9);
        --scrollbar-track: #e0efe6;
        --scrollbar-thumb: #1aab7a;
        --sidebar-info-color: #2d5a3d;
        --footer-color:  #2d5a3d;
        --header-bg: linear-gradient(135deg, #d0e8d8 0%, #e0efe6 60%, rgba(13,122,86,0.08) 100%);
        --btn-bg: linear-gradient(135deg, #1aab7a 0%, #0d7a56 100%);
        --btn-bg-hover: linear-gradient(135deg, #0f9168 0%, #1aab7a 100%);
        --expander-bg:   #d0e8d8;
        --app-bg:        #f0f7f2;
        --input-bg:      #ffffff;
        --input-bg-hover:#f0f7f2;
        --input-text:    #0f2418;
        --input-border:  rgba(13,122,86,0.3);
        --input-border-focus: rgba(13,122,86,0.7);
        --dropdown-bg:   #ffffff;
        --dropdown-hover:#e0efe6;
    }
    """

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap');
{theme_css}
html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; background-color: var(--bg-deep) !important; color: var(--text-main) !important; }}
.stApp {{ background: radial-gradient(ellipse at 20% 50%, rgba(45,212,160,0.04) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(29,184,136,0.05) 0%, transparent 50%), var(--app-bg) !important; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, var(--bg-dark) 0%, var(--bg-deep) 100%) !important; border-right: 1px solid var(--border-color) !important; }}
[data-testid="stSidebar"] * {{ color: var(--text-main) !important; }}
.terra-header {{ background: var(--header-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 28px 36px; margin-bottom: 24px; position: relative; overflow: hidden; }}
.terra-header::before {{ content: ''; position: absolute; top: -40px; right: -40px; width: 200px; height: 200px; background: radial-gradient(circle, rgba(45,212,160,0.08) 0%, transparent 70%); border-radius: 50%; animation: breathe 4s ease-in-out infinite; }}
.terra-header::after {{ content: ''; position: absolute; bottom: -60px; left: 30%; width: 300px; height: 120px; background: radial-gradient(ellipse, rgba(29,184,136,0.05) 0%, transparent 70%); animation: breathe 6s ease-in-out infinite reverse; }}
@keyframes breathe {{ 0%, 100% {{ transform: scale(1); opacity: 0.6; }} 50% {{ transform: scale(1.15); opacity: 1; }} }}
.terra-title {{ font-family: 'Playfair Display', serif; font-size: 2.2rem; font-weight: 600; color: var(--teal-primary) !important; margin: 0 0 4px 0; letter-spacing: -0.5px; }}
.terra-subtitle {{ font-size: 0.95rem; color: var(--text-muted) !important; font-weight: 300; letter-spacing: 0.5px; }}
.terra-tagline {{ font-size: 0.8rem; color: var(--text-subtle) !important; margin-top: 10px; font-style: italic; }}
.live-badge {{ display: inline-flex; align-items: center; gap: 7px; background: rgba(45,212,160,0.1); border: 1px solid var(--border-color); border-radius: 20px; padding: 4px 12px; font-size: 0.75rem; color: var(--teal-primary) !important; margin-top: 12px; }}
.pulse-dot {{ width: 7px; height: 7px; background: var(--teal-primary); border-radius: 50%; animation: pulse 2s ease-in-out infinite; }}
@keyframes pulse {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(45,212,160,0.7); }} 50% {{ box-shadow: 0 0 0 6px rgba(45,212,160,0); }} }}
.metric-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }}
.metric-card {{ background: var(--bg-mid); border: 1px solid var(--border-color); border-radius: 12px; padding: 16px 18px; transition: border-color 0.3s, transform 0.2s; }}
.metric-card:hover {{ border-color: var(--border-hover); transform: translateY(-2px); }}
.metric-val {{ font-family: 'Playfair Display', serif; font-size: 1.8rem; font-weight: 600; line-height: 1; margin-bottom: 4px; }}
.metric-label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted) !important; }}
.legend-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 16px 0; }}
.legend-item {{ display: flex; align-items: center; gap: 10px; background: var(--legend-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 8px 12px; font-size: 0.78rem; color: var(--text-main) !important; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
.stButton > button {{ background: var(--btn-bg) !important; color: var(--teal-primary) !important; border: 1px solid var(--border-hover) !important; border-radius: 10px !important; font-family: 'DM Sans', sans-serif !important; font-size: 0.9rem !important; font-weight: 500 !important; letter-spacing: 0.5px !important; padding: 0.6rem 1.2rem !important; transition: all 0.25s ease !important; width: 100% !important; }}
.stButton > button:hover {{ background: var(--btn-bg-hover) !important; border-color: var(--teal-primary) !important; box-shadow: 0 0 20px rgba(45,212,160,0.2) !important; transform: translateY(-1px) !important; }}
.stSelectbox label, .stSlider label, [data-testid="stSidebar"] label {{ color: var(--text-muted) !important; font-size: 0.8rem !important; text-transform: uppercase !important; letter-spacing: 0.6px !important; }}
[data-testid="stSlider"] [role="slider"] {{ background: var(--teal-primary) !important; }}
[data-testid="stSelectbox"] > div > div {{ background-color: var(--input-bg) !important; border: 1px solid var(--input-border) !important; border-radius: 8px !important; color: var(--input-text) !important; }}
[data-testid="stSelectbox"] span, [data-testid="stSelectbox"] div[data-baseweb="select"] span {{ color: var(--input-text) !important; }}
[data-testid="stSelectbox"] svg {{ fill: var(--teal-primary) !important; }}
[data-baseweb="popover"] ul, [data-baseweb="menu"] {{ background-color: var(--dropdown-bg) !important; border: 1px solid var(--input-border) !important; border-radius: 8px !important; box-shadow: 0 8px 24px rgba(0,0,0,0.25) !important; }}
[data-baseweb="menu"] li, [role="option"] {{ background-color: var(--dropdown-bg) !important; color: var(--input-text) !important; }}
[data-baseweb="menu"] li:hover, [role="option"]:hover, [aria-selected="true"] {{ background-color: var(--dropdown-hover) !important; color: var(--teal-primary) !important; }}
.stAlert {{ border-radius: 10px !important; border-left-width: 3px !important; }}
.streamlit-expanderHeader {{ background: var(--expander-bg) !important; border-radius: 8px !important; color: var(--teal-primary) !important; }}
::-webkit-scrollbar {{ width: 5px; }} ::-webkit-scrollbar-track {{ background: var(--scrollbar-track); }} ::-webkit-scrollbar-thumb {{ background: var(--scrollbar-thumb); border-radius: 4px; }}
hr {{ border-color: var(--border-color) !important; }}
.section-title {{ font-family: 'Playfair Display', serif; font-size: 1.1rem; color: var(--teal-primary) !important; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; margin: 18px 0 12px 0; }}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label {{ color: var(--text-main) !important; }}
p, span, div, li {{ color: var(--text-main); }}
table {{ color: var(--text-main) !important; }} thead tr {{ background: var(--bg-mid) !important; }} tbody tr:nth-child(even) {{ background: var(--bg-dark) !important; }}
</style>
""", unsafe_allow_html=True)

# Colour and label for each alert category
CATEGORY_STYLE = {
    "illegal_encroachment": {"color": "#ff5252", "label": "Illegal encroachment"},
    "natural_wildfire":     {"color": "#4fc3f7", "label": "Natural wildfire"},
    "agricultural_burn":    {"color": "#ff9800", "label": "Agricultural burn"},
    "anomaly":              {"color": "#b0bec5", "label": "Unclassified anomaly"},
    "unclassified":         {"color": "#78909c", "label": "Unclassified"},
}

# Map centre coordinates for all supported regions
REGION_COORDS = {
    "Western Ghats, India":           [12.0,   76.5],
    "Aravalli Hills, India":          [26.0,   74.5],
    "Northeast India Forests":        [25.0,   93.0],
    "Sundarbans, Bangladesh":         [21.9,   89.2],
    "Amazon Basin, Brazil":           [-3.5,  -60.0],
    "Atlantic Forest, Brazil":        [-18.0, -43.0],
    "Tongass National Forest, USA":   [57.0, -133.0],
    "Congo Basin, Africa":            [-1.0,   24.0],
    "Borneo Rainforest":              [1.5,   114.0],
    "Daintree Rainforest, Australia": [-16.1, 145.4],
    "Black Forest, Germany":          [48.2,    8.1],
}

# Sidebar
with st.sidebar:
    st.markdown('<div class="section-title">Forest Region</div>', unsafe_allow_html=True)

    # All regions in a single flat list for the selectbox
    region = st.selectbox("Select region", list(REGION_COORDS.keys()),
                          label_visibility="collapsed")

    st.markdown('<div class="section-title">Detection Settings</div>', unsafe_allow_html=True)

    # Minimum radiance delta to flag a pixel as suspicious
    threshold = st.slider(
        "Alert threshold (nW/cm²/sr)",
        min_value=1.0, max_value=15.0, value=5.0, step=0.5,
        help="Higher = fewer but more certain alerts. Recommended: 5–8 to reduce noise."
    )

    # Minimum pixels in a cluster — filters out single-pixel sensor noise
    min_cluster = st.slider(
        "Min cluster size (pixels)",
        min_value=1, max_value=20, value=3,
        help="Filter out lone pixels. Camps typically appear as 2–8 pixel clusters."
    )

    st.markdown('<div class="section-title">Filter by Type</div>', unsafe_allow_html=True)
    show_encroachment = st.checkbox("Illegal encroachment", value=True)
    show_wildfire     = st.checkbox("Natural wildfires",    value=True)
    show_agri         = st.checkbox("Agricultural burns",   value=True)
    show_anomaly      = st.checkbox("Unclassified anomaly", value=False)

    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.72rem; color: var(--sidebar-info-color); line-height: 1.7;'>
    📡 Data source: NASA VIIRS DNB<br>
    📅 Baseline: 5-yr median 2019–2023<br>
    🛰️ Resolution: 500m per pixel<br>
    ⚠️ Note: This tool is a prototype for research and awareness. Always verify alerts with on-the-ground checks before taking action.
    </div>
    """, unsafe_allow_html=True)

# Header
st.markdown("""
<div class="terra-header">
    <div class="terra-title">🌿 TerraVision AI</div>
    <div class="terra-subtitle">Satellite Forest Guardian · Illegal Encroachment Detection</div>
    <div class="terra-tagline">"Every tree that falls in silence, we hear from space."</div>
    <div class="live-badge"><div class="pulse-dot"></div>VIIRS satellite feed · Live</div>
</div>
""", unsafe_allow_html=True)

# Legend
st.markdown("""
<div class="legend-grid">
    <div class="legend-item"><div class="legend-dot" style="background:#ff5252"></div><span>Illegal encroachment — small persistent cluster, moderate radiance</span></div>
    <div class="legend-item"><div class="legend-dot" style="background:#4fc3f7"></div><span>Natural wildfire — large cluster, very high radiance spike</span></div>
    <div class="legend-item"><div class="legend-dot" style="background:#ff9800"></div><span>Agricultural burn — large seasonal cluster, moderate radiance</span></div>
    <div class="legend-item"><div class="legend-dot" style="background:#b0bec5"></div><span>Unclassified anomaly — does not match known patterns</span></div>
</div>
""", unsafe_allow_html=True)

# Scan button
col_btn, col_space = st.columns([1, 3])
with col_btn:
    scan = st.button("🔍  Run Satellite Scan", use_container_width=True)

# Map setup
center = REGION_COORDS.get(region, [12.0, 76.5])
map_tiles = "CartoDB dark_matter" if is_dark else "CartoDB positron"
m = folium.Map(location=center, zoom_start=6, tiles=map_tiles, prefer_canvas=True)

folium.Rectangle(
    bounds=[[center[0]-3, center[1]-3], [center[0]+3, center[1]+3]],
    color="#2dd4a0", weight=1.5, fill=True,
    fill_color="#2dd4a0", fill_opacity=0.04,
    tooltip="Protected forest boundary",
).add_to(m)

# Scan and alert rendering
if scan:
    baseline_path, current_path = get_tif_paths(region)

    if baseline_path is None or current_path is None:
        st.error(
            "Satellite data not available for this region. "
            "Run gee_export.py locally, download the TIF files from Google Drive, "
            "and place them in the project folder."
        )
    else:
        params = DetectionParams(delta_min_flag=threshold)

        with st.spinner("🛰️  Analysing VIIRS satellite data — comparing against 5-year baseline..."):
            time.sleep(0.5)
            all_alerts = detect_encroachments(
                baseline_path, current_path, params=params, verbose=True
            )

        all_alerts = [a for a in all_alerts if a["cluster_size"] >= min_cluster]

        active_cats = set()
        if show_encroachment: active_cats.add("illegal_encroachment")
        if show_wildfire:     active_cats.add("natural_wildfire")
        if show_agri:         active_cats.add("agricultural_burn")
        if show_anomaly:      active_cats.add("anomaly")
        alerts = [a for a in all_alerts if a["category"] in active_cats]

        n_enc  = len([a for a in alerts if a["category"] == "illegal_encroachment"])
        n_fire = len([a for a in alerts if a["category"] == "natural_wildfire"])
        n_agri = len([a for a in alerts if a["category"] == "agricultural_burn"])
        avg_conf = int(sum(a["confidence"] for a in alerts) / len(alerts)) if alerts else 0

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card"><div class="metric-val" style="color:#ff5252">{n_enc}</div><div class="metric-label">Illegal encroachments</div></div>
            <div class="metric-card"><div class="metric-val" style="color:#4fc3f7">{n_fire}</div><div class="metric-label">Natural wildfires</div></div>
            <div class="metric-card"><div class="metric-val" style="color:#ff9800">{n_agri}</div><div class="metric-label">Agricultural burns</div></div>
            <div class="metric-card"><div class="metric-val" style="color:#2dd4a0">{avg_conf}%</div><div class="metric-label">Avg confidence</div></div>
        </div>
        """, unsafe_allow_html=True)

        if n_enc > 0:
            st.warning(f"🚨  {n_enc} illegal encroachment cluster(s) detected. Immediate verification recommended.")
        else:
            st.success("✅  No illegal encroachments detected in this scan.")

        for alert in alerts:
            style   = CATEGORY_STYLE.get(alert["category"], CATEGORY_STYLE["anomaly"])
            color   = style["color"]
            radius  = 10 if alert["category"] == "illegal_encroachment" else 7
            opacity = 0.9 if alert["severity"] in ("high", "critical") else 0.65

            popup_html = f"""
            <div style='font-family:sans-serif;font-size:13px;min-width:210px;'>
                <b style='color:{color}'>{style["label"].upper()}</b><br>
                <hr style='margin:6px 0;border-color:#333'>
                📍 {alert['lat']:.4f}°N, {alert['lon']:.4f}°E<br>
                ⚡ Radiance mean: <b>{alert['delta_mean']} nW/cm²/sr</b><br>
                ⚡ Radiance peak: <b>{alert['delta_max']} nW/cm²/sr</b><br>
                🔲 Cluster size: {alert['cluster_size']} pixels<br>
                🎯 Confidence: <b>{alert['confidence']}%</b><br>
                ⚠️ Severity: {alert['severity'].upper()}
            </div>
            """
            folium.CircleMarker(
                location=[alert["lat"], alert["lon"]],
                radius=radius, color=color, fill=True,
                fill_color=color, fill_opacity=opacity, weight=1.5,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{style['label']} · {alert['confidence']}% confidence",
            ).add_to(m)

        enc_alerts = [a for a in alerts if a["category"] == "illegal_encroachment"]
        if enc_alerts:
            with st.expander(f"📋  Illegal encroachment detail log ({len(enc_alerts)} clusters)"):
                rows = "\n".join([
                    f"| {i+1} | {a['lat']:.4f}°N {a['lon']:.4f}°E "
                    f"| {a['delta_mean']} nW | {a['delta_max']} nW "
                    f"| {a['cluster_size']} px | {a['confidence']}% | {a['severity'].upper()} |"
                    for i, a in enumerate(enc_alerts[:50])
                ])
                st.markdown(
                    "| # | Coordinates | Δ Mean | Δ Peak | Cluster | Conf | Severity |\n"
                    "|---|-------------|--------|--------|---------|------|----------|\n" + rows
                )

st_folium(m, width="100%", height=540, returned_objects=[])

st.markdown("---")
st.markdown("""
<div style='text-align:center; font-size:0.75rem; color:var(--footer-color); padding: 8px 0;'>
    TerraVision AI · Built with NASA VIIRS · Protecting forests from space 🛰️
</div>
""", unsafe_allow_html=True)