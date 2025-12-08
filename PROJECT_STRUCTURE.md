# 📁 Structure du Projet Radar Hexatrust

## Vue d'ensemble

```
RADAR_HEXATRUST/
├── .github/                    # 🤖 Automatisation GitHub
│   ├── ISSUE_TEMPLATE/         # Formulaires d'issues
│   │   └── add_company.yml     # Formulaire d'ajout d'entreprise
│   ├── workflows/              # GitHub Actions
│   │   ├── process-new-company.yml    # Traitement des nouvelles entreprises
│   │   └── regenerate-radar.yml       # Régénération automatique
│   ├── scripts/                # Scripts d'automatisation
│   │   └── parse_issue.py      # Parser d'issues GitHub
│   └── README.md               # Documentation GitHub Actions
│
├── assets/                     # 📦 Ressources
│   ├── Mask/                  # Gabarits et template du radar
│   ├── Report/                # Rapports générés (CSV/XLSX)
│   ├── logos/                 # Logos des entreprises (260 fichiers)
│   ├── Panorama_cyber.svg     # Radar généré (SVG)
│   ├── Panorama_cyber.png     # Radar généré (PNG)
│   └── solutions.xlsx         # Base de données Excel
│
├── docs/                       # 📚 Documentation
│   ├── USAGE.md                # Guide d'utilisation complet
│   └── CHANGELOG.md            # Historique des changements
│
├── src/                        # 💻 Code source Python
│   ├── config.py               # Configuration centralisée
│   ├── main.py                 # Génération du radar (core)
│   └── read_solutions.py       # Lecture des données Excel
│
├── .gitignore                  # Configuration Git
├── README.md                   # Documentation principale
├── requirements.txt            # Dépendances Python
└── PROJECT_STRUCTURE.md        # Ce fichier
```

---

## 📂 Description Détaillée

### `.github/` - Automatisation GitHub

Contient toute l'infrastructure d'automatisation via GitHub Actions :

- **ISSUE_TEMPLATE/add_company.yml** : Formulaire structuré pour proposer l'ajout d'une entreprise
- **workflows/process-new-company.yml** : Workflow qui s'exécute quand une issue est approuvée
- **workflows/regenerate-radar.yml** : Régénération quotidienne automatique du radar
- **scripts/parse_issue.py** : Parse les issues GitHub et ajoute les entreprises
- **README.md** : Documentation technique de l'automatisation

### `assets/` - Ressources

Contient toutes les ressources du projet :

- **Mask/** : Template SVG original (`Radar_Hexatrust_Cesin.svg`) et masques générés
- **Report/** : Rapports générés (`rapport_logos_places.csv`, `logo_recap.xlsx`, `report.csv`)
- **logos/** : 260+ logos d'entreprises au format PNG, SVG, WebP, JPG
- **Panorama_cyber.svg** : Radar généré avec les logos (SVG)
- **Panorama_cyber.png** : Radar généré (PNG)
- **solutions.xlsx** : Base de données principale (4.1 MB, 314 entreprises)

### `docs/` - Documentation

- **USAGE.md** : Guide complet d'utilisation (toutes les fonctionnalités)
- **CHANGELOG.md** : Historique des changements et nouvelles fonctionnalités

### `src/` - Code Source

Code Python organisé en modules :

- **config.py** : Configuration centralisée (chemins, mappings, paramètres)
- **main.py** : Algorithme de génération du radar (placement des logos)
- **read_solutions.py** : Chargement et parsing du fichier Excel

---

## 🚀 Points d'Entrée

### 1. Formulaire GitHub (Recommandé - 100% Automatique)
Créer une issue avec le template "Ajouter une entreprise"
→ Un mainteneur valide avec le label `approved`
→ GitHub Actions fait tout automatiquement

### 2. Génération Locale (Développeurs)
```bash
python3 src/main.py
```
Génère le radar SVG/PNG directement

---

## 📊 Statistiques

- **Fichiers Python** : 3 modules (src/)
- **Workflows GitHub** : 2 (automatisation complète)
- **Logos** : 260+ fichiers
- **Entreprises** : 314 dans le fichier Excel
- **Documentation** : 4 fichiers Markdown

---

## 🎯 Flux de Travail

### Flux Principal (GitHub Actions - Automatique)

```
Utilisateur → Formulaire GitHub
     ↓
Issue créée automatiquement
     ↓
Mainteneur ajoute label "approved"
     ↓
GitHub Actions triggered
     ↓
parse_issue.py extrait données
     ↓
Télécharge logo depuis URL
     ↓
Ajoute au Excel (pandas)
     ↓
src/main.py régénère le radar
     ↓
Commit et push automatique
     ↓
Notification à l'utilisateur
```

### Flux Alternatif (Développeurs - Local)

```
git clone → Modifier Excel/logos
     ↓
python3 src/main.py (test local)
     ↓
git commit && git push
     ↓
GitHub Actions régénère automatiquement
```

---

## 🔧 Configuration

Toute la configuration est centralisée dans `src/config.py` :

- Chemins des fichiers et dossiers
- Mapping des fonctions NIST
- Paramètres du radar (tailles, couleurs)
- Extensions de fichiers acceptées

---

## 📝 Notes

- **Simplicité** : Architecture simplifiée, focus sur GitHub Actions
- **Modularité** : Code Python minimal et ciblé (génération du radar)
- **Documentation** : Documentation complète et à jour
- **Automatisation** : 100% automatique via GitHub Actions
- **Accessibilité** : Pas d'installation locale nécessaire pour contribuer

---

**Dernière mise à jour** : 2025-11-05
**Version** : 3.0 (GitHub-only)
