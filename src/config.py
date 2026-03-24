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
HEXATRUST_ONLY = os.environ.get('HEXATRUST_ONLY', '0') == '1'

if HEXATRUST_ONLY:
    EXCEL_FILE = os.path.join(ASSETS_DIR, 'solutions_hexatrust.xlsx')
    INPUT_SVG = os.path.join(MASK_DIR, 'HEXATRUST_RADAR-HEXAGONE_V5-ombre.svg')
    OUTPUT_SVG = os.path.join(ASSETS_DIR, 'Panorama_cyber_Hexatrust.svg')
    OUTPUT_PNG = os.path.join(ASSETS_DIR, 'Panorama_cyber_Hexatrust.png')
    MASK_PREFIX = 'Hexatrust_Radar_mask_no_center'
else:
    EXCEL_FILE = os.path.join(ASSETS_DIR, 'solutions.xlsx')
    INPUT_SVG = os.path.join(MASK_DIR, 'RADAR-HEXAGONE_V5-ombre.svg')
    OUTPUT_SVG = os.path.join(ASSETS_DIR, 'Panorama_cyber.svg')
    OUTPUT_PNG = os.path.join(ASSETS_DIR, 'Panorama_cyber.png')
    MASK_PREFIX = 'Radar_mask_no_center'

RAPPORT_CSV = os.path.join(RAPPORT_DIR, 'rapport_logos_places.csv')

# Mapping des fonctions NIST vers les classes CSS du SVG de fond
if HEXATRUST_ONLY:
    FONCTION_TO_CLASS = {
        'Prot\u00e9ger':   'st12',
        'Identifier': 'st0',
        'Gouverner':  'st2',
        'R\u00e9cup\u00e9rer':  'st11',
        'R\u00e9pondre':   'st5',
        'D\u00e9tecter':   'st3',
    }
    QUARTIERS = {
        'st12': {'nom': 'Prot\u00e9ger',   'couleur': 'Violet'},
        'st0':  {'nom': 'Identifier', 'couleur': 'Bleu'},
        'st2':  {'nom': 'Gouverner',  'couleur': 'Jaune'},
        'st5':  {'nom': 'R\u00e9pondre',   'couleur': 'Rouge'},
        'st3':  {'nom': 'D\u00e9tecter',   'couleur': 'Orange'},
        'st11': {'nom': 'R\u00e9cup\u00e9rer',  'couleur': 'Vert'},
    }
else:
    FONCTION_TO_CLASS = {
        'Prot\u00e9ger':   'st9',
        'Identifier': 'st2',
        'Gouverner':  'st12',
        'R\u00e9cup\u00e9rer':  'st7',
        'R\u00e9pondre':   'st11',
        'D\u00e9tecter':   'st0',
    }
    QUARTIERS = {
        'st9':  {'nom': 'Prot\u00e9ger',   'couleur': 'Violet'},
        'st2':  {'nom': 'Identifier', 'couleur': 'Bleu'},
        'st12': {'nom': 'Gouverner',  'couleur': 'Jaune'},
        'st11': {'nom': 'R\u00e9pondre',   'couleur': 'Rouge'},
        'st0':  {'nom': 'D\u00e9tecter',   'couleur': 'Orange'},
        'st7':  {'nom': 'R\u00e9cup\u00e9rer',  'couleur': 'Vert'},
    }

# Mapping des tailles (0=very_large, 1=large, 2=medium, 3=small)
TAILLE_TO_SIZE = {
    0: 'very_large',
    1: 'large',
    2: 'medium',
    3: 'small'
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
