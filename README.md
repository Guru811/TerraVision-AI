# 🌿 TerraVision AI — Forest Encroachment Detection

Satellite-powered illegal forest encroachment detection using 
NASA VIIRS night-light data and machine learning.

## What it does
Monitors protected forests by comparing current satellite 
night-light radiance against a 5-year historical baseline. 
Flags suspicious light clusters and classifies them as 
illegal encroachment, natural wildfire, agricultural burn, 
or anomaly using a weighted scoring classifier.

## Tech Stack
- Python 3.12
- NASA VIIRS DNB via Google Earth Engine API
- Rasterio · NumPy · Scikit-learn
- Streamlit · Folium

## How to run

### 1. Install dependencies
pip install -r requirements.txt

### 2. Authenticate Google Earth Engine
python test_connection.py

### 3. Export satellite data
python gee_export.py

### 4. Launch dashboard
streamlit run app.py

## Project Structure
- app.py — Streamlit dashboard
- detect.py — Change detection and ML classification
- gee_export.py — Satellite data pipeline
- test_connection.py — GEE authentication test

## Data Sources
- NASA VIIRS DNB (NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG)
- World Database of Protected Areas (WDPA)

## Team
EcoSentinel — YESIST12 Innovation Challenge 2026
