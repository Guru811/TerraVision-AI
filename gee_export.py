import ee
from gee_gateway import connect_gee

# Call the hidden connection
connect_gee()

# Western Ghats boundary
forest = ee.Geometry.Rectangle([74.0, 8.0, 78.5, 15.5])

# 5-year baseline
baseline = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG") \
    .filterDate("2019-01-01", "2023-12-31") \
    .filterBounds(forest) \
    .select("avg_rad") \
    .median()

# Current data
current = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG") \
    .filterDate("2026-01-01", "2026-03-01") \
    .filterBounds(forest) \
    .select("avg_rad") \
    .mean()

# Export both to Google Drive
ee.batch.Export.image.toDrive(
    image=baseline,
    description="viirs_baseline",
    region=forest,
    scale=500,
    fileFormat="GeoTIFF"
).start()

ee.batch.Export.image.toDrive(
    image=current,
    description="viirs_current",
    region=forest,
    scale=500,
    fileFormat="GeoTIFF"
).start()

print("Export started! Check Google Drive in ~10 minutes.")