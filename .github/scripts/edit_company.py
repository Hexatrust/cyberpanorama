#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour modifier une entreprise existante dans le radar
"""
import os
import sys
import re
import requests
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import FONCTION_TO_CLASS, EXCEL_FILE, LOGOS_DIR


def download_logo(url, company_name, logos_dir='assets/logos'):
    """Télécharge le logo depuis une URL"""
    try:
        print(f"Téléchargement du nouveau logo depuis: {url}")

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

        print(f"✓ Nouveau logo sauvegardé: {filepath}")
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
        'company_name': r"###\s*🏢\s*Nom\s+de\s+l[''']entreprise\s+à\s+modifier\s*\n+\s*([^\n]+)",
        'modification_type': r'###\s*🔧\s*Type\s+de\s+modification\s*\n+\s*([^\n]+)',
        'new_logo_url': r'###\s*🖼️\s*Nouvelle\s+URL\s+du\s+logo\s*\(optionnel\)\s*\n+\s*([^\n]+)',
        'new_fonction_nist': r'###\s*🎯\s*Nouvelle\s+Fonction\s+NIST\s*\(optionnel\)\s*\n+\s*([^\n]+)',
        'new_objectif_nis2': r'###\s*🛡️\s*Nouvel\s+objectif\s+NIS2\s*\(optionnel\)\s*\n+\s*([^\n]+)',
        'new_taille': r"###\s*📏\s*Nouvelle\s+taille\s+de\s+l[''']entreprise\s*\(optionnel\)\s*\n+\s*([^\n]+)",
        'new_description': r'###\s*📝\s*Nouvelle\s+description\s*\(optionnel\)\s*\n+\s*(.+?)(?=\n###|\Z)',
        'new_website': r'###\s*🌐\s*Nouveau\s+site\s+web\s*\(optionnel\)\s*\n+\s*([^\n]+)',
        'reason': r'###\s*💬\s*Raison\s+de\s+la\s+modification\s*\n+\s*(.+?)(?=\n###|\Z)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            # Liste des valeurs à ignorer (ne pas modifier)
            ignore_values = [
                '',
                '_No response_',
                'N/A',
                'None',
                '(Ne pas modifier)',
                '(Aucun)',
                'null',
                'undefined'
            ]
            # Nettoyer les valeurs - ignorer si vide ou valeur à ne pas modifier
            if value and value not in ignore_values:
                data[key] = value
                print(f"  [DEBUG] Trouvé {key}: {value[:80]}...")
            else:
                print(f"  [DEBUG] Valeur ignorée pour {key}: '{value}'")
        else:
            print(f"  [DEBUG] Pattern non trouvé pour: {key}")

    # Parser les sous-fonctions NIST (checkboxes)
    sous_fonctions_section = re.search(
        r'###\s*🔍\s*Nouvelles\s+sous-fonctions\s+NIST\s+CSF\s+2\.0\s*\(optionnel,\s*max\s+3\)\s*\n(.*?)(?=\n###|\Z)',
        body,
        re.MULTILINE | re.DOTALL
    )
    if sous_fonctions_section:
        # Extraire les checkboxes cochées (contiennent [X] ou [x])
        checked_items = re.findall(r'-\s+\[x\]\s+(.+)', sous_fonctions_section.group(1), re.IGNORECASE)
        if checked_items:
            # Extraire seulement les codes (ex: "GV.OC")
            codes = [item.split(' - ')[0].strip() for item in checked_items[:3]]  # Max 3
            data['new_sous_fonctions_nist'] = ', '.join(codes)
            print(f"  [DEBUG] Trouvé new_sous_fonctions_nist: {', '.join(codes)}")
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
    return None


def update_company_in_excel(company_name, updates):
    """Met à jour une entreprise dans le fichier Excel"""
    try:
        # Charger le fichier Excel
        df = pd.read_excel(EXCEL_FILE)

        # Trouver l'entreprise
        company_idx = df[df['Solutions'] == company_name].index

        if len(company_idx) == 0:
            print(f"⚠️  L'entreprise '{company_name}' n'a pas été trouvée dans le fichier Excel")
            return False

        if len(company_idx) > 1:
            print(f"⚠️  Plusieurs entrées trouvées pour '{company_name}', mise à jour de la première")

        idx = company_idx[0]

        # Appliquer les modifications
        modified_fields = []

        if 'fonction_nist' in updates:
            df.at[idx, 'Fonction NIST'] = updates['fonction_nist']
            modified_fields.append(f"Fonction NIST: {updates['fonction_nist']}")

        if 'taille' in updates:
            df.at[idx, 'Taille'] = updates['taille']
            modified_fields.append(f"Taille: {updates['taille']}")

        if 'logo_path' in updates:
            df.at[idx, 'Logo'] = os.path.basename(updates['logo_path'])
            modified_fields.append(f"Logo: {os.path.basename(updates['logo_path'])}")

        if 'description' in updates:
            if 'Description' in df.columns:
                df.at[idx, 'Description'] = updates['description']
                modified_fields.append("Description: (updated)")
            else:
                print("⚠️  Colonne 'Description' non trouvée dans le fichier Excel")

        if 'sous_fonctions_nist' in updates:
            if 'Sous-fonctions NIST' in df.columns:
                df.at[idx, 'Sous-fonctions NIST'] = updates['sous_fonctions_nist']
                modified_fields.append(f"Sous-fonctions NIST: {updates['sous_fonctions_nist']}")
            else:
                print("⚠️  Colonne 'Sous-fonctions NIST' non trouvée dans le fichier Excel")

        if 'objectif_nis2' in updates:
            if 'Objectif NIS2' in df.columns:
                df.at[idx, 'Objectif NIS2'] = updates['objectif_nis2']
                modified_fields.append(f"Objectif NIS2: {updates['objectif_nis2']}")
            else:
                print("⚠️  Colonne 'Objectif NIS2' non trouvée dans le fichier Excel")

        # Sauvegarder avec openpyxl pour préserver le formatage
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl', mode='w') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')

        print(f"✅ Entreprise '{company_name}' mise à jour avec succès")
        print(f"   Champs modifiés: {', '.join(modified_fields)}")
        return True

    except Exception as e:
        print(f"✗ Erreur lors de la mise à jour du fichier Excel: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python edit_company.py <issue_number>")
        sys.exit(1)

    issue_number = sys.argv[1]
    github_token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', 'RobinEY-prog/RADAR_HEXATRUST')

    if not github_token:
        print("✗ GITHUB_TOKEN non défini")
        sys.exit(1)

    print("=" * 60)
    print(f"MODIFICATION D'ENTREPRISE - ISSUE #{issue_number}")
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
            if key in ['new_logo_url', 'new_website']:
                print(f"  ✓ {key}: {value}")
            else:
                print(f"  ✓ {key}: {value[:150] if len(str(value)) > 150 else value}")
    else:
        print("  ⚠️  Aucune donnée extraite de l'issue")

    # Valider les données obligatoires
    if 'company_name' not in data:
        print("\n✗ Nom de l'entreprise manquant")
        print("\n💡 Vérifiez que l'issue a été créée avec le bon template:")
        print("   - Template 'Modifier une entreprise' pour une modification")
        print("   - Vérifiez que tous les champs obligatoires sont remplis")
        print("   - Assurez-vous que l'issue a le label 'radar:edit-entry'")
        sys.exit(1)

    company_name = data['company_name']
    updates = {}

    # Télécharger le nouveau logo si fourni
    if 'new_logo_url' in data:
        print("\n" + "-" * 60)
        logo_path = download_logo(data['new_logo_url'], company_name, LOGOS_DIR)
        if logo_path:
            updates['logo_path'] = logo_path
        else:
            print("⚠️  Le logo n'a pas pu être téléchargé, mais la modification continue")

    # Préparer les autres mises à jour
    if 'new_fonction_nist' in data:
        fonction = data['new_fonction_nist']
        if fonction in FONCTION_TO_CLASS:
            updates['fonction_nist'] = fonction
        else:
            print(f"⚠️  Fonction NIST invalide: {fonction}")

    if 'new_taille' in data:
        taille = extract_taille_number(data['new_taille'])
        if taille is not None:
            updates['taille'] = taille

    if 'new_description' in data:
        updates['description'] = data['new_description']

    if 'new_sous_fonctions_nist' in data:
        updates['sous_fonctions_nist'] = data['new_sous_fonctions_nist']

    if 'new_objectif_nis2' in data:
        updates['objectif_nis2'] = data['new_objectif_nis2']

    if not updates:
        print("\n⚠️  Aucune modification à appliquer")
        sys.exit(0)

    # Mettre à jour l'entreprise dans le fichier Excel
    print("\n" + "-" * 60)
    print("Mise à jour de l'entreprise dans le fichier Excel...")

    success = update_company_in_excel(company_name, updates)

    if not success:
        print("✗ Erreur lors de la mise à jour de l'entreprise")
        sys.exit(1)

    # Exporter les variables pour GitHub Actions
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"company_name={company_name}\n")
            f.write(f"modifications={', '.join(updates.keys())}\n")

    print("\n" + "=" * 60)
    print("✅ ENTREPRISE MODIFIÉE AVEC SUCCÈS")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
