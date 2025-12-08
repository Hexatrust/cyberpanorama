#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration centralisée pour le projet Radar Hexatrust
"""
import os

# Chemins des fichiers
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Project root
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
LOGOS_DIR = os.path.join(ASSETS_DIR, 'logos')
MASK_DIR = os.path.join(ASSETS_DIR, 'Mask')
SRC_DIR = os.path.join(BASE_DIR, 'src')
DOCS_DIR = os.path.join(BASE_DIR, 'docs')
TESTS_DIR = os.path.join(BASE_DIR, 'tests')
RAPPORT_DIR = os.path.join(ASSETS_DIR, 'Report')

# Fichiers principaux
EXCEL_FILE = os.path.join(ASSETS_DIR, 'solutions.xlsx')
INPUT_SVG = os.path.join(MASK_DIR, 'Radar_Hexatrust_Cesin.svg')
OUTPUT_SVG = os.path.join(ASSETS_DIR, 'Panorama_cyber.svg')
OUTPUT_PNG = os.path.join(ASSETS_DIR, 'Panorama_cyber.png')
RAPPORT_CSV = os.path.join(RAPPORT_DIR, 'rapport_logos_places.csv')

# Mapping des fonctions NIST vers les classes CSS du NOUVEAU SVG
FONCTION_TO_CLASS = {
    'Prot\u00e9ger':   'st3',
    'Identifier': 'st11',
    'Gouverner':  'st5',
    'R\u00e9cup\u00e9rer':  'st12',
    'R\u00e9pondre':   'st7',
    'D\u00e9tecter':   'st10',
}

# Mapping des tailles (0=very_large, 1=large, 2=medium, 3=small)
TAILLE_TO_SIZE = {
    0: 'very_large',
    1: 'large',
    2: 'medium',
    3: 'small'
}

# Noms complets des quartiers
QUARTIERS = {
    'st3':  {'nom': 'Prot\u00e9ger',   'couleur': 'Violet'},
    'st11': {'nom': 'Identifier', 'couleur': 'Bleu'},
    'st5':  {'nom': 'Gouverner',  'couleur': 'Jaune'},
    'st7':  {'nom': 'R\u00e9pondre',   'couleur': 'Rouge'},
    'st10': {'nom': 'D\u00e9tecter',   'couleur': 'Orange'},
    'st12': {'nom': 'R\u00e9cup\u00e9rer',  'couleur': 'Vert'},
}

# Tailles des rectangles sur le radar
RECTANGLE_SIZES = {
    'small': {'width': 30, 'height': 12},
    'medium': {'width': 42, 'height': 16},
    'large': {'width': 56, 'height': 21},
    'very_large': {'width': 70, 'height': 26},
}

# Paramètres de placement
GAP_PX = 1  # Espacement entre les logos
SCALE = 2   # Échelle pour la rastérisation

# Extensions de fichiers acceptées pour les logos
LOGO_EXTENSIONS = ['png', 'svg', 'webp', 'jpg', 'jpeg']

# Configuration Flask
FLASK_PORT = 5000
FLASK_DEBUG = True
FLASK_HOST = '0.0.0.0'

# Dossiers de téléchargement
UPLOAD_FOLDER = LOGOS_DIR
MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg', 'webp'}
