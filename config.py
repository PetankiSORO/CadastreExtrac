# - url du cadastre minier
url = "https://portals.landfolio.com/CoteDIvoire/FR/"

# - Parametre de requettes html
headers = {"User-Agent": "Mozilla/5.0"}
timeout = 15
encoding = "utf-8"

# - Parametre d'extraction des couches
resultRecordCount = 1000
f = "json"
where = "1=1"
spatialRel = "esriSpatialRelIntersects"
geometryType = "esriGeometryPolygon"
outSR = 4326

# - Parametre de sauvegardes des couches
output = "outputs/"
log_output = f"{output}logs/"
