# main.py (ajoute ces lignes à la fin)
import os, glob, mimetypes
from Google  # ← importe la fonction ajoutée au-dessus

if __name__ == "__main__":
    # 1) exécuter ton scraping existant


    # 2) uploader tout le dossier outputs/ vers Drive
    folder_id = os.environ["DRIVE_FOLDER_ID"]
    for path in glob.glob("outputs/*"):
        mime, _ = mimetypes.guess_type(path)
        fid = upload_file_to_drive(path, folder_id, mime=mime)
        print(f"[UPLOAD] {path} -> file_id={fid}")
