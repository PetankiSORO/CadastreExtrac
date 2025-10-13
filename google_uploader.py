# google_uploader.py
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

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
    # cache_discovery=False évite l’avertissement sur le cache local
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def upload_file_to_drive(filepath, folder_id, mime=None):
    service = build_drive_service_from_oauth()
    meta = {"name": os.path.basename(filepath), "parents": [folder_id]}
    media = MediaFileUpload(filepath, mimetype=mime, resumable=True)
    created = service.files().create(body=meta, media_body=media, fields="id").execute()
    return created["id"]
