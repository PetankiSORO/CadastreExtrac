# main.py (ajoute ces lignes à la fin)
import os, glob, mimetypes
from pathlib import Path
import google_uploader as gu
import utils as u
import config as c

if __name__ == "__main__":
    # 1) exécuter ton scraping existant
    html = u.extract_html(c.url).text
    html_json = u.extract_json(html)
    data_info = u.extract_data_info(html_json)
    data_json = u.extract_data_json(data_info)
    data_feature = u.extract_data_feature(data_json)

    licence = u.fusion_feature(data_feature.get("Demandes", {}), data_feature.get("Licences", {}))
    admin = data_feature.get("Administration", {})

    print (" ")
    u.save_file_admin(admin, "Admin_Ci")
    u.save_file_licence(licence, "Cadastre_Minier_Ci")
    print (" ")
    u.fin()
    
    # 2) Lister les fichiers locaux avant envoi
    output_dir = os.environ.get("OUTPUT_DIR", getattr(c, "output", "outputs/")).rstrip("/")
    files = sorted(Path(output_dir).glob("*"))

    print(f"[LOCAL] Dossier de sortie : {output_dir}")
    print(f"[LOCAL] Nombre de fichiers détectés : {len(files)}")
    for f in files:
        try:
            size = f.stat().st_size
        except Exception as e:
            size = f"(taille inconnue : {e})"
        print(f"[LOCAL] - {f.name} ({size} octets)")

    if not files:
        raise SystemExit(f"[ERREUR] Aucun fichier trouvé dans '{output_dir}'. "
                         f"Vérifie la cohérence entre config.output et l’écriture des fichiers.")

    # 3) Upload vers Google Drive
    output_dir = os.environ.get("OUTPUT_DIR", "outputs")
    folder_id  = os.environ["DRIVE_FOLDER_ID"]

    def guess_mime(p: Path) -> str | None:
        # Drive sait deviner, mais on pose un mime pour .gpkg
        if p.suffix.lower() == ".gpkg":
            return "application/geopackage+sqlite3"
        return None

    files = [p for p in Path(output_dir).glob("*") if p.is_file()]

    print(f"[LOCAL] Dossier de sortie : {output_dir}")
    print(f"[LOCAL] Nombre de fichiers détectés : {len(files)}")
    for p in files:
        try:
            mime = guess_mime(p)
            fid = gu.upload_file_to_drive(str(p), folder_id, mime=mime)
            print(f"[DRIVE] Upload OK: {p.name} → fileId={fid}")
        except Exception as e:
            print(f"[DRIVE] ERREUR sur {p.name} : {e}")

