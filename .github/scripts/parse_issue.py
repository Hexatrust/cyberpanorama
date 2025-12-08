#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour parser une GitHub Issue et ajouter l'entreprise au radar
"""
import os
import sys
import re
import requests
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import FONCTION_TO_CLASS, EXCEL_FILE, LOGOS_DIR


def download_logo(url, company_name, logos_dir='assets/logos'):
    """Télécharge le logo depuis une URL"""
    try:
        print(f"Téléchargement du logo depuis: {url}")

        # Headers pour éviter les blocages (403 Forbidden) de certains sites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # Télécharger le fichier
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()

        # Déterminer l'extension
        content_type = response.headers.get('content-type', '')
        ext_mapping = {
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/svg+xml': 'svg',
            'image/webp': 'webp'
        }

        ext = ext_mapping.get(content_type)
        if not ext:
            # Essayer de deviner depuis l'URL
            ext = url.split('.')[-1].lower()
            if ext not in ['png', 'jpg', 'jpeg', 'svg', 'webp']:
                ext = 'png'  # Par défaut

        # Normaliser le nom (garder les espaces, remplacer seulement les caractères invalides)
        normalized_name = company_name.replace('/', '_').replace('\\', '_')

        # Trouver le prochain numéro disponible
        counter = 1
        while True:
            filename = f"{normalized_name}_{counter:02d}.{ext}"
            filepath = Path(logos_dir) / filename
            if not filepath.exists():
                break
            counter += 1

        # Sauvegarder le fichier
        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"✓ Logo sauvegardé: {filepath}")
        return str(filepath)

    except Exception as e:
        print(f"✗ Erreur lors du téléchargement du logo: {e}")
        return None


def parse_issue_body(body):
    """Parse le corps de l'issue pour extraire les informations"""
    data = {}

    # Patterns pour extraire les informations
    # Note: Utilisation de [^\n]+ pour capturer seulement la première ligne après le titre
    # Patterns plus robustes avec \s+ pour gérer les variations d'espaces
    # Support de tous les types d'apostrophes: ' (U+0027), ' (U+2018), ' (U+2019)
    patterns = {
        'company_name': r"###\s*🏢\s*Nom\s+de\s+l[''']entreprise/solution\s*\n+\s*([^\n]+)",
        'fonction_nist': r'###\s*🎯\s*Fonction\s+NIST\s+principale\s*\n+\s*([^\n]+)',
        'taille': r"###\s*📏\s*Taille\s+de\s+l[''']entreprise\s*\n+\s*([^\n]+)",
        'description': r'###\s*📝\s*Description\s+de\s+la\s+solution\s*\n+\s*(.+?)(?=\n###|\Z)',
        'website': r'###\s*🌐\s*Site\s+web\s*\n+\s*([^\n]+)',
        'logo_url': r'###\s*🖼️\s*URL\s+du\s+logo\s*\n+\s*([^\n]+)',
        'objectif_nis2': r'###\s*🛡️\s*Objectif\s+NIS2\s+principal\s*\(optionnel\)\s*\n+\s*([^\n]+)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            # Nettoyer les valeurs
            if value and value != '_No response_' and value != 'N/A' and value != '(Aucun)':
                data[key] = value
                print(f"  [DEBUG] Trouvé {key}: {value[:80]}...")
        else:
            print(f"  [DEBUG] Pattern non trouvé pour: {key}")

    # Parser les sous-fonctions NIST (checkboxes)
    sous_fonctions_section = re.search(
        r'###\s*🔍\s*Sous-fonctions\s+NIST\s+CSF\s+2\.0\s*\(optionnel,\s*max\s+3\)\s*\n(.*?)(?=\n###|\Z)',
        body,
        re.MULTILINE | re.DOTALL
    )
    if sous_fonctions_section:
        # Extraire les checkboxes cochées (contiennent [X] ou [x])
        checked_items = re.findall(r'-\s+\[x\]\s+(.+)', sous_fonctions_section.group(1), re.IGNORECASE)
        if checked_items:
            # Extraire seulement les codes (ex: "GV.OC")
            codes = [item.split(' - ')[0].strip() for item in checked_items[:3]]  # Max 3
            data['sous_fonctions_nist'] = ', '.join(codes)
            print(f"  [DEBUG] Trouvé sous_fonctions_nist: {', '.join(codes)}")
        else:
            print(f"  [DEBUG] Aucune sous-fonction NIST cochée")
    else:
        print(f"  [DEBUG] Section sous-fonctions NIST non trouvée")

    return data


def extract_taille_number(taille_str):
    """Extrait le numéro de taille depuis la chaîne du dropdown"""
    # Format: "1 - Large (grande entreprise, solution mature)"
    match = re.match(r'^(\d+)', taille_str)
    if match:
        return int(match.group(1))
    return 2  # Par défaut medium


def add_company_to_excel(company_name, fonction_nist, taille, logo_path, description='',
                         sous_fonctions_nist='', objectif_nis2=''):
    """Ajoute une entreprise directement au fichier Excel"""
    try:
        # Charger le fichier Excel
        df = pd.read_excel(EXCEL_FILE)

        # Vérifier si l'entreprise existe déjà
        if company_name in df['Solutions'].values:
            print(f"⚠️  L'entreprise '{company_name}' existe déjà dans le fichier Excel")
            return False

        # Créer une nouvelle ligne
        new_row = {
            'Solutions': company_name,
            'Fonction NIST': fonction_nist,
            'Taille': taille,
            'Logo': os.path.basename(logo_path) if logo_path else ''
        }

        # Ajouter la description si la colonne existe
        if 'Description' in df.columns and description:
            new_row['Description'] = description

        # Ajouter les sous-fonctions NIST si la colonne existe
        if 'Sous-fonctions NIST' in df.columns and sous_fonctions_nist:
            new_row['Sous-fonctions NIST'] = sous_fonctions_nist

        # Ajouter l'objectif NIS2 si la colonne existe
        if 'Objectif NIS2' in df.columns and objectif_nis2:
            new_row['Objectif NIS2'] = objectif_nis2

        # Ajouter la nouvelle ligne
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Sauvegarder avec openpyxl pour préserver le formatage
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')

        print(f"✅ Entreprise '{company_name}' ajoutée au fichier Excel")
        return True

    except Exception as e:
        print(f"✗ Erreur lors de l'ajout au fichier Excel: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_issue.py <issue_number>")
        sys.exit(1)

    issue_number = sys.argv[1]
    github_token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', 'RobinEY-prog/RADAR_HEXATRUST')

    if not github_token:
        print("✗ GITHUB_TOKEN non défini")
        sys.exit(1)

    print("=" * 60)
    print(f"TRAITEMENT DE L'ISSUE #{issue_number}")
    print("=" * 60)

    # Récupérer l'issue depuis GitHub
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"✗ Erreur lors de la récupération de l'issue: {response.status_code}")
        sys.exit(1)

    issue = response.json()
    body = issue['body']

    # Afficher le corps de l'issue pour debug
    print("\n" + "-" * 60)
    print("Corps de l'issue (DEBUG):")
    print("-" * 60)
    print(body)
    print("-" * 60)

    # Parser les données
    data = parse_issue_body(body)

    print("\nDonnées extraites:")
    if data:
        for key, value in data.items():
            # Afficher les URLs complètes, tronquer seulement les descriptions longues
            if key in ['logo_url', 'website']:
                print(f"  ✓ {key}: {value}")
            else:
                print(f"  ✓ {key}: {value[:150] if len(str(value)) > 150 else value}")
    else:
        print("  ⚠️  Aucune donnée extraite de l'issue")

    # Valider les données obligatoires
    required_fields = ['company_name', 'fonction_nist', 'taille', 'logo_url']
    missing = [f for f in required_fields if f not in data]

    if missing:
        print(f"\n✗ Champs manquants: {', '.join(missing)}")
        print("\n💡 Vérifiez que l'issue a été créée avec le bon template:")
        print("   - Template 'Ajouter une entreprise' pour une nouvelle entreprise")
        print("   - Template 'Modifier une entreprise' pour une modification")
        sys.exit(1)

    # Extraire les valeurs
    company_name = data['company_name']
    fonction_nist = data['fonction_nist']
    taille = extract_taille_number(data['taille'])
    logo_url = data['logo_url']
    description = data.get('description', '')
    sous_fonctions_nist = data.get('sous_fonctions_nist', '')
    objectif_nis2 = data.get('objectif_nis2', '')

    # Valider la fonction NIST
    if fonction_nist not in FONCTION_TO_CLASS:
        print(f"\n✗ Fonction NIST invalide: {fonction_nist}")
        print(f"   Fonctions valides: {', '.join(FONCTION_TO_CLASS.keys())}")
        sys.exit(1)

    # Télécharger le logo
    print("\n" + "-" * 60)
    logo_path = download_logo(logo_url, company_name, LOGOS_DIR)

    if not logo_path:
        print("✗ Impossible de télécharger le logo")
        sys.exit(1)

    # Ajouter l'entreprise au fichier Excel
    print("\n" + "-" * 60)
    print("Ajout de l'entreprise au fichier Excel...")

    success = add_company_to_excel(
        company_name=company_name,
        fonction_nist=fonction_nist,
        taille=taille,
        logo_path=logo_path,
        description=description,
        sous_fonctions_nist=sous_fonctions_nist,
        objectif_nis2=objectif_nis2
    )

    if not success:
        print("✗ Erreur lors de l'ajout de l'entreprise")
        sys.exit(1)

    # Exporter les variables pour GitHub Actions
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"company_name={company_name}\n")
            f.write(f"fonction_nist={fonction_nist}\n")
            f.write(f"taille={taille}\n")

    print("\n" + "=" * 60)
    print("✅ ENTREPRISE AJOUTÉE AVEC SUCCÈS")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
