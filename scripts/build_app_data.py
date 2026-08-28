#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Régénère data/solutions.generated.js depuis data/solutions.json (le fichier unique de donnee).

Reflète l'état final vérifié : 276 acteurs (exclusions + dédoublonnage + rebrands),
NIST 1 / catégorie unique / sous-catégories, libellés FR, logos (SVG préférés),
et les couleurs NIST exactes.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# URL canonique de production (pour le SEO : canonical, sitemap, llms.txt). Meme depuis test3, on pointe
# la version de reference vers la prod pour ne pas indexer les copies de test.
SITE_BASE = "https://cyberpanorama.fr"
SIZE_FR_SEO = {"very_large": "Grand groupe", "large": "ETI / Scale-up", "medium": "PME", "small": "Startup / TPME"}

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "solutions.generated.js"
JSON_OUT = DATA / "solutions.json"  # le fichier unique de donnee (lu, non modifié ici)

DROP_IDS = {"leviia", "nucleon-security-nucleon-edr", "evertrust-horizon"}
EXCLUDE_IDS = {
    "myrgpd-pro", "rfence", "defensx", "vates", "afnic", "sienna",
    "linagora", "bodyguard", "safebrain", "dlplace",
    "wraptor", "waryme", "clouddataengine", "pow-software-bytesync",
    # Re-vérification 2026-06 : éditeurs disparus ou hors périmètre cyber.
    "beware-cyberlabs",   # dissoute, radiée du RCS le 01/10/2025
    "lybero-net",         # liquidation judiciaire (13/09/2024)
    "opencell-security",  # opencellsoft.com = facturation SaaS (FinTech), pas de la cyber
    "psc-france-cyber-detect-gorille",  # doublon de cyberdetect (meme editeur Cyber-Detect)
    "pradeo-yagaan",  # produit Yagaan = doublon de l editeur pradeo
    # Revue client Hexatrust/CESIN (2026-06) : on garde CoreUpdate et on retire Galeax (meme produit) ;
    # Stackered retire (fournisseur de services, pas editeur).
    "galeax", "stackered",
    # Revue Hexatrust (2026-06) : rachetes + radies / disparus.
    "malizen",  # racheté par Wallix et radié
    "n-cyp",    # racheté, n'existe plus
}
NAME_FIX = {}  # migre dans solutions.json / size_review.json
# Surcharge de description (correction ponctuelle validée par le client).
DESC_FIX = {}  # migre dans solutions.json / size_review.json
# Taille d'entreprise figée par décision (revue Hexatrust). Valeurs : small | medium | large | very_large.
# small=Startup/TPME, medium=PME, large=ETI/Scale Up, very_large=Grand groupe.
SIZE_FIX = {}  # migre dans solutions.json / size_review.json
# Correction d'URL (le site officiel a changé ou l'ancien domaine est mort).
WEBSITE_FIX = {}  # migre dans solutions.json / size_review.json
# Reclassement NIST validé (audit 2026-06, confiance élevée/moyenne). Format : (fonction, catégorie, [sous-catégories]).
CLASSIF_FIX = {}  # migre dans solutions.json / size_review.json

# Couleurs NIST exactes (demandées)
COLORS = {
    "Gouverner": "#F7F19E", "Identifier": "#4AB2DF", "Protéger": "#9190C6",
    "Détecter": "#FAB746", "Répondre": "#ED7368", "Récupérer": "#92C78F",
}
CODES = {"Gouverner": "GV", "Identifier": "ID", "Protéger": "PR",
         "Détecter": "DE", "Répondre": "RS", "Récupérer": "RC"}


