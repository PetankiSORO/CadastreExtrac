# utils.py (ajoute ce bloc à la fin, sans casser tes fonctions existantes)
import os
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def _drive_service(sa_path: Optional[str] = None):
    sa_path = sa_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "sa.json")
    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=_SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def upload_file_to_drive(local_path: str, folder_id: str, mime: Optional[str] = None) -> str:
    """
    Envoie un fichier local vers Google Drive dans le dossier folder_id.
    Retourne l'ID du fichier créé.
    """
    service = _drive_service()
    meta = {"name": os.path.basename(local_path), "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)
    created = service.files().create(body=meta, media_body=media, fields="id").execute()
    return created["id"]
