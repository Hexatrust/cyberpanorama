# Update: exclude central circle/ellipse when placing rectangles by cutting a white "hole" in the mask.
from xml.etree import ElementTree as ET
import random
import base64
import mimetypes
import os
import sys
import glob
from pathlib import Path
import math
import re
import unicodedata

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config
from src.read_solutions import load_solutions_mapping
import logging
logging.getLogger('svglib.svglib').setLevel(logging.ERROR)

# Change to project root directory
os.chdir(config.BASE_DIR)


INPUT_SVG = config.INPUT_SVG
OUTPUT_SVG_SQUARES = config.OUTPUT_SVG
OUTPUT_PNG_SQUARES = config.OUTPUT_PNG
SVG_NS = "http://www.w3.org/2000/svg"
MASK_DIR = config.MASK_DIR
MASK_SVG = os.path.join(MASK_DIR, "Radar_mask_no_center.svg")
MASK_PNG = os.path.join(MASK_DIR, "Radar_mask_no_center.png")
os.makedirs(MASK_DIR, exist_ok=True)

# Optionnel : graine pour reproductibilité
random.seed(42)

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# ======= Charger les logos par quartier et taille depuis solutions.xlsx =======
print("\n" + "="*60)
print("Chargement des solutions depuis solutions.xlsx...")
print("="*60)
solutions_by_quartier = load_solutions_mapping()

