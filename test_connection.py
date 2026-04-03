import ee

ee.Authenticate()
ee.Initialize(project="vibrant-castle-473713-k1")

image = ee.Image("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG/20240101")
print("Connected! Bands:", image.bandNames().getInfo())