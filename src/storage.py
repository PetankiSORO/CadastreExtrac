"""
storage.py — Sauvegarde locale (GPKG/SHP) + upload Google Drive.
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Optional

import geopandas as gpd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import src.config as cfg

logger = logging.getLogger("cadastre.storage")

_DRIVERS: dict[str, str] = {
    ".gpkg": "GPKG",
    ".shp":  "ESRI Shapefile",
}
_GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


# ──────────────────────────────────────────────────────────────────────────────
# Chemins de sortie
# ──────────────────────────────────────────────────────────────────────────────
def _output_path(name: str, suffix: str, timestamp: str) -> Path:
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return cfg.DATA_DIR / f"{name}_{timestamp}{suffix}"


# ──────────────────────────────────────────────────────────────────────────────
# Sauvegarde locale
# ──────────────────────────────────────────────────────────────────────────────
def save_layered(
    layers   : dict[str, gpd.GeoDataFrame],
    name     : str,
    timestamp: str,
    fmt      : str = ".gpkg",
    encoding : str = "utf-8",
) -> Optional[Path]:
    """
    Sauvegarde un dict {couche: GeoDataFrame} dans un fichier multi-couches.
    Retourne le chemin créé ou None si rien à sauvegarder.
    """
    if not layers:
        logger.warning("save_layered('%s') — dict vide.", name)
        return None

    driver  = _DRIVERS.get(fmt, "GPKG")
    path    = _output_path(name, fmt, timestamp)
    written = 0

    for layer_name, gdf in layers.items():
        if gdf.empty:
            logger.warning("Couche '%s' vide — ignorée.", layer_name)
            continue
        # GPKG supporte l'ajout de couches (mode "a"), SHP nécessite "w"
        mode = "a" if fmt == ".gpkg" else "w"
        gdf.to_file(str(path), layer=layer_name, driver=driver, encoding=encoding, mode=mode)
        logger.info("  ↳ Couche '%s' écrite → %s", layer_name, path.name)
        written += 1

    if written:
        logger.info("✅ '%s' sauvegardé (%d couche(s)).", path.name, written)
        return path

    logger.warning("Aucune couche non-vide à écrire pour '%s'.", name)
    return None


def save_single(
    gdf      : gpd.GeoDataFrame,
    name     : str,
    timestamp: str,
    fmt      : str = ".gpkg",
    encoding : str = "utf-8",
) -> Optional[Path]:
    """Sauvegarde un GeoDataFrame unique. Retourne le chemin ou None."""
    if gdf.empty:
        logger.warning("save_single('%s') — GeoDataFrame vide.", name)
        return None

    driver = _DRIVERS.get(fmt, "GPKG")
    path   = _output_path(name, fmt, timestamp)
    gdf.to_file(str(path), driver=driver, encoding=encoding, mode="w")
    logger.info("✅ '%s' sauvegardé (%d features).", path.name, len(gdf))
    return path


# ──────────────────────────────────────────────────────────────────────────────
# Google Drive
# ──────────────────────────────────────────────────────────────────────────────
def _build_drive_service():
    """
    Construit le client Drive API v3.
    Stratégie :
      1. Service Account JSON  → GDRIVE_SA_JSON (prioritaire)
      2. OAuth2 refresh token → GDRIVE_CLIENT_ID / _SECRET / _REFRESH_TOKEN
    """
    sa_path = Path(cfg.GDRIVE_CREDS_FILE)

    # ── Méthode 1 : Service Account JSON ───────────────────────────────────
    if sa_path.exists() and cfg.GDRIVE_SA_JSON:
        logger.info("Drive auth : Service Account (%s).", sa_path)
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path),
            scopes=_GDRIVE_SCOPES,
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # ── Méthode 2 : OAuth2 (refresh token) ─────────────────────────────────
    if cfg.GDRIVE_CLIENT_ID and cfg.GDRIVE_CLIENT_SECRET and cfg.GDRIVE_REFRESH_TOKEN:
        logger.info("Drive auth : OAuth2 refresh token.")
        creds = Credentials(
            token=None,
            refresh_token=cfg.GDRIVE_REFRESH_TOKEN,
            client_id=cfg.GDRIVE_CLIENT_ID,
            client_secret=cfg.GDRIVE_CLIENT_SECRET,
            scopes=_GDRIVE_SCOPES,
        )
        creds.refresh(Request())
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    raise FileNotFoundError(
        "Aucune méthode d'authentification Drive disponible.\n"
        "→ Définissez GDRIVE_SA_JSON (chemin vers le JSON du SA)\n"
        "   OU  GDRIVE_CLIENT_ID + GDRIVE_CLIENT_SECRET + GDRIVE_REFRESH_TOKEN.\n"
        "→ Vérifiez les secrets GitHub : GDRIVE_SA_JSON, GDRIVE_CLIENT_ID, "
        "GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN."
    )


def _list_drive_files(service, folder_id: str, name_prefix: str) -> list[dict]:
    """Liste les fichiers d'un dossier Drive dont le nom commence par `name_prefix`."""
    query = (
        f"'{folder_id}' in parents "
        f"and name contains '{name_prefix}' "
        f"and trashed=false"
    )
    result = service.files().list(
        q=query,
        fields="files(id, name, createdTime)",
        orderBy="createdTime desc",
    ).execute()
    return result.get("files") or []