# Encoder tous les logos en base64
def encode_logo_to_base64(logo_path):
    """Encode un logo en base64 data URI."""
    try:
        with open(logo_path, 'rb') as f:
            logo_bytes = f.read()
        mime_type = mimetypes.guess_type(logo_path)[0] or 'image/png'
        base64_data = base64.b64encode(logo_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        print(f"Erreur lors de l'encodage de {logo_path}: {e}")
        return None

# Encoder tous les logos
print("\nEncodage des logos en base64...")
encoded_logos_by_quartier = {}
total_encoded = 0
for quartier_cls in solutions_by_quartier:
    encoded_logos_by_quartier[quartier_cls] = {
        'very_large': [],
        'large': [],
        'medium': [],
        'small': []
    }
    for size in ['very_large', 'large', 'medium', 'small']:
        for logo_path in solutions_by_quartier[quartier_cls][size]:
            data_uri = encode_logo_to_base64(logo_path)
            if data_uri:
                encoded_logos_by_quartier[quartier_cls][size].append({
                    'path': logo_path,
                    'data_uri': data_uri,
                    'name': os.path.basename(logo_path)
                })
                total_encoded += 1

print(f"> {total_encoded} logos encodes avec succes\n")
def q(tag): return f"{{{SVG_NS}}}{tag}"

# Les classes reellement utilisees pour tes quartiers dans le NOUVEAU SVG
QUARTIERS = config.QUARTIERS
TARGET_CLASSES = set(QUARTIERS.keys())

# Parameters - compute rectangle sizes so that:
#  - area(small) = baseline
#  - area(medium) = area(small) * 2   (+100% than small)
#  - area(large)  = area(small) * 3   (+200% than small)
#  - area(very_large) = area(small) * 4 (+300% than small)
# This ensures small is exactly 1/4 of very_large (area-wise).
# We preserve the aspect ratio of the previous small size (27x11) as a baseline.
BASE_SMALL = {'width': 33, 'height': 10}
ratio = BASE_SMALL['width'] / BASE_SMALL['height']
area_small = BASE_SMALL['width'] * BASE_SMALL['height']

mults = {
    'small': 1,
    'medium': 2,
    'large': 3,
    'very_large': 4
}

RECTANGLE_SIZES = {}
for size_name, m in mults.items():
    target_area = area_small * m
    # height = sqrt(area / ratio), then width = round(ratio * height)
    h = int(round(math.sqrt(target_area / ratio)))
    w = int(round(ratio * h))
    # Ensure minimums (avoid zero)
    h = max(1, h)
    w = max(1, w)
    RECTANGLE_SIZES[size_name] = {'width': w, 'height': h}

# For visibility, print computed sizes (helps debugging)
print("RECTANGLE_SIZES computed (area-based):")
for k in ['small', 'medium', 'large', 'very_large']:
    w = RECTANGLE_SIZES[k]['width']
    h = RECTANGLE_SIZES[k]['height']
    print(f"  - {k}: {w}x{h} (area={w*h})")

GAP_PX = 1  # Espacement minimal
SCALE = 2

# Parse original SVG
tree = ET.parse(INPUT_SVG)
root = tree.getroot()

viewBox = root.get("viewBox")
if viewBox:
    vx, vy, vw, vh = [float(x) for x in viewBox.strip().split()]
else:
    def to_float(val, default=1000):
        if val is None: return default
        m = re.match(r"([\d.]+)", val)
        return float(m.group(1)) if m else default
    vx, vy = 0.0 , 0.0
    vw, vh = to_float(root.get("width")), to_float(root.get("height"))

# Collect shapes (paths, polygons, ellipses, cercles) WITH their class
TARGET_SHAPE_TAGS = ["path", "polygon", "circle", "ellipse"]

def build_shape_element(tag, attrib, fill_color):
    """Create an SVG element for a shape with the desired fill color."""
    base_attrib = {"fill": fill_color, "stroke": "none"}

    if tag == "path":
        base_attrib["d"] = attrib.get("d")
    elif tag == "polygon":
        base_attrib["points"] = attrib.get("points", "")
    elif tag == "circle":
        base_attrib.update({
            "cx": attrib.get("cx", "0"),
            "cy": attrib.get("cy", "0"),
            "r": attrib.get("r", "0"),
        })
    elif tag == "ellipse":
        base_attrib.update({
            "cx": attrib.get("cx", "0"),
            "cy": attrib.get("cy", "0"),
            "rx": attrib.get("rx", "0"),
            "ry": attrib.get("ry", "0"),
        })

    if "transform" in attrib:
        base_attrib["transform"] = attrib["transform"]

    return ET.Element(q(tag), attrib=base_attrib)

shapes_with_class = []
for tag in TARGET_SHAPE_TAGS:
    for el in root.findall(f".//{q(tag)}"):
        cls_attr = el.get("class") or ""
        classes = set(cls_attr.split())
        matching_class = classes & TARGET_CLASSES
        if matching_class:
            cls = list(matching_class)[0]
            shapes_with_class.append((tag, cls, dict(el.attrib)))

if not shapes_with_class:
    print("[!] Aucune forme de quartier detectee dans le SVG source")

def extract_font_sizes_from_style(svg_root):
    """Extract font-size by CSS class from <style> blocks."""
    font_sizes = {}
    for style in svg_root.findall(f".//{q('style')}"):
        css_text = "".join(style.itertext())
        for cls_name, body in re.findall(r"\.(st[\w-]+)\s*\{([^}]*)\}", css_text, flags=re.DOTALL):
            match = re.search(r"font-size\s*:\s*([\d.]+)px", body)
            if match:
                font_sizes[cls_name] = float(match.group(1))
    return font_sizes

def parse_translate(transform):
    """Parse translate(x y) from an SVG transform string."""
    if not transform:
        return None
    match = re.search(r"translate\(\s*([-\d.]+)(?:[ ,]+([-\d.]+))?\s*\)", transform)
    if not match:
        return None
    tx = float(match.group(1))
    ty = float(match.group(2) or 0.0)
    return tx, ty

def collect_text_exclusion_rects(svg_root):
    """Build keep-out rectangles around labels to avoid logo/text overlap."""
    font_sizes = extract_font_sizes_from_style(svg_root)
    exclusion_rects = []
    category_labels = {
        re.sub(r"\s+", " ", unicodedata.normalize("NFKD", info['nom']).encode("ascii", "ignore").decode("ascii")).strip().upper()
        for info in QUARTIERS.values()
    }

    for text_el in svg_root.findall(f".//{q('text')}"):
        classes = (text_el.get("class") or "").split()
        font_size = 37.0
        for cls in classes:
            if cls in font_sizes:
                font_size = font_sizes[cls]
                break

        position = parse_translate(text_el.get("transform"))
        if position is None:
            x_attr = text_el.get("x")
            y_attr = text_el.get("y")
            if x_attr is None or y_attr is None:
                continue
            try:
                position = (float(x_attr), float(y_attr))
            except ValueError:
                continue

        x, y = position

        text_parts = []
        tspans = text_el.findall(f".//{q('tspan')}")
        if tspans:
            for tspan in tspans:
                value = "".join(tspan.itertext()).strip()
                if value:
                    text_parts.append(value)
        else:
            value = "".join(text_el.itertext()).strip()
            if value:
                text_parts.append(value)

        if not text_parts:
            continue

        label = " ".join(text_parts)
        normalized_label = re.sub(
            r"\s+", " ",
            unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
        ).strip().upper()

        # Les libelles de categories sont deja geres via la contrainte "sous le texte".
        # On n'ajoute pas de zone blanche ici pour eviter de creer des "trous" dans les quartiers.
        if normalized_label in category_labels:
            continue

        if normalized_label == "CYBERPANORAMA BY":
            padding = max(8.0, font_size * 0.18)
            estimated_width = (font_size * 0.58 * len(label)) + (padding * 2)
            estimated_height = (font_size * 1.20) + (padding * 2)
        else:
            padding = max(22.0, font_size * 0.55)
            estimated_width = (font_size * 0.82 * len(label)) + (padding * 2)
            estimated_height = (font_size * 1.6) + (padding * 2)

        exclusion_rects.append({
            "x": x - padding,
            "y": y - (font_size * 1.15) - padding,
            "width": estimated_width,
            "height": estimated_height,
            "label": label,
        })

    return exclusion_rects

def normalize_label_key(value):
    """Normalise un libelle pour faire des comparaisons robustes."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value).strip().upper()

def collect_category_label_constraints(svg_root):
    """Retourne, par quartier CSS, une contrainte locale autour du libelle de categorie."""
    font_sizes = extract_font_sizes_from_style(svg_root)

    normalized_quartiers = {
        normalize_label_key(info['nom']): cls
        for cls, info in QUARTIERS.items()
    }

    category_constraints = {}
    for text_el in svg_root.findall(f".//{q('text')}"):
        position = parse_translate(text_el.get("transform"))
        if position is None:
            continue

        classes = (text_el.get("class") or "").split()
        font_size = 37.0
        for cls_name in classes:
            if cls_name in font_sizes:
                font_size = font_sizes[cls_name]
                break

        text_parts = []
        tspans = text_el.findall(f".//{q('tspan')}")
        if tspans:
            for tspan in tspans:
                value = "".join(tspan.itertext()).strip()
                if value:
                    text_parts.append(value)
        else:
            value = "".join(text_el.itertext()).strip()
            if value:
                text_parts.append(value)

        if not text_parts:
            continue

        normalized_label = normalize_label_key(" ".join(text_parts))
        matched_quartier_cls = None
        for quartier_name, quartier_cls in normalized_quartiers.items():
            if quartier_name and quartier_name in normalized_label:
                matched_quartier_cls = quartier_cls
                break

        if matched_quartier_cls is None:
            continue

        label = " ".join(text_parts)
        x, y = position

        width_factor = 0.92
        padding_factor = 0.26
        min_y_factor = 0.68

        text_width_svg = (font_size * width_factor * len(label))
        padding_x_svg = max(2.0, font_size * padding_factor)

        left_svg = x - padding_x_svg
        right_svg = x + text_width_svg + padding_x_svg
        min_y_svg = y + (font_size * min_y_factor) + 4.0

        existing = category_constraints.get(matched_quartier_cls)
        if existing is None:
            category_constraints[matched_quartier_cls] = {
                'x_left': left_svg,
                'x_right': right_svg,
                'min_y': min_y_svg,
            }
        else:
            existing['x_left'] = min(existing['x_left'], left_svg)
            existing['x_right'] = max(existing['x_right'], right_svg)
            existing['min_y'] = max(existing['min_y'], min_y_svg)

    return category_constraints

# Detect center ellipse/circle (choose the smallest candidate)
center_candidates = []
for el in root.iter():
    tag = el.tag.split('}')[-1]
    if tag == "ellipse":
        try:
            cx = float(el.get("cx","0")); cy = float(el.get("cy","0"))
            rx = float(el.get("rx","0") or 0); ry = float(el.get("ry","0") or 0)
        except:
            continue
        # Heuristic range for center
        if 40 <= rx <= 200 and 40 <= ry <= 200:
            center_candidates.append(("ellipse", cx, cy, rx, ry))
    elif tag == "circle":
        try:
            cx = float(el.get("cx","0")); cy = float(el.get("cy","0"))
            r = float(el.get("r","0") or 0)
        except:
            continue
        if 40 <= r <= 200:
            center_candidates.append(("circle", cx, cy, r, r))

center = None
if center_candidates:
    center = min(center_candidates, key=lambda c: c[3] * c[4])

# Build mask SVG (black wedges, then white center "hole")
mask_svg = ET.Element(q("svg"), attrib={
    "viewBox": f"{vx} {vy} {vw} {vh}",
    "width": str(int(vw)),
    "height": str(int(vh)),
})
mask_svg.append(ET.Element(q("rect"), attrib={
    "x": str(vx), "y": str(vy), "width": str(vw), "height": str(vh),
    "fill": "white"
}))
for tag, cls, attrib in shapes_with_class:
    mask_svg.append(build_shape_element(tag, attrib, "black"))

# Add white hole for center
if center:
    kind, cx, cy, rx, ry = center
    if kind == "ellipse":
        mask_svg.append(ET.Element(q("ellipse"), attrib={
            "cx": str(cx), "cy": str(cy), "rx": str(rx), "ry": str(ry),
            "fill": "white", "stroke": "none"
        }))
    else:
        mask_svg.append(ET.Element(q("circle"), attrib={
            "cx": str(cx), "cy": str(cy), "r": str(rx),  # rx==ry here
            "fill": "white", "stroke": "none"
        }))

text_exclusion_rects = collect_text_exclusion_rects(root)
for rect in text_exclusion_rects:
    mask_svg.append(ET.Element(q("rect"), attrib={
        "x": str(rect["x"]),
        "y": str(rect["y"]),
        "width": str(rect["width"]),
        "height": str(rect["height"]),
        "fill": "white",
        "stroke": "none",
    }))

print(f"> Zones d'exclusion texte detectees: {len(text_exclusion_rects)}")

mask_tree = ET.ElementTree(mask_svg)
mask_tree.write(MASK_SVG, encoding="utf-8", xml_declaration=True)

# Rasterize mask using svglib + reportlab
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM

target_width = max(1, int(vw * SCALE))
target_height = max(1, int(vh * SCALE))

# Convert mask SVG to PNG
drawing = svg2rlg(MASK_SVG)
renderPM.drawToFile(drawing, MASK_PNG, fmt="PNG", dpi=72*SCALE)

# Créer un masque par quartier pour identifier l'appartenance
from PIL import Image

quartier_masks = {}
for tag, cls, attrib in shapes_with_class:
    # Creer un masque temporaire pour ce quartier
    temp_svg = ET.Element(q("svg"), attrib={
        "viewBox": f"{vx} {vy} {vw} {vh}",
        "width": str(int(vw)),
        "height": str(int(vh)),
    })
    temp_svg.append(ET.Element(q("rect"), attrib={
        "x": str(vx), "y": str(vy), "width": str(vw), "height": str(vh),
        "fill": "white"
    }))
    temp_svg.append(build_shape_element(tag, attrib, "black"))


    # Sauvegarder et rasteriser
    temp_svg_path = f"temp_quartier_{cls}.svg"
    temp_png_path = f"temp_quartier_{cls}.png"
    ET.ElementTree(temp_svg).write(temp_svg_path, encoding="utf-8", xml_declaration=True)

    drawing_temp = svg2rlg(temp_svg_path)
    renderPM.drawToFile(drawing_temp, temp_png_path, fmt="PNG", dpi=72*SCALE)

    quartier_masks[cls] = Image.open(temp_png_path).convert("L")

def compute_mask_black_area(mask_image):
    """Compte le nombre de pixels noirs (zone autorisee)."""
    pixels = mask_image.load()
    width, height = mask_image.size
    black_count = 0
    for yy in range(height):
        for xx in range(width):
            if pixels[xx, yy] < 128:
                black_count += 1
    return black_count

def compute_quartier_scale_factors():
    """Calcule un facteur d'agrandissement par quartier selon la densite attendue."""
    target_density = 0.55
    max_scale = 3.20
    scale_factors = {}

    for cls in QUARTIERS.keys():
        mask = quartier_masks.get(cls)
        if mask is None:
            scale_factors[cls] = 1.0
            continue

        quartier_area = compute_mask_black_area(mask)
        if quartier_area <= 0:
            scale_factors[cls] = 1.0
            continue

        planned_logo_area = 0
        for size_name, size in RECTANGLE_SIZES.items():
            logo_count = len(encoded_logos_by_quartier[cls][size_name])
            planned_logo_area += logo_count * size['width'] * size['height']

        if planned_logo_area <= 0:
            scale_factors[cls] = 1.0
            continue

        density = planned_logo_area / quartier_area
        if density < target_density:
            scale = math.sqrt(target_density / max(density, 1e-9))
            scale_factors[cls] = min(max_scale, max(1.0, scale))
        else:
            scale_factors[cls] = 1.0

    return scale_factors

QUARTIER_SCALE_FACTORS = compute_quartier_scale_factors()
print("Facteurs d'agrandissement par quartier:")
for cls, factor in QUARTIER_SCALE_FACTORS.items():
    info = QUARTIERS[cls]
    print(f"  - {info['nom']}: x{factor:.2f}")

# Load mask and place rectangles
mask_img = Image.open(MASK_PNG).convert("L")
W, H = mask_img.size
mask_pixels = mask_img.load()

category_label_constraints_svg = collect_category_label_constraints(root)
CATEGORY_LABEL_BLOCKS = {}
for cls, constraint in category_label_constraints_svg.items():
    left_px = int(round(((constraint['x_left'] - vx) / vw) * W)) if vw else 0
    right_px = int(round(((constraint['x_right'] - vx) / vw) * W)) if vw else W - 1
    min_y_px = int(round(((constraint['min_y'] - vy) / vh) * H)) if vh else 0

    CATEGORY_LABEL_BLOCKS[cls] = {
        'x_left_px': max(0, min(W - 1, left_px)),
        'x_right_px': max(0, min(W - 1, right_px)),
        'min_y_px': max(0, min(H - 1, min_y_px)),
    }

print("Contraintes locales sous libelles (pixels):")
for cls in QUARTIERS.keys():
    if cls in CATEGORY_LABEL_BLOCKS:
        info = QUARTIERS[cls]
        block = CATEGORY_LABEL_BLOCKS[cls]
        print(f"  - {info['nom']}: x=[{block['x_left_px']},{block['x_right_px']}], y>={block['min_y_px']}")

def is_rectangle_inside(x, y, width, height):
    """Vérifie si un rectangle rentre dans le masque (noir = autorisé)."""
    for yy in range(y, y + height):
        for xx in range(x, x + width):
            if xx < 0 or yy < 0 or xx >= W or yy >= H:
                return False
            if mask_pixels[xx, yy] >= 128:  # blanc = hors masque ou trou central
                return False
    return True

def is_space_occupied(x, y, width, height, occupied_pixels):
    """Vérifie si l'espace (avec gap) est libre."""
    for yy in range(y, y + height + GAP_PX):
        for xx in range(x, x + width + GAP_PX):
            if (xx, yy) in occupied_pixels:
                return True
    return False

def rect_size_for_quartier(size_name, target_quartier_cls):
    """Renvoie la taille du rectangle pour un quartier donne."""
    base = RECTANGLE_SIZES[size_name]
    factor = QUARTIER_SCALE_FACTORS.get(target_quartier_cls, 1.0)
    return {
        'width': max(1, int(round(base['width'] * factor))),
        'height': max(1, int(round(base['height'] * factor))),
    }


def min_distance_to_existing(cx, cy, target_quartier_cls):
    """Distance (au carre) vers le logo le plus proche deja place dans ce quartier."""
    best = None
    for (px, py, _size_name, w, h, cls, _info, _logo) in placed:
        if cls != target_quartier_cls:
            continue
        pcx = px + w / 2
        pcy = py + h / 2
        dist2 = (cx - pcx) ** 2 + (cy - pcy) ** 2
        if best is None or dist2 < best:
            best = dist2
    return best


def get_quartier(x, y, width, height):
    """Détermine le quartier d'un rectangle en testant son centre."""
    center_x = x + width // 2
    center_y = y + height // 2

    for cls, mask in quartier_masks.items():
        pixels = mask.load()
        if center_x < mask.size[0] and center_y < mask.size[1]:
            if pixels[center_x, center_y] < 128:  # noir = dans le quartier
                return cls, QUARTIERS[cls]
    return None, None

# ======= NOUVEAU : placement par quotas =======
# Grille de positions de base (pas = plus petite hauteur + GAP)
min_height = min(rect['height'] for rect in RECTANGLE_SIZES.values())
step = min_height + GAP_PX

grid_positions = [(x, y) for y in range(0, H, step) for x in range(0, W, step)]

placed = []
occupied_pixels = set()
quartier_stats = {cls: 0 for cls in QUARTIERS.keys()}
size_counts_by_quartier = {}
for cls in QUARTIERS.keys():
    size_counts_by_quartier[cls] = {'very_large': 0, 'large': 0, 'medium': 0, 'small': 0}

def try_place_logo(size_name, target_quartier_cls, logo_data, max_positions=3500):
    """Essaie de placer 1 logo d'une taille donnee dans un quartier specifique."""
    base_size = RECTANGLE_SIZES[size_name]
    requested_factor = QUARTIER_SCALE_FACTORS.get(target_quartier_cls, 1.0)
    factor_steps = []
    for ratio in [1.00, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64, 0.58, 0.52]:
        candidate = max(1.0, requested_factor * ratio)
        factor_steps.append(round(candidate, 3))
    factor_steps.append(1.0)
    factor_steps = list(dict.fromkeys(factor_steps))

    label_block = CATEGORY_LABEL_BLOCKS.get(target_quartier_cls)

    search_budget = max_positions
    if target_quartier_cls == 'st2':
        search_budget = min(len(grid_positions), max_positions * 5)

    for factor in factor_steps:
        width_px = max(1, int(round(base_size['width'] * factor)))
        height_px = max(1, int(round(base_size['height'] * factor)))

        # On parcourt la grille en ordre aleatoire (limite a max_positions pour plus de rapidite)
        positions = grid_positions[:]
        random.shuffle(positions)
        positions = positions[:search_budget]  # Limiter le nombre de positions testees

        best_candidate = None
        best_score = -1

        for (x, y) in positions:
            if not is_rectangle_inside(x, y, width_px, height_px):
                continue
            if is_space_occupied(x, y, width_px, height_px, occupied_pixels):
                continue

            quartier_cls, quartier_info = get_quartier(x, y, width_px, height_px)

            # CONTRAINTE : le logo doit etre place dans SON quartier
            if quartier_cls != target_quartier_cls:
                continue

            # CONTRAINTE stricte : tous les logos du quartier doivent etre sous le libelle
            if label_block is not None:
                if y < label_block['min_y_px']:
                    continue

            cx = x + width_px / 2
            cy = y + height_px / 2
            score = min_distance_to_existing(cx, cy, target_quartier_cls)
            if score is None:
                score = float("inf")

            if score > best_score:
                best_score = score
                best_candidate = (x, y, quartier_cls, quartier_info)

        if best_candidate:
            x, y, quartier_cls, quartier_info = best_candidate
            placed.append((x, y, size_name, width_px, height_px, quartier_cls, quartier_info, logo_data))
            size_counts_by_quartier[quartier_cls][size_name] += 1
            quartier_stats[quartier_cls] += 1

            # Marquer les pixels occupes (incluant le gap)
            for yy in range(y, y + height_px + GAP_PX):
                for xx in range(x, x + width_px + GAP_PX):
                    if 0 <= xx < W and 0 <= yy < H:
                        occupied_pixels.add((xx, yy))
            return True

    return False

# Placement par quartier et par taille
print("\n" + "="*60)
print("Placement des logos sur le radar...")
print("="*60)

# Ordre de remplissage : très grands -> grands -> moyens -> petits (meilleur packing)
fill_order = ['very_large', 'large', 'medium', 'small']

total_placed = 0
total_failed = 0

for quartier_cls, quartier_info in QUARTIERS.items():
    print(f"\n{quartier_info['nom']} ({quartier_info['couleur']}):", end='', flush=True)

    for size_name in fill_order:
        logos_to_place = encoded_logos_by_quartier[quartier_cls][size_name]
        target_count = len(logos_to_place)

        if target_count == 0:
            continue

        placed_count = 0
        max_attempts_per_logo = 140  # Maximum de tentatives pour placer TOUS les logos

        for idx, logo_data in enumerate(logos_to_place):
            # Afficher le progres tous les 10 logos
            if idx > 0 and idx % 10 == 0:
                print(".", end='', flush=True)

            attempts = 0
            success = False

            while not success and attempts < max_attempts_per_logo:
                success = try_place_logo(size_name, quartier_cls, logo_data)
                attempts += 1

            if success:
                placed_count += 1
                total_placed += 1
            else:
                total_failed += 1
                # Si impossible a placer, l'afficher
                if attempts >= max_attempts_per_logo:
                    print(f"\\n    x Impossible de placer: {logo_data['name']}", flush=True)

        if placed_count > 0:
            print(f"\n  {size_name}: {placed_count}/{target_count} places", flush=True)
        if placed_count < target_count:
            print(f"    ! {target_count - placed_count} logo(s) non place(s)", flush=True)

print(f"\n{'='*60}")
print(f"TOTAL: {total_placed} logos placés, {total_failed} non placés")
print(f"{'='*60}\n")

def px_to_svg(px, py):
    sx = vx + (px / W) * vw
    sy = vy + (py / H) * vh
    return sx, sy

# Create overlay group with logos
overlay_group = ET.Element(q("g"), attrib={"id": "logos_overlay"})

for (px, py, size_name, width_px, height_px, quartier_cls, quartier_info, logo_data) in placed:
    sx, sy = px_to_svg(px, py)
    rect_svg_w = vw * (width_px / W)
    rect_svg_h = vh * (height_px / H)

    # Créer un élément <image> pour afficher le logo
    attribs = {
        "x": str(sx), "y": str(sy),
        "width": str(rect_svg_w), "height": str(rect_svg_h),
        "{http://www.w3.org/1999/xlink}href": logo_data['data_uri'],
        "preserveAspectRatio": "xMidYMid meet",
        "data-size": size_name,
        "data-logo-name": logo_data['name']
    }

    if quartier_info:
        attribs["data-quartier"] = quartier_info['nom']
        attribs["data-couleur"] = quartier_info['couleur']

    overlay_group.append(ET.Element(q("image"), attrib=attribs))

# Insert overlay at end so logos render on top of white-fill hexagons
root.append(overlay_group)
tree.write(OUTPUT_SVG_SQUARES, encoding="utf-8", xml_declaration=True)

# Convert final SVG to PNG using svglib
try:
    drawing_final = svg2rlg(OUTPUT_SVG_SQUARES)
    renderPM.drawToFile(drawing_final, OUTPUT_PNG_SQUARES, fmt="PNG", dpi=72*SCALE)
    print(f"PNG généré: {OUTPUT_PNG_SQUARES}")
except Exception as e:
    print(f"Avertissement: Impossible de générer le PNG: {e}")
    print(f"Le fichier SVG avec les logos est disponible: {OUTPUT_SVG_SQUARES}")

# ======= Récap =======
# Calculer la distribution globale des tailles
total_size_counts = {'very_large': 0, 'large': 0, 'medium': 0, 'small': 0}
for cls in size_counts_by_quartier:
    for size in ['very_large', 'large', 'medium', 'small']:
        total_size_counts[size] += size_counts_by_quartier[cls][size]

print("\n" + "="*60)
print("RÉSUMÉ FINAL")
print("="*60)
print(f"Centre détecté: {center is not None}")
print(f"Nombre de logos placés: {len(placed)}")
print(f"Distribution par taille:")
print(f"  - Very Large: {total_size_counts['very_large']}")
print(f"  - Large: {total_size_counts['large']}")
print(f"  - Medium: {total_size_counts['medium']}")
print(f"  - Small: {total_size_counts['small']}")
print(f"\nRépartition par quartier:")
for cls, count in quartier_stats.items():
    info = QUARTIERS[cls]
    print(f"  {info['nom']} ({info['couleur']}): {count} logos")
print(f"\nFichier SVG généré: {OUTPUT_SVG_SQUARES}")
print("="*60)

# Nettoyer les fichiers temporaires
import os
for cls in QUARTIERS.keys():
    try:
        os.remove(f"temp_quartier_{cls}.svg")
        os.remove(f"temp_quartier_{cls}.png")
    except:
        pass