def _slug(value):
    """Meme normalisation que parse_submission.slugify : sans accents, minuscules, non-alphanum -> '-'."""
    value = "".join(c for c in unicodedata.normalize("NFD", value or "") if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def load_id_list(path):
    """Lit un fichier 'un id (slug) par ligne' : ignore les lignes vides et les commentaires (#, y compris
    en fin de ligne). Renvoie un set d'ids normalises (slug). Fichier absent -> set vide."""
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(_slug(line))
    return out


def primary_l2(level2, level3):
    level2 = [c for c in (level2 or []) if c]
    if not level2:
        return None
    counts = Counter(c.rsplit("-", 1)[0] for c in (level3 or []))
    return max(level2, key=lambda c: (counts.get(c, 0), -level2.index(c)))


def combined_index(m):
    """Un seul champ d'indexation : le produit phare (en tête) suivi des mots-cles, dedupliques."""
    pp = (m.get("produit_phare") or "").strip()
    terms = ([pp] if pp else []) + [t for t in (m.get("indexation") or []) if t]
    seen, out = set(), []
    for t in terms:
        k = t.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(t.strip())
    return out


def write_seo(solutions, root):
    """Genere les fichiers lisibles par les crawlers et les agents LLM (qui n'executent pas le JS) :
    une page texte (directory.html) avec JSON-LD, un llms.txt, un sitemap.xml et un robots.txt."""
    esc = html.escape
    by_fn = {name: [] for name in CODES}
    for s in solutions:
        by_fn.setdefault(s["nist"]["level1"], []).append(s)
    total = len(solutions)

    # Page texte : un acteur = un <article> en HTML semantique, groupe par fonction NIST.
    sections = []
    for fn in CODES:
        lst = sorted(by_fn.get(fn) or [], key=lambda x: x["solution_name"].lower())
        if not lst:
            continue
        rows = []
        for s in lst:
            codes = " · ".join(c for c in [", ".join(s["nist"].get("level2") or []),
                                           ", ".join(s["nist"].get("level3") or [])] if c)
            meta = " · ".join(p for p in [SIZE_FR_SEO.get(s.get("size", ""), ""), fn, codes] if p)
            web = (s.get("website") or "").strip()
            # On n'autorise que http(s) : une URL javascript:/data: en donnee ne doit pas devenir un lien.
            web_ok = web.lower().startswith(("http://", "https://"))
            link = f'<p><a href="{esc(web)}" rel="noopener noreferrer nofollow">{esc(web)}</a></p>' if web_ok else ""
            rows.append(f'<article><h3>{esc(s["solution_name"])}</h3>'
                        f'<p class="meta">{esc(meta)}</p>'
                        f'<p>{esc(s.get("description") or "")}</p>{link}</article>')
        sections.append(f"<section><h2>{esc(fn)} ({len(lst)})</h2>\n" + "\n".join(rows) + "\n</section>")

    items = []
    for i, s in enumerate(sorted(solutions, key=lambda x: x["solution_name"].lower()), 1):
        org = {"@type": "Organization", "name": s["solution_name"]}
        if s.get("website"):
            org["url"] = s["website"]
        if s.get("description"):
            org["description"] = s["description"]
        items.append({"@type": "ListItem", "position": i, "item": org})
    jsonld = json.dumps({"@context": "https://schema.org", "@type": "ItemList",
                         "name": "Acteurs de la cybersecurite francaise (CyberPanorama)",
                         "numberOfItems": total, "itemListElement": items}, ensure_ascii=False)
    # json.dumps n'echappe pas "</script>" : une description malveillante pourrait fermer le <script>
    # ld+json et injecter du HTML. On echappe < > & (et les separateurs de ligne JS) en \uXXXX (JSON valide).
    jsonld = jsonld.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    intro = (f"Panorama des {total} acteurs de la cybersecurite francaise et europeenne, classes selon le "
             "referentiel NIST CSF 2.0 (Gouverner, Identifier, Proteger, Detecter, Repondre, Recuperer). "
             "Projet mene avec Hexatrust et le CESIN.")
    (root / "directory.html").write_text(
        f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CyberPanorama : {total} acteurs de la cybersecurite francaise (NIST CSF 2.0)</title>
<meta name="description" content="Liste textuelle des {total} acteurs de la cybersecurite francaise classes par fonction NIST CSF 2.0. Par Hexatrust et le CESIN.">
<link rel="canonical" href="{SITE_BASE}/directory.html">
<script type="application/ld+json">{jsonld}</script>
</head>
<body>
<h1>CyberPanorama : {total} acteurs de la cybersecurite francaise</h1>
<p>{intro}</p>
<p><a href="./">Voir le panorama interactif</a></p>
{chr(10).join(sections)}
</body>
</html>
""", encoding="utf-8")

    # llms.txt : resume markdown + liste des acteurs (convention pour les agents LLM).
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    llms = ["# CyberPanorama", "", f"> {intro}", "",
            f"Derniere mise a jour : {today}", "", "## Pages",
            f"- [Panorama interactif]({SITE_BASE}/) : l'application (hexagone NIST, recherche, filtres).",
            f"- [Liste texte des acteurs]({SITE_BASE}/directory.html) : les {total} acteurs en HTML lisible.",
            "", "## Acteurs par fonction NIST CSF 2.0", ""]
    for fn in CODES:
        lst = sorted(by_fn.get(fn) or [], key=lambda x: x["solution_name"].lower())
        if not lst:
            continue
        llms.append(f"### {fn} ({len(lst)})")
        for s in lst:
            web = (s.get("website") or "").strip()
            desc = (s.get("description") or "").replace("\n", " ").strip()
            line = f"- {s['solution_name']}" + (f" ({web})" if web else "") + (f" : {desc}" if desc else "")
            llms.append(line)
        llms.append("")
    (root / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")

    # robots.txt + sitemap.xml
    (root / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}/sitemap.xml\n", encoding="utf-8")
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in ("", "directory.html"):
        sm.append(f"  <url><loc>{SITE_BASE}/{path}</loc><lastmod>{today}</lastmod></url>")
    sm.append("</urlset>")
    (root / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    print(f"écrit SEO : directory.html ({total}), llms.txt, sitemap.xml, robots.txt")


def write_hexatrust_page(root):
    """Genere hexatrust.html a partir d'index.html (SOURCE UNIQUE, pas de duplication) : meme app, mais
    en mode 'hexatrust' (page /hexatrust). On injecte window.CP_MODE avant js/app.js et on adapte le
    titre et la description. Aucune bascule entre les deux pages : chacune s'atteint par son URL."""
    src = (root / "index.html").read_text(encoding="utf-8")
    out = src
    # Mode page : script inline (non defer) -> s'execute avant js/app.js (defer), qui lit window.CP_MODE.
    out = out.replace(
        '<script src="js/app.js" defer></script>',
        '<script>window.CP_MODE = "hexatrust";</script>\n    <script src="js/app.js" defer></script>',
    )
    out = out.replace("<title>CyberPanorama Hexatrust / CESIN</title>",
                      "<title>Panorama HexaTrust — CyberPanorama</title>")
    out = re.sub(r'name="description"\s+content="[^"]*"',
                 'name="description" content="Les solutions de cybersecurite editees par les membres '
                 'd\'HexaTrust, classees par fonction NIST CSF 2.0."', out)
    (root / "hexatrust.html").write_text(out, encoding="utf-8")


def main():
    # solutions.json = donnee finale (un seul fichier, deja fusionne, exclus retires).
    base = json.load((DATA / "solutions.json").open(encoding="utf-8"))
    labels = json.load((DATA / "nist_labels_fr.json").open(encoding="utf-8"))
    global SIZE_REVIEW
    # Re-verification taille (revue IA 2026-06 : registre INSEE + CA + levees). SIZE_FIX (client) reste prioritaire.
    _sr = DATA / "size_review.json"
    SIZE_REVIEW = json.load(_sr.open(encoding="utf-8")) if _sr.exists() else {}

    # Deux listes texte versionnees pilotent la page /hexatrust et l'exclusion du panorama general.
    # is_hexatrust : membres HexaTrust (affiches sur /hexatrust). hq_outside_france : sieges hors de
    # France (masques du panorama general CESIN x HexaTrust, mais conserves sur /hexatrust et dans l'Excel).
    hexatrust_ids = load_id_list(DATA / "solutions_hexatrust.txt")
    hors_france_ids = load_id_list(DATA / "solutions_sieges_hors_france.txt")

    level1_catalog = {name: {"code": CODES[name], "label": name, "color": COLORS[name]}
                      for name in CODES}
    level2_catalog = {code: {"function": next(n for n in CODES if CODES[n] == code[:2]),
                             "label": lab}
                      for code, lab in labels["level2"].items()}
    level3_catalog = dict(labels["level3"])

    solutions = []
    for s in base:
        sid = s.get("id")
        if sid in DROP_IDS or sid in EXCLUDE_IDS:   # filet de securite (deja retires de solutions.json)
            continue
        m = dict(s)
        if sid in NAME_FIX:
            m["solution_name"] = NAME_FIX[sid]
            m["company_name"] = NAME_FIX[sid]
        if sid in WEBSITE_FIX:
            m["website"] = WEBSITE_FIX[sid]
        if sid in DESC_FIX:
            m["description"] = DESC_FIX[sid]
        if sid in SIZE_REVIEW:                         # taille re-verifiee (IA)
            m["size"] = SIZE_REVIEW[sid].get("size_code", m.get("size"))
        if sid in SIZE_FIX:                            # taille figee client : prioritaire
            m["size"] = SIZE_FIX[sid]
        if sid in CLASSIF_FIX:
            l1f, l2f, l3f = CLASSIF_FIX[sid]
            m["nist"] = {"level1": l1f, "level2": [l2f], "level3": list(l3f)}
        nist = m.get("nist") or {}
        # On garde TOUTES les catégories N2 (jusqu'à 3) et TOUS les N3 : l'app sait afficher/filtrer
        # plusieurs N2. (Avant, primary_l2 n'en gardait qu'une, ce qui perdait les autres.)
        l2_all = [c for c in (nist.get("level2") or []) if c]
        l3_all = [c for c in (nist.get("level3") or []) if c]
        solutions.append({
            "id": sid,
            "solution_name": m.get("solution_name", ""),
            "company_name": m.get("company_name", m.get("solution_name", "")),
            "logo_path": m.get("logo_path", ""),
            "logo_file": m.get("logo_file", ""),
            "logo_source": m.get("logo_source", ""),
            "size": m.get("size", "medium"),
            "nist": {"level1": nist.get("level1", ""),
                     "level2": l2_all,
                     "level3": l3_all},
            "description": m.get("description", ""),
            "detailed_description": m.get("detailed_description", ""),
            "website": m.get("website", ""),
            "email_contact": m.get("email_contact", ""),
            "contact_url": m.get("contact_url", ""),
            "country": m.get("country", ""),
            "is_french": bool(m.get("is_french")),
            "nis2_objective": m.get("nis2_objective", ""),
            "indexation": combined_index(m),
            "is_hexatrust": _slug(sid) in hexatrust_ids,
            "hq_outside_france": _slug(sid) in hors_france_ids,
        })

    syn_path = DATA / "search_synonyms.json"
    synonyms = json.load(syn_path.open(encoding="utf-8")).get("groups", []) if syn_path.exists() else []

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "level1_catalog": level1_catalog,
        "level2_catalog": level2_catalog,
        "level3_catalog": level3_catalog,
        "search_synonyms": synonyms,
        "solutions": solutions,
        "quality_summary": {"total": len(solutions)},
    }
    body = "window.CYBERPANORAMA_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"
    OUT.write_text(body, encoding="utf-8")
    svg = sum(1 for s in solutions if (s["logo_path"] or "").lower().endswith(".svg"))
    print(f"écrit {OUT.name} : {len(solutions)} solutions | {svg} logos SVG")

    write_seo(solutions, DATA.parent)  # directory.html, llms.txt, sitemap.xml, robots.txt a la racine
    write_hexatrust_page(DATA.parent)  # hexatrust.html (page /hexatrust) genere depuis index.html
    print("écrit hexatrust.html (page /hexatrust)")


if __name__ == "__main__":
    main()
