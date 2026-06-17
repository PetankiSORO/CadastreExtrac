"""
config.py — Configuration centrale (constantes uniquement, aucun effet de bord).
Valeurs sensibles injectées via variables d'environnement (GitHub Secrets).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Répertoires
# ──────────────────────────────────────────────────────────────────────────────
def _base_path() -> Path:
    """Répertoire racine, compatible exécutable PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.resolve()


BASE_DIR    : Path = _base_path()
DATA_DIR    : Path = BASE_DIR / "data"
LOG_DIR     : Path = DATA_DIR / "log"


# ──────────────────────────────────────────────────────────────────────────────
# Fichier credentials Google Drive
# ──────────────────────────────────────────────────────────────────────────────
def _get_gdrive_credentials_path() -> Path:
    """Retourne le chemin du fichier credentials Google Drive."""
    if env_path := os.getenv("GDRIVE_CREDENTIALS_FILE"):
        return Path(env_path)
    
    home_creds = Path.home() / ".config" / "gdrive_credentials.json"
    if home_creds.exists():
        return home_creds
    
    project_creds = BASE_DIR / "secrets" / "gdrive_credentials.json"
    return project_creds


GDRIVE_CREDENTIALS_FILE : Path = _get_gdrive_credentials_path()


# ──────────────────────────────────────────────────────────────────────────────
# Google Drive
# ──────────────────────────────────────────────────────────────────────────────
GDRIVE_FOLDER_ID  : str = os.getenv("GDRIVE_FOLDER_ID", "")
GDRIVE_KEEP_LAST_N: int = 30
GDRIVE_UPLOAD_FORMATS: list[str] = [
    ".xlsx",
    ".csv",
    ".geojson",
    ".json",
    ".zip",
]

# ──────────────────────────────────────────────────────────────────────────────
# HTTP — URLs sensibles en secrets
# ──────────────────────────────────────────────────────────────────────────────
def _get_landfolio_url() -> str:
    """
    Récupère l'URL du portail Landfolio depuis les secrets.
    
    En CI/CD (GitHub Actions) :
      - Injecté via LANDFOLIO_URL secret
    
    En local (développement) :
      - Depuis .env ou par défaut (voir exemple ci-dessous)
    """
    url = os.getenv("LANDFOLIO_URL")
    if not url:
        raise ValueError(
            "❌ LANDFOLIO_URL non définie. "
            "Définir la variable d'environnement ou le secret GitHub."
        )
    return url


def _get_proxy_base() -> str:
    """Récupère l'URL de base du proxy Landfolio depuis les secrets."""
    proxy = os.getenv("LANDFOLIO_PROXY_BASE")
    if not proxy:
        raise ValueError(
            "❌ LANDFOLIO_PROXY_BASE non définie. "
            "Définir la variable d'environnement ou le secret GitHub."
        )
    return proxy


def _get_proxy_referer() -> str:
    """Récupère l'URL referer du proxy Landfolio depuis les secrets."""
    referer = os.getenv("LANDFOLIO_PROXY_REFERER")
    if not referer:
        raise ValueError(
            "❌ LANDFOLIO_PROXY_REFERER non définie. "
            "Définir la variable d'environnement ou le secret GitHub."
        )
    return referer

# Charger au démarrage (levera une exception si manquant)
URL_CADASTRE    : str = "https://portals.landfolio.com/CoteDIvoire/FR/"
PROXY_BASE      : str = "https://portals.landfolio.com/CoteDIvoire/en/proxy.ashx?"
PROXY_REFERER   : str = "https://portals.landfolio.com/CoteDIvoire/en/"

# # Charger au démarrage (levera une exception si manquant)
# URL_CADASTRE    : str = _get_landfolio_url()
# PROXY_BASE      : str = _get_proxy_base()
# PROXY_REFERER   : str = _get_proxy_referer()

HTTP_HEADERS    : dict = {"User-Agent": "Mozilla/5.0"}
HTTP_TIMEOUT    : int = 30
HTTP_MAX_RETRY  : int = 5
HTTP_BACKOFF    : float = 3.0


# ──────────────────────────────────────────────────────────────────────────────
# ArcGIS
# ──────────────────────────────────────────────────────────────────────────────
ARCGIS_RECORD_COUNT : int = 1_000
ARCGIS_F            : str = "json"
ARCGIS_WHERE        : str = "1=1"
ARCGIS_SPATIAL_REL  : str = "esriSpatialRelIntersects"
ARCGIS_GEOM_TYPE    : str = "esriGeometryPolygon"
ARCGIS_OUT_SR       : int = 4326
CRS                 : str = f"EPSG:{ARCGIS_OUT_SR}"


# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
LOG_LEVEL       : str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT      : str = "[%(asctime)s] %(levelname)-8s | %(name)s — %(message)s"
LOG_DATEFORMAT  : str = "%Y-%m-%d %H:%M:%S"


# ──────────────────────────────────────────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────────────────────────────────────────
def ensure_directories() -> None:
    """Crée les répertoires nécessaires s'ils n'existent pas."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Groupes de couches — Cadastre Minier
# ──────────────────────────────────────────────────────────────────────────────

# Couches de licences/demandes à fusionner
LICENCE_GROUPS: list[str] = [
    "Demandes",
    "Licences",
]

# Couche administrative
ADMIN_GROUP: str = "Administration"

