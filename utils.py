# %% IMPORTATION DES BIBLIOTHEQUES
# ─────────────────────────────────────────────
from __future__ import annotations

# » Bibliothèque standard
from datetime import datetime
import time
import re
import json
import codecs
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from urllib.parse import urlsplit, urlunsplit

# » Bibliothèques externes
import requests
from bs4 import BeautifulSoup
import geopandas as gpd
from shapely.geometry import Point, Polygon
import pandas as pd

# » Fichiers de configuration
import config as c # paramètres globaux (url, headers, timeouts, chemins, etc.)

# » Date d'aujourd'hui
today_str = datetime.today().strftime("%d%m%Y")

# %% FONCTIONS
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Journalisation → FICHIER uniquement (aucune sortie terminal)
# ─────────────────────────────────────────────────────────────────────────────
LOG_DIR = (Path(__file__).resolve().parent / "outputs" / "logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"cadastre_{today_str}.log"

logger = logging.getLogger("cadastre")
logger.setLevel(logging.INFO)

# Nettoyer d'éventuels handlers existants
for h in list(logger.handlers):
    logger.removeHandler(h)

fh = TimedRotatingFileHandler(
    LOG_FILE, when="midnight", backupCount=30, encoding="utf-8", utc=False
)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(fh)

# Empêche la propagation vers le root (sinon risque d'affichage console)
logger.propagate = False

# Réduire le bruit de certaines libs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("fiona").setLevel(logging.WARNING)
logging.getLogger("shapely").setLevel(logging.ERROR)
logging.captureWarnings(True)

# ─────────────────────────────────────────────────────────────────────────────
# Masquage des informations sensibles dans TOUTES les lignes de log
# ─────────────────────────────────────────────────────────────────────────────
_TOKEN_RE = re.compile(r"(token=)([^&]+)", re.IGNORECASE)

def safe_url(s: str) -> str:
    """Masque de l'URL par un placeholder dans les logs"""
    try:
        parts = urlsplit(s)
        if parts.scheme and parts.netloc:
            masked = urlunsplit((parts.scheme,
                                 "BaseUrl**", "RestUrl**",
                                 "Query**", parts.fragment))
            return masked
    except Exception:
        pass
    return s

class RedactFilter(logging.Filter):
    """Filtre global: applique safe_url au message et à ses arguments."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = safe_url(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: safe_url(v) if isinstance(v, str) else v
                               for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(safe_url(a) if isinstance(a, str) else a
                                    for a in record.args)
            elif isinstance(record.args, str):
                record.args = safe_url(record.args)
        return True

logger.addFilter(RedactFilter())

# ──────────────────────────────────────────────────────────────────────────────
# I/O utilitaires
# ──────────────────────────────────────────────────────────────────────────────
def _mkdir_parents(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Requêtes HTTP (GET) avec retries
# ──────────────────────────────────────────────────────────────────────────────
def extract_html(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int | float = 15,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> requests.Response:
    headers = headers or c.headers
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                sleep_s = backoff * attempt
                logger.warning("Tentative %s/%s échouée. Retry dans %.1fs | URL=%s | Err=%s",
                               attempt, max_retries, sleep_s, url, str(e))
                time.sleep(sleep_s)
            else:
                logger.error("Échec définitif de la requête | URL=%s | Err=%s", url, str(e))
                raise
    assert last_exc
    raise last_exc

# ──────────────────────────────────────────────────────────────────────────────
# Extraction du JSON d'initialisation
# ──────────────────────────────────────────────────────────────────────────────
def extract_json(html: str, json_name: str = "MainPage.Init") -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", {"type": "text/javascript"})
    motif = r"\s*\(\s*['\"]((?:\\.|[^'\"])+?)['\"]\s*,"
    pattern = re.compile(re.escape(json_name) + motif, re.DOTALL)

    for script in scripts:
        content = script.get_text() or ""
        m = pattern.search(content)
        if m:
            raw_json = m.group(1)
            decoded = codecs.decode(raw_json, "unicode_escape")
            obj = json.loads(decoded)
            logger.info("✅ JSON '%s' trouvé et décodé.", json_name)
            print(f"✅ JSON {json_name} trouvé et décodé.")
            return obj

    raise RuntimeError(f"{json_name} introuvable dans la page.")

# ──────────────────────────────────────────────────────────────────────────────
# Métadonnées (RestUrl, token, LayerIDs)
# ──────────────────────────────────────────────────────────────────────────────
def extract_data_info (html_json: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data_info: Dict[str, Dict[str, Any]] = {}
    
    # Recensement des services dynamiques
    for ms in html_json.get("MapServices"):
        if ms.get("MapServiceType") != "Dynamic" :
            continue
        data_info [ms.get("DisplayName")]  = {
            "RestUrl": ms.get("RestUrl"),
            "ArcGISToken": ms.get("ArcGISToken"),
            "LayerName": [],
            "LayerID": []}

        # Affectation des couches par service
        for grp in html_json.get("GroupByTemplates"):
            if grp.get("MapServiceName") == ms.get("Name"):
                lyr_names = [gr["LayerName"][0] for gr in grp["LayerTemplates"]]
                lyr_ids = [int(gr["LayerID"]) for gr in grp["LayerTemplates"]]
                data_info[ms["DisplayName"]]["LayerName"] = lyr_names
                data_info[ms["DisplayName"]]["LayerID"] = lyr_ids
                
    # Journalisation (sans fuite d'infos)
    for disp, meta in data_info.items():
        tok_present = "oui" if meta.get("ArcGISToken") else "non"
        logger.info("Service '%s' → %s couches | token présent: %s",
                    disp, len(meta.get("LayerID", [])), tok_present)
    return data_info

# ──────────────────────────────────────────────────────────────────────────────
# Téléchargement des entités (pagination)
# ──────────────────────────────────────────────────────────────────────────────
def _build_query_url(rest_url: str, layer_id: int, token: Optional[str], offset: int) -> str:
    base = f"{rest_url}/{layer_id}/query"
    params = [
        f"f={c.f}",
        f"where={c.where}",
        "returnGeometry=true",
        f"spatialRel={c.spatialRel}",
        f"geometryType={c.geometryType}",
        "outFields=*",
        f"outSR={c.outSR}",
        f"resultOffset={offset}",
        f"resultRecordCount={c.resultRecordCount}",
    ]
    if token:
        params.insert(0, f"token={token}")
    return base + "?" + "&".join(params)

def extract_data_json(data_info: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    data_json: Dict[str, Dict[str, Any]] = {}

    for grp_name, grp in data_info.items():
        rest_url: Optional[str] = grp.get("RestUrl")
        token: Optional[str] = grp.get("ArcGISToken")
        layer_ids: List[int] = grp.get("LayerID", [])
        layer_names: List[str] = grp.get("LayerName", [])

        if not rest_url or not layer_ids:
            logger.warning("⚠️ Service '%s' ignoré (RestUrl/LayerID manquants).", grp_name)
            print(f"⚠️ Service {grp_name} ignoré (RestUrl/LayerID manquants).")
            continue

        data_json[grp_name] = {}

        for lyr_id, lyr_name in zip(layer_ids, layer_names):
            features: List[Dict[str, Any]] = []
            offset = 0
            geom_type: Optional[str] = None

            while True:
                url = _build_query_url(rest_url, lyr_id, token, offset)
                try:
                    r = extract_html(url, headers=c.headers, timeout=c.timeout)
                    d = r.json()
                except Exception as e:
                    logger.error("❌ Requête échouée: %s | Err=%s", url, str(e))
                    print(f"❌ Requête échouée: {url} | Err={str(e)}")
                    break

                batch = d.get("features", [])
                geom_type = d.get("geometryType")
                if not batch:
                    break

                features.extend(batch)
                offset += c.resultRecordCount
                logger.info("→ %s:%s +%s (total %s) via %s",
                            grp_name, lyr_name, len(batch), len(features), url)

            if not features:
                logger.warning("⚠️ Aucune entité pour %s:%s", grp_name, lyr_name)
                print(f"⚠️ Aucune entité pour {grp_name}:{lyr_name}")
                continue

            logger.info("✅ %s entités extraites pour %s:%s",
                        len(features), grp_name, lyr_name)
            print(f"✅ {len(features)} entités extraites pour {grp_name}:{lyr_name}")
            data_json[grp_name][lyr_name] = {
                "features": features,
                "geom_type": geom_type
            }

    return data_json

# ──────────────────────────────────────────────────────────────────────────────
# Conversion → GeoDataFrames
# ──────────────────────────────────────────────────────────────────────────────
def extract_geom(geometry: Dict[str, Any], geom_type: str) -> Optional[Point | Polygon]:
    if geom_type == "esriGeometryPoint":
        try:
            return Point(list(geometry.values()))
        except Exception:
            return None

    if geom_type == "esriGeometryPolygon":
        try:
            rings = geometry.get("rings", [])
            if not rings:
                return None
            ring = rings[0] if len(rings) == 1 else rings[1]
            return Polygon(ring)
        except Exception:
            return None

    logger.warning("❌ Géométrie non gérée: %s.", geom_type)
    print(f"❌ Géométrie non gérée: {geom_type}.")
    return None

def convert_dates(attrs: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in list(attrs.items()):
        if isinstance(v, int) and v > 1e12:  # timestamps ms
            attrs[k] = datetime.fromtimestamp(v / 1000).strftime("%d-%m-%Y")
    return attrs

def extract_data_feature(
    data_json: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, gpd.GeoDataFrame]]:
    data_feature: Dict[str, Dict[str, gpd.GeoDataFrame]] = {}

    for grp_name, grp in data_json.items():
        data_feature[grp_name] = {}
        for lyr_name, lyr in grp.items():
            feats_attrs: List[Dict[str, Any]] = []
            features = lyr.get("features", [])
            geom_type = lyr.get("geom_type", "esriGeometryPolygon")

            for feat in features:
                attr = convert_dates(dict(feat.get("attributes", {})))
                attr["layer"] = lyr_name
                geom = extract_geom(feat.get("geometry", {}), geom_type)
                attr["geometry"] = geom
                feats_attrs.append(attr)

            gdf = gpd.GeoDataFrame(feats_attrs, crs=f"EPSG:{c.outSR}")
            gdf = gdf[gdf.geometry.notnull()].copy()
            data_feature[grp_name][lyr_name] = gdf

    return data_feature

# ──────────────────────────────────────────────────────────────────────────────
# Fusion & sauvegardes
# ──────────────────────────────────────────────────────────────────────────────
def fusion_feature(
    *args: Dict[str, gpd.GeoDataFrame] | gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    gdfs: List[gpd.GeoDataFrame] = []
    for feat in args:
        if isinstance(feat, dict):
            gdfs.extend(list(feat.values()))
        elif isinstance(feat, gpd.GeoDataFrame):
            gdfs.append(feat)

    gdfs = [df for df in gdfs if hasattr(df, "size") and df.size > 0 and df.notna().any().any()]
    if not gdfs:
        return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{c.outSR}")

    cols_seen = set()
    valid_cols: List[str] = []
    for df in gdfs:
        for col in df.columns:
            if col not in cols_seen and df[col].notna().any():
                if "guid" not in col.lower():
                    valid_cols.append(col)
                cols_seen.add(col)

    aligned = [df.reindex(columns=valid_cols) for df in gdfs]
    return pd.concat(aligned, ignore_index=True)  # type: ignore

def _prepare_output_paths(name: str, file_format: str) -> Tuple[str, str, str]:
    driver = "GPKG" if file_format == ".gpkg" else "ESRI Shapefile"
    file = f"{c.output}{name}{file_format}"
    _mkdir_parents(Path(file).parent)
    return driver, file

def save_file_admin(
    grp: Dict[str, gpd.GeoDataFrame],
    name: str,
    file_format: str = ".gpkg",
    encoding: str = "utf-8",
) -> None:
    driver, file = _prepare_output_paths(name, file_format)
    for lyr_name, gdf in grp.items():
        gdf.to_file(file, layer=lyr_name, driver=driver, encoding=encoding, mode="w")
    logger.info("✅ %s%s sauvegardée avec succès.", name, file_format)
    print(f"✅ {name}{file_format} sauvegardée avec succès")

def save_file_licence(
    licence: gpd.GeoDataFrame,
    name: str,
    file_format: str = ".gpkg",
    encoding: str = "utf-8",
) -> None:
    driver, file = _prepare_output_paths(name, file_format)
    licence.to_file(file, driver=driver, encoding=encoding, mode="w")
    logger.info("✅ %s%s sauvegardée avec succès.", name, file_format)
    print(f"✅ {name}{file_format} sauvegardée avec succès")

def fin() -> None :
    logger.info("✅"*20)
    logger.info("\n"*4)

# ──────────────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────────────
def execute_all(url: str) -> None:
    html = extract_html(url, headers=c.headers, timeout=c.timeout).text
    html_json = extract_json(html)
    data_info = extract_data_info(html_json)
    data_json = extract_data_json(data_info)
    data_feature = extract_data_feature(data_json)

    # Licences = fusion des groupes 'Demandes' et 'Licences' (selon dispo)
    if "Demandes" in data_feature and "Licences" in data_feature:
        licence = fusion_feature(data_feature["Demandes"], data_feature["Licences"])
    elif "Licences" in data_feature:
        licence = fusion_feature(data_feature["Licences"])
    elif "Demandes" in data_feature:
        licence = fusion_feature(data_feature["Demandes"])
    else:
        licence = gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{c.outSR}")

    admin = data_feature.get("Administration", {})

    if isinstance(licence, pd.DataFrame) and not licence.empty:
        save_file_licence(licence, "Cadastre_Minier_Ci")
    else:
        logger.warning("⚠️ Aucune donnée de licences/demandes à sauvegarder.")

    if isinstance(admin, dict) and admin:
        save_file_admin(admin, "Admin_Ci")
    else:
        logger.warning("⚠️ Aucune couche 'Administration' à sauvegarder.")

# %% Fonction Executer tout
if __name__ == "__main__":
    execute_all(c.url)
