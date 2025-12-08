#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas as pd
import glob
import os
import re
import sys
from pathlib import Path

# S'assurer que le rÃ©pertoire racine est dans sys.path pour les import internes
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import config

def normalize_solution_name(name):
    """Normalise le nom de la solution pour correspondre aux fichiers de logos."""
    # Retirer le contenu entre parenthèses
    name = re.sub(r'\([^)]*\)', '', name).strip()
    # Retirer les espaces multiples
    name = re.sub(r'\s+', ' ', name)
    return name

def find_logo_for_solution(solution_name, logos_dir=config.LOGOS_DIR):
    """Trouve le fichier logo correspondant à une solution."""
    # Normaliser le nom
    normalized = normalize_solution_name(solution_name)

    # Lister tous les logos disponibles
    all_logos = []
    for ext in ['png', 'svg', 'webp', 'jpg', 'jpeg']:
        all_logos.extend(glob.glob(f'{logos_dir}/*.{ext}'))

    # Essayer plusieurs patterns de correspondance
    patterns = [
        solution_name,  # Nom complet
        normalized,     # Nom normalisé
        solution_name.split('(')[0].strip(),  # Avant la parenthèse
        solution_name.split()[0]  # Premier mot
    ]

    for pattern in patterns:
        for logo_path in all_logos:
            logo_basename = os.path.basename(logo_path)
            # Retirer l'extension et le suffixe _01, _02, etc.
            logo_name = re.sub(r'_\d+\.(png|svg|webp|jpg|jpeg)$', '', logo_basename, flags=re.IGNORECASE)

            if logo_name.lower() == pattern.lower():
                return logo_path
            if pattern.lower() in logo_name.lower():
                return logo_path

    return None

def parse_fonction_nist(fonction_str):
    """Parse la colonne Fonction NIST qui peut avoir plusieurs formats."""
    # Nettoyer les espaces et caractères spéciaux
    fonction_str = str(fonction_str).strip()

    # Séparer par différents délimiteurs
    separators = [',', ';', '\n']
    fonctions = [fonction_str]

    for sep in separators:
        new_fonctions = []
        for f in fonctions:
            new_fonctions.extend([x.strip() for x in f.split(sep) if x.strip()])
        fonctions = new_fonctions

    # Nettoyer les résultats
    cleaned = []
    for f in fonctions:
        f = f.strip()
        if f and f not in cleaned:
            cleaned.append(f)

    return cleaned

def load_solutions_mapping(excel_path=config.EXCEL_FILE):
    """
    Charge le mapping entre solutions, quartiers et tailles.

    Returns:
        dict: {
            quartier_class: {
                'large': [logo_paths],
                'medium': [logo_paths],
                'small': [logo_paths]
            }
        }
    """
    # Mapping des fonctions NIST vers les classes CSS du SVG
    fonction_to_class = config.FONCTION_TO_CLASS

    # Mapping des tailles (0=very_large, 1=large, 2=medium, 3=small selon l'utilisateur)
    taille_to_size = config.TAILLE_TO_SIZE

    # Structure de données résultante
    solutions_by_quartier = {}
    for cls in fonction_to_class.values():
        solutions_by_quartier[cls] = {
            'very_large': [],
            'large': [],
            'medium': [],
            'small': []
        }

    # Lire le fichier Excel
    df = pd.read_excel(excel_path)

    print(f"\nChargement de {len(df)} solutions depuis {excel_path}")

    logos_found = 0
    logos_not_found = []
    multiple_quartiers = []

    # Parcourir les lignes
    for idx, row in df.iterrows():
        solution_name = row['Solutions']
        fonction_nist = row['Fonction NIST']
        taille_num = int(row['Taille'])

        # Parser les fonctions (peut y en avoir plusieurs)
        fonctions = parse_fonction_nist(fonction_nist)

        # Obtenir la taille
        size = taille_to_size.get(taille_num, 'medium')

        # Chercher le logo - priorite a la colonne Logo dans Excel
        logo_path = None
        if 'Logo' in row and pd.notna(row['Logo']) and row['Logo']:
            # Si la colonne Logo existe et contient une valeur
            logo_filename = str(row['Logo']).strip()
            potential_path = os.path.join(config.LOGOS_DIR, logo_filename)
            if os.path.exists(potential_path):
                logo_path = potential_path
            else:
                print(f"[!] Logo specifie '{logo_filename}' non trouve pour {solution_name}, recherche par nom...")

        # Si pas de logo trouve via la colonne Logo, chercher par nom de solution (fallback)
        if not logo_path:
            logo_path = find_logo_for_solution(solution_name)

        if logo_path:
            logos_found += 1
            if fonctions:
                fonction = fonctions[0]
                quartier_class = fonction_to_class.get(fonction)
                if quartier_class:
                    solutions_by_quartier[quartier_class][size].append(logo_path)
                    if len(fonctions) > 1:
                        multiple_quartiers.append(solution_name)
        else:
            logos_not_found.append(solution_name)

    print(f"> {logos_found} logos trouves")
    print(f"> {len(logos_not_found)} logos non trouves")

    if logos_not_found[:5]:
        print()
        print("Exemples de logos non trouves:")
        for name in logos_not_found[:5]:
            print(f"  - {name}")

    if multiple_quartiers[:3]:
        print()
        print("Exemples de solutions multi-quartiers (seul le 1er quartier est utilise):")
        for name in set(multiple_quartiers[:3]):
            print(f"  - {name}")

    # Afficher le resume par quartier
    print()
    print("=== Repartition par quartier ===")
    quartiers_names = {cls: f"{info['nom']} ({info['couleur']})" for cls, info in config.QUARTIERS.items()}

    for cls, quartier_name in quartiers_names.items():
        very_large_count = len(solutions_by_quartier[cls]['very_large'])
        large_count = len(solutions_by_quartier[cls]['large'])
        medium_count = len(solutions_by_quartier[cls]['medium'])
        small_count = len(solutions_by_quartier[cls]['small'])
        total = very_large_count + large_count + medium_count + small_count
        print(f"{quartier_name}: {total} logos")
        if very_large_count > 0:
            print(f"  very_large: {very_large_count}")
        if large_count > 0:
            print(f"  large: {large_count}")
        if medium_count > 0:
            print(f"  medium: {medium_count}")
        if small_count > 0:
            print(f"  small: {small_count}")

    return solutions_by_quartier

if __name__ == '__main__':
    solutions = load_solutions_mapping()