def _delete_old_files(service, files: list[dict], keep: int) -> None:
    """Supprime les fichiers excédentaires (conserve les `keep` plus récents)."""
    for f in files[keep:]:
        service.files().delete(fileId=f["id"]).execute()
        logger.info("🗑️  Fichier Drive supprimé : %s", f["name"])


def upload_to_drive(local_path: Path, folder_id: Optional[str] = None) -> Optional[str]:
    """
    Upload un fichier local sur Google Drive.
    Retourne l'ID Drive du fichier uploadé, ou None en cas d'erreur.
    """
    folder_id = folder_id or cfg.DRIVE_FOLDER_ID
    if not folder_id:
        logger.error("DRIVE_FOLDER_ID non défini — upload ignoré.")
        return None
    if not local_path.exists():
        logger.error("Fichier introuvable pour upload : %s", local_path)
        return None

    try:
        service   = _build_drive_service()
        mime_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

        # Récupérer les anciens fichiers avant upload (pour rotation)
        prefix   = local_path.stem.split("_")[0]
        existing = _list_drive_files(service, folder_id, prefix)

        # Upload
        meta    = {"name": local_path.name, "parents": [folder_id]}
        media   = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
        result  = service.files().create(
            body=meta, media_body=media, fields="id, name"
        ).execute()

        file_id: str = result["id"]
        logger.info("✅ Upload Drive OK : %s (id=%s)", result["name"], file_id)

        # Rotation : suppression des anciens fichiers excédentaires
        _delete_old_files(service, existing, keep=cfg.GDRIVE_KEEP_LAST_N - 1)

        return file_id

    except Exception as exc:
        logger.error("❌ Échec upload Drive (%s) : %s", local_path.name, exc)
        return None


def upload_outputs(paths: list[Optional[Path]]) -> dict[str, str]:
    """
    Upload une liste de fichiers locaux sur Drive.
    Ignore les None et les formats absents de GDRIVE_UPLOAD_FORMATS.
    Retourne {filename: drive_id}.
    """
    results: dict[str, str] = {}
    for path in paths:
        if path is None:
            continue
        if path.suffix not in cfg.GDRIVE_UPLOAD_FORMATS:
            logger.debug("Format '%s' ignoré (hors GDRIVE_UPLOAD_FORMATS).", path.suffix)
            continue
        drive_id = upload_to_drive(path)
        if drive_id:
            results[path.name] = drive_id
    return results
