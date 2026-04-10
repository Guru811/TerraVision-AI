import ee
from gee_gateway import connect_gee

# Connect to Earth Engine using the project ID from the .env file
connect_gee()



FOREST_REGIONS = {
    "Western Ghats, India": ee.Geometry.Rectangle([74.0, 8.0, 78.5, 15.5]),
    "Aravalli Hills, India": ee.Geometry.Rectangle([72.5, 23.5, 77.5, 28.5]),
    "Amazon Basin, Brazil": ee.Geometry.Rectangle([-73.0, -10.0, -44.0, 5.0]),
    "Borneo Rainforest": ee.Geometry.Rectangle([108.0, -4.5, 119.0, 7.0]),
    "Congo Basin, Africa": ee.Geometry.Rectangle([15.0, -5.0, 30.0, 5.0]),
    "Sundarbans, Bangladesh": ee.Geometry.Rectangle([88.5, 21.5, 90.0, 22.5]),
    "Daintree Rainforest, Australia": ee.Geometry.Rectangle([145.2, -16.5, 145.7, -15.8]),
    "Black Forest, Germany": ee.Geometry.Rectangle([7.5, 47.5, 8.5, 48.8]),
    "Tongass National Forest, USA": ee.Geometry.Rectangle([-136.0, 54.5, -129.0, 60.0]),
    "Atlantic Forest, Brazil": ee.Geometry.Rectangle([-50.0, -25.0, -35.0, -10.0]),
    "Northeast India Forests": ee.Geometry.Rectangle([89.5, 21.5, 97.5, 29.0]),
}

# =============================================================================
# EXPORT FUNCTION
# Pulls baseline and current VIIRS data for a selected region and
# exports both as GeoTIFF files to Google Drive.
# =============================================================================

def export_region(region_name: str):
    """
    Export baseline (5-year median) and current VIIRS radiance rasters
    for the named region to Google Drive as GeoTIFF files.

    Files are named:
      viirs_baseline_{region_slug}.tif
      viirs_current_{region_slug}.tif
    """
    if region_name not in FOREST_REGIONS:
        raise ValueError(
            f"Region '{region_name}' not found. "
            f"Available: {list(FOREST_REGIONS.keys())}"
        )

    forest = FOREST_REGIONS[region_name]

    # Create a safe filename slug from the region name
    slug = region_name.lower().replace(" ", "_").replace(",", "")

    # 5-year median baseline (2019-2023)
    # Using median rather than mean makes the baseline robust to
    # occasional wildfire seasons or cloud contamination in any single year
    baseline = (
        ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
        .filterDate("2019-01-01", "2023-12-31")
        .filterBounds(forest)
        .select("avg_rad")
        .median()
    )

    # Current period (January to March 2026)
    current = (
        ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
        .filterDate("2026-03-01", "2026-04-01")
        .filterBounds(forest)
        .select("avg_rad")
        .mean()
    )

    # Export baseline raster to Google Drive
    ee.batch.Export.image.toDrive(
        image=baseline,
        description=f"viirs_baseline_{slug}",
        region=forest,
        scale=500,
        fileFormat="GeoTIFF",
        maxPixels=1e10,
    ).start()

    # Export current raster to Google Drive
    ee.batch.Export.image.toDrive(
        image=current,
        description=f"viirs_current_{slug}",
        region=forest,
        scale=500,
        fileFormat="GeoTIFF",
        maxPixels=1e10,
    ).start()

    print(f"Export started for: {region_name}")
    print(f"  Baseline file: viirs_baseline_{slug}.tif")
    print(f"  Current file : viirs_current_{slug}.tif")
    print("Check Google Drive in 10-15 minutes.")


if __name__ == "__main__":
    # Change this to export a different region
    # export_region("Western Ghats, India")
    # export_region("Aravalli Hills, India")
    export_region("Amazon Basin, Brazil")