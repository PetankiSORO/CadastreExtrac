# main.py (ajoute ces lignes à la fin)
import os, glob, mimetypes
import GoogleUploader  # ← importe la fonction ajoutée au-dessus
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

    # 2) uploader tout le dossier outputs/ vers Drive
    folder_id = os.environ["DRIVE_FOLDER_ID"]
    for path in glob.glob("outputs/*"):
        mime, _ = mimetypes.guess_type(path)
        fid = upload_file_to_drive(path, folder_id, mime=mime)
        print(f"[UPLOAD] {path} -> file_id={fid}")
