# 📡 CadastreExtrac

[![CI/CD](https://github.com/PetankiSORO/CadastreExtrac/actions/workflows/cadastre_daily.yml/badge.svg)](https://github.com/PetankiSORO/CadastreExtrac/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Extraction automatique quotidienne** des données du Cadastre Minier de Côte d'Ivoire depuis le portail [LandFolio](https://portals.landfolio.com/CoteDIvoire/FR/) — orchestration par **GitHub Actions** et synchronisation vers **Google Drive**.

---

## 📋 Table des matières

1. [Présentation](#-présentation)
2. [Architecture](#-architecture)
3. [Prérequis](#-prérequis)
4. [Installation locale](#-installation-locale)
5. [Configuration](#-configuration)
6. [Utilisation](#-utilisation)
7. [CI/CD — GitHub Actions](#-cicd--github-actions)
8. [Dépannage](#-dépannage)
9. [Contribuer](#-contribuer)
10. [Licence](#-licence)

---

## 🎯 Présentation

### But du projet

Extraire chaque jour, sans intervention humaine, les couches cartographiques du **Cadastre Minier** et les rendre disponibles sur **Google Drive**.

Les données extraites incluent :
- Concessions minières
- Permis d'exploration, d'exploitation et de recherche
- Zones immobilières et d'occupation

### Flux de données

```
 Portail LandFolio
        │
        ▼
 ┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
 │  Scrapping   │────▶│  Parsing      │────▶│  Export CSV /    │
 │  MapServices │     │  GeoJSON      │     │  GeoJSON + Logs  │
 └──────────────┘     └───────────────┘     └────────┬─────────┘
                                                     │
                                            ┌────────▼────────┐
                                            │  Google Drive   │
                                            │  (Drive API)    │
                                            └─────────────────┘
```

---

## 🏗️ Architecture

```
CadastreExtrac/
├── .github/
│   └── workflows/
│       └── cadastre_daily.yml     ← Planification Cron (quotidienne)
├── src/
│   ├── __init__.py
│   ├── config.py                  ← Constantes de configuration
│   ├── logging_setup.py          ← Logger avec rotation automatique
│   ├── http_client.py             ← Client HTTP avec retry & timeout
│   ├── parser.py                  ← Parsing JSON + extraction métadonnées
│   ├── geo.py                     ← Transformation géométries (WGS84)
│   └── storage.py                 ← Sauvegarde CSV/GeoJSON + upload Drive
├── main.py                        ← Point d'entrée
├── requirements.txt              ← Dépendances Python
├── .gitignore
├── README.md
└── LICENSE
```

### Flux d'exécution

```
main.py
  │
  ├─ ensure_output_dirs()           → crée data/log/
  ├─ fetch_services()               → GET sur le portail LandFolio
  ├─ extract_service_urls()          → parse le JSON LandFolio
  ├─ extract_layer_info()            → extrait les métadonnées
  │
  ├─ Pour chaque service :
  │    ├─ fetch_layer()             → GET avec retry exponentiel
  │    ├─ extract_data_info()       → parse la réponse ESRI
  │    ├─ parse_geojson()           → conversion géométries
  │    ├─ save_geojson()            → export GeoJSON
  │    └─ save_csv()                → export CSV
  │
  └─ upload_to_drive()              → upload sur Google Drive (CI only)
```

---

## ✅ Prérequis

### Environnement local

| Outil | Version minimum | Usage |
|-------|----------------|-------|
| Python | 3.10+ | Interpréteur |
| pip | última | Gestionnaire de paquets |

### CI/CD (GitHub Actions)

| Ressource | Détail | Obtention |
|-----------|--------|-----------|
| Service Account Google | Rôle Éditeur sur Drive | Google Cloud Console → IAM |
| Folder ID Drive | Dossier cible | URL Drive : `drive.google.com/.../folders/<ID>` |
| Secrets GitHub | Tous les secrets listés ci-dessous | Paramètres du repo → Secrets and variables → Actions |

> **En CI/CD, tous les secrets sont configurés dans GitHub → Settings → Secrets and variables → Actions. Pour le fichier JSON du Service Account, copiez-collez son contenu complet dans `GDRIVE_SA_JSON`.**

---

## 💻 Installation locale

### 1. Cloner le dépôt

```bash
git clone https://github.com/PetankiSORO/CadastreExtrac.git
cd CadastreExtrac
```

### 2. Créer un environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Vérifier le bon fonctionnement

```bash
python main.py
```

Le script crée :
- `data/` — fichiers CSV et GeoJSON exportés
- `data/log/` — logs horodatés avec rotation automatique (14 jours)

---

## ⚙️ Configuration

### Variables d'environnement (optionnel)

Pour une exécution locale avec upload Drive, créez un fichier `.env` :

```bash
# .env (NE PAS COMMITER — déjà dans .gitignore)
cp .env.example .env   # puis remplir les valeurs
```

> ⚠️ **En CI/CD, les secrets sont configurés dans GitHub → Settings → Secrets and variables → Actions. Le fichier `.env.example` liste tous les secrets nécessaires.**

### Ajuster les paramètres

Éditez `src/config.py` :

```python
# Timeout des requêtes HTTP (secondes)
TIMEOUT = 15

# Nombre d'enregistrements par requête
RECORD_COUNT = 1000

# Couches à extraire (True = active, False = ignorée)
LAYERS = {
    "DR_Concessions": True,
    "DR_Permis_Exploration": True,
    "DR_Permis_Exploitation": True,
    "DR_Permis_Recherche": True,
    "DR_Permis_Sensibles": True,
    "DR_Zones_Immobilieres": True,
    "DR_Zones_Occupation": True,
}
```

---

## 🚀 Utilisation

### Exécution locale

```bash
# Activation de l'environnement
source .venv/bin/activate

# Lancer l'extraction
python main.py
```

### Sorties générées

```
data/
├── DR_Concessions_2026-06-16.json
├── DR_Concessions_2026-06-16.csv
├── DR_Permis_Exploration_2026-06-16.json
├── DR_Permis_Exploration_2026-06-16.csv
└── ...
data/log/
├── cadastre_2026-06-16.log
└── cadastre_2026-06-17.log     ← nouveau à chaque exécution
```

### Format GeoJSON

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [-5.234, 5.123],
          [-5.230, 5.125],
          [-5.231, 5.130],
          [-5.234, 5.123]
        ]]
      },
      "properties": {
        "NAME": "SOpéra Sud 1",
        "SUBSTANCE": "Or",
        "HOLDER": "Société Minière...",
        "EXPIRY_DATE": "2026-08-12",
        "AREA_HA": 25631.45
      }
    }
  ]
}
```

---

## 🔄 CI/CD — GitHub Actions

### Planification

Le workflow `cadastre_daily.yml` s'exécute **quotidiennement à 02h00 UTC** :

```yaml
on:
  schedule:
    - cron: '0 2 * * *'      # Chaque jour à 02h00 UTC
  workflow_dispatch:           # Déclenchement manuel
```

### Workflow complet

> Le workflow complet est dans [`.github/workflows/cadastre_daily.yml`](.github/workflows/cadastre_daily.yml).
> Voir la section [CI/CD](#-cicd--github-actions) pour le détail de la planification et des étapes.

### Configurer les secrets GitHub

```
1. Ouvrir https://github.com/PetankiSORO/CadastreExtrac/settings/secrets/actions
2. Cliquer sur "New repository secret"
3. Ajouter TOUS les secrets :

┌─────────────────────────────┬────────────────────────────────────────────────────────┐
│ Secret                      │ Comment obtenir / Description                          │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ URL_CADASTRE                │ URL du Cadastre a extraire                             │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ PROXY_BASE                  │ Proxy HTTP (optionnel, laisser vide sinon)             │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ PROXY_REFERER               │ URL du Cadastre a extraire                             │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ DRIVE_FOLDER_ID             │ URL Drive : .../folders/<ID>                           │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ GDRIVE_SA_JSON              │ Google Cloud → IAM → SA → Keys → Create Key (JSON)     │
│                             │ → Copier TOUT le contenu du fichier JSON               │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ GDRIVE_CLIENT_ID            │ Google Cloud → APIs & Services → Credentials → OAuth2  │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ GDRIVE_CLIENT_SECRET        │ Google Cloud → APIs & Services → Credentials → OAuth2  │
├─────────────────────────────┼────────────────────────────────────────────────────────┤
│ GDRIVE_REFRESH_TOKEN        │ OAuth Playground ou code OAuth2 (optionnel si SA)      │
└─────────────────────────────┴────────────────────────────────────────────────────────┘

⚠️  GDRIVE_SA_JSON est prioritaire sur OAuth2. OAuth2 (CLIENT_ID/SECRET/REFRESH_TOKEN)
    n'est utilisé que si GDRIVE_SA_JSON n'est pas configuré.
```

### Préparer le Service Account Google

```bash
# 1. Google Cloud Console → IAM → Créer un compte de service (rôle Éditeur Drive)
# 2. Keys → Create Key → JSON → Télécharger
# 3. Copier TOUT le contenu du JSON dans le secret GDRIVE_SA_JSON
```

```bash
# Copier le contenu du JSON (macOS/Linux)
cat /chemin/vers/cle.json | pbcopy
```

```powershell
# Copier le contenu du JSON (Windows PowerShell)
Get-Content C:\chemin\vers\cle.json | Set-Clipboard
```

**Partager le dossier Drive** avec l'email du Service Account (`xxx@project.iam.gserviceaccount.com`) en rôle **Éditeur**.

### Déclenchement manuel

```
GitHub → Actions → Cadastre Daily Extraction → Run workflow
```

---

## 🐛 Dépannage

### Erreur `ConnectionError` / timeout

```
HTTPError: 504 Gateway Timeout
```

→ Le portail LandFolio est temporairement indisponible. Le script réessaie automatiquement (3 tentatives avec backoff exponentiel). Si l'échec persiste, vérifiez le statut du portail manuellement.

### Erreur `403 Forbidden` sur l'API Google Drive

```
googleapiclient.errors.HttpError: 403 Insufficient Permission
```

**Solutions :**

1. Vérifier que le Service Account a le rôle **Éditeur** sur le dossier Drive
2. Confirmer que le dossier a été partagé avec l'email du Service Account
3. Regenerer la clé JSON et mettre à jour le secret `GDRIVE_CREDENTIALS_JSON`

### Erreur `FileNotFoundError` sur les logs

```
FileNotFoundError: [Errno 2] No such file or directory: 'data/log'
```

→ Le script crée automatiquement le dossier `data/log/` au démarrage. Si le problème persiste, vérifiez les permissions du répertoire courant.

### Erreur `JSONDecodeError`

```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1
```

→ Le portail a changé sa structure de réponse. Ouvrez un [Issue GitHub](https://github.com/PetankiSORO/CadastreExtrac/issues) avec le log complet.

### Vérifier le statut du dernier run

```
https://github.com/PetankiSORO/CadastreExtrac/actions/workflows/cadastre_daily.yml
```

---

## 🤝 Contribuer

Les contributions sont les bienvenues ! Pour proposer une modification :

```bash
# 1. Forker le dépôt
# 2. Créer une branche
git checkout -b feature/ma-fonctionnalite

# 3. Appliquer les modifications
# 4. Ajouter des tests si applicable
# 5. Commiter
git commit -m 'feat: nouvelle fonctionnalité'

# 6. Pousser et ouvrir une Pull Request
git push origin feature/ma-fonctionnalite
```

### Standards de code

- Python ≥ 3.10 (annotations de type recommandées)
- Pas de classes — fonctions pures uniquement
- Logger pour toute sortie (pas de `print()`)
- Tests unitaires dans `tests/`

---

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🔗 Ressources

- [Documentation Google Drive API](https://developers.google.com/drive/api/guides/about-files)
- [GitHub Actions — Documentation](https://docs.github.com/en/actions)
- [ESRI REST API — Query](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-.md)

---

*CadastreExtrac v2.0*
