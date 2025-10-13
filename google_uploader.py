# google_uploader.py
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

# === CHOISIR LE SCOPE ICI ===
# Option A (recommandé, plus simple) :
# SCOPES = ["https://www.googleapis.com/auth/drive"]
# Option B (minimal, plus restreint) :
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def build_drive_service_from_oauth():
    creds = Credentials(
        None,
        refresh_token=os.environ["GDRIVE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GDRIVE_CLIENT_ID"],
        client_secret=os.environ["GDRIVE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def ensure_folder_exists(folder_id: str | None, fallback_name: str = "CadastreMine_Extrac") -> str:
    """
    - Si folder_id est fourni, on tente de le lire (avec supportsAllDrives=True).
      * Si ça 404 en scope drive.file, on lèvera et le caller décidera quoi faire.
    - Si folder_id est vide (ou introuvable), on crée un dossier dans Mon Drive (root).
    Retourne l'ID du dossier utilisable pour l’upload.
    """
    service = build_drive_service_from_oauth()

    if folder_id:
        try:
            service.files().get(
                fileId=folder_id,
                fields="id,name,driveId",
                supportsAllDrives=True
            ).execute()
            return folder_id
        except HttpError as e:
            # 404 -> on crée un nouveau dossier plutôt que d'échouer
            if getattr(e, "status_code", None) == 404 or "notFound" in str(e):
                print("[DRIVE] folderId invalide/invisible. Création d’un nouveau dossier dans Mon Drive.")
            else:
                raise

    
    # Créer un dossier dans "Mon Drive"
    meta = {"name": fallback_name, "mimeType": "application/vnd.google-apps.folder"}
    created = service.files().create(
        body=meta,
        fields="id",
        supportsAllDrives=True
    ).execute()
    return created["id"]

def upload_file_to_drive(filepath, folder_id, mime=None):
    service = build_drive_service_from_oauth()
    meta = {"name": os.path.basename(filepath), "parents": [folder_id]}
    media = MediaFileUpload(filepath, mimetype=mime, resumable=True)
    created = service.files().create(
        body=meta,
        media_body=media,
        fields="id",
        supportsAllDrives=True  # important pour My Drive & Shared Drives
    ).execute()
    return created["id"]
