#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse une GitHub Issue (formulaire add_company / edit_company) et prepare les changements de donnees.

Mode "add"  : ajoute une entree dans data/solutions.json (le fichier unique de donnee).
Mode "edit" : modifie l'entree ciblee dans data/solutions.json.
Dans les deux cas le logo fourni est telecharge dans assets/logos/, puis build_app_data.py regenere
data/solutions.generated.js. Lance par le workflow quand un mainteneur pose le label approved.

Usage : python3 .github/scripts/parse_submission.py <issue_number> <add|edit>
Stdlib uniquement. Variables d'env : GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_OUTPUT (optionnel).
"""
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
LOGOS = ROOT / "assets" / "logos"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

FONCTION_MAP = {
    "gouverner": "Gouverner", "identifier": "Identifier", "proteger": "Protéger",
    "detecter": "Détecter", "repondre": "Répondre", "recuperer": "Récupérer",
}
SIZE_MAP = {
    "grand groupe": "very_large", "eti / scale up": "large",
    "pme": "medium", "startup / tpme": "small",
}
EMPTY = {"", "_no response_", "n/a", "(aucun)", "(inchange)", "none"}


def strip_accents(value):
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")


def slugify(value):
    value = strip_accents(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "solution"


def fetch_issue(number):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def field(body, label):
    """Valeur sous un titre de section '### <label>'. Le titre est compare SANS accents ni casse
    (les libelles du formulaire peuvent en avoir), mais la valeur est renvoyee telle quelle (accents
    preserves). Ainsi on peut accentuer les libelles du formulaire sans toucher a ce script."""
    target = strip_accents(label).strip().lower()
    for m in re.finditer(r"###[ \t]*([^\n]+?)[ \t]*\n+(.*?)(?=\n###|\Z)", body, re.DOTALL):
        if strip_accents(m.group(1)).strip().lower() == target:
            val = m.group(2).strip()
            return "" if strip_accents(val).lower() in EMPTY else val
    return ""


def checked_codes(body, label, limit=3):
    """Codes coches dans une liste de checkboxes (lignes '- [x] CODE : ...')."""
    sec = re.search(r"###\s*" + re.escape(label) + r"\s*\n(.+?)(?=\n###|\Z)", body, re.DOTALL)
    if not sec:
        return []
    items = re.findall(r"-\s*\[x\]\s*([^\n:]+)", sec.group(1), re.IGNORECASE)
    return [it.split(":")[0].strip() for it in items][:limit]


def codes_from_text(text, limit=12):
    """Codes NIST depuis un champ texte libre : 'PR.DS-01, DE.CM' -> ['PR.DS-01', 'DE.CM'].
    On ne garde que les jetons qui ressemblent a un code (XX.XX ou XX.XX-NN)."""
    if not text:
        return []
    out = []
    for tok in re.split(r"[,;\s]+", text.strip()):
        c = tok.strip().upper()
        if re.fullmatch(r"[A-Z]{2}\.[A-Z]{2}(?:-\d{2})?", c):
            out.append(c)
    return out[:limit]


def image_url_from(text):
    """Extrait l'URL d'une image depuis un champ : image markdown `![](url)` (cas d'un fichier glisse
    dans le formulaire, heberge par GitHub), pieces jointes GitHub, ou URL d'image nue."""
    if not text:
        return ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', text, re.I)        # <img src="url"> (image collee/glissee)
    if m:
        return m.group(1)
    m = re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)            # ![alt](url) (drag & drop)
    if m:
        return m.group(1)
    m = re.search(r"https?://(?:user-images\.githubusercontent\.com|github\.com/user-attachments)/\S+", text)
    if m:
        return m.group(0).rstrip('".,)\'<>')
    m = re.search(r"https?://\S+\.(?:png|gif|jpe?g|svg|webp)", text, re.I)  # URL d'image nue
    if m:
        return m.group(0).rstrip('".,)\'<>')
    m = re.search(r"https?://\S+", text)  # toute URL en dernier recours (download_logo valide que c'est bien une image)
    return m.group(0).rstrip('".,)\'<>') if m else ""


def ensure_public_url(url):
    """Anti-SSRF : n'accepte que http(s) vers une IP publique (rejette loopback, LAN, link-local
    169.254.169.254 metadata, etc.). Leve une erreur sinon. Resout le DNS et verifie chaque IP."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError(f"URL refusée (schéma/hôte) : {url!r}")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(p.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"résolution DNS impossible pour {p.hostname!r}") from exc
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"IP non publique bloquée ({ip}) pour {p.hostname!r}")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Revalide chaque redirection (les CDN GitHub redirigent vers S3) pour qu'on ne soit pas
    renvoye vers une cible interne apres coup."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ensure_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


IMG_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
           "image/svg+xml": "svg", "image/webp": "webp"}


# Elements et attributs qui rendent un SVG "actif" (executent du JS, chargent du distant, ouvrent un
# vecteur XXE). Un logo n'en a jamais besoin : on les retire systematiquement.
_SVG_BAD_TAGS = {"script", "foreignobject", "iframe", "object", "embed",
                 "animate", "animatetransform", "animatemotion", "set", "handler", "use"}
_SVG_HREF_ATTRS = {"href", "{http://www.w3.org/1999/xlink}href", "src", "xlink:href"}


def sanitize_svg(data):
    """Neutralise un SVG potentiellement piege : refuse DOCTYPE/ENTITY (XXE, billion-laughs), retire
    les balises actives (script, foreignObject, use externe...), les gestionnaires on* et les URI
    javascript:/data:text-html. Renvoie le SVG nettoye en bytes. Leve ValueError si illisible/dangereux.

    On rend le SVG inoffensif AU LIEU de juste verifier : un controle ("est-ce une image ?") ne supprime
    pas un payload contenu dans un SVG par ailleurs valide. Le fichier ecrit dans le depot est donc une
    version desinfectee, pas l'original."""
    text = data.decode("utf-8", "ignore")
    if re.search(r"<!doctype|<!entity", text, re.I):
        raise ValueError("SVG refusé : déclaration DOCTYPE/ENTITY (risque XXE) interdite dans un logo.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError(f"SVG illisible : {e}")
    parents = {child: parent for parent in root.iter() for child in parent}
    for el in list(root.iter()):
        local = el.tag.split("}")[-1].lower()
        # <use href="http..."> peut tirer un fragment distant : on ne garde que les <use> internes (#id).
        if local == "use":
            ref = next((el.attrib[a] for a in el.attrib if a.split("}")[-1].lower() == "href"), "")
            if ref.strip().startswith("#"):
                continue
        if local in _SVG_BAD_TAGS:
            p = parents.get(el)
            if p is not None:
                p.remove(el)
            continue
        for attr in list(el.attrib):
            an = attr.split("}")[-1].lower()
            val = el.attrib[attr]
            flat = re.sub(r"\s+", "", val).lower()
            if an.startswith("on"):                                   # onload, onclick, onbegin...
                del el.attrib[attr]
            elif an in {a.split("}")[-1].lower() for a in _SVG_HREF_ATTRS} or an.endswith("href"):
                if flat.startswith(("javascript:", "data:text/html", "data:image/svg")):
                    del el.attrib[attr]
            elif an == "style" and ("javascript:" in flat or "expression(" in flat or "url(" in flat):
                del el.attrib[attr]
    return ET.tostring(root, encoding="utf-8")


def download_logo(url, slug):
    ensure_public_url(url)                         # anti-SSRF avant toute requete
    headers = {"User-Agent": UA}
    # Image deposee dans le formulaire (depot prive) : l'URL GitHub exige le token du runner. On ne
    # joint le token QUE pour les hotes GitHub (jamais vers un hote arbitraire).
    token = os.environ.get("GITHUB_TOKEN", "")
    host = (urlparse(url).hostname or "").lower()
    # Limite de domaine STRICTE (un point) : sinon "evilgithubusercontent.com" passerait le endswith
    # et le token du runner fuirait vers le serveur de l'attaquant.
    if token and (host == "github.com" or host == "githubusercontent.com"
                  or host.endswith(".githubusercontent.com")):
        headers["Authorization"] = f"token {token}"
    opener = urllib.request.build_opener(_SafeRedirect)   # verification TLS par defaut (active)
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=30) as r:
        data = r.read(4_000_000)
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    is_svg = data[:300].lstrip().lower().startswith(b"<svg") or b"<svg" in data[:300]
    ext = IMG_EXT.get(ctype)
    if not ext and not (is_svg or ctype.startswith("image/")):
        raise ValueError(f"contenu non-image refusé (Content-Type={ctype!r}) pour {url!r}")
    if not ext:
        tail = url.lower().split("?")[0].rsplit(".", 1)[-1]
        ext = tail if tail in ("png", "jpg", "jpeg", "gif", "svg", "webp") else "png"
    if is_svg:
        ext = "svg"
        data = sanitize_svg(data)                  # desinfection AVANT ecriture dans le depot
    LOGOS.mkdir(parents=True, exist_ok=True)
    name = f"{slug}.{ext}"
    (LOGOS / name).write_bytes(data)
    return name


def load(path, default):
    return json.load(path.open(encoding="utf-8")) if path.exists() else default


def emit(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        # Une valeur multi-lignes (nom saisi par l'utilisateur) pourrait injecter d'autres sorties
        # d'etape : on neutralise les retours a la ligne.
        value = str(value).replace("\r", " ").replace("\n", " ")
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


FUNC_BY_PREFIX = {"GV": "Gouverner", "ID": "Identifier", "PR": "Protéger",
                  "DE": "Détecter", "RS": "Répondre", "RC": "Récupérer"}


def validate_nist(nist):
    """Verifie la classification finale : les codes N2/N3 existent dans le referentiel
    (data/nist_labels_fr.json) et le N3 se rattache a une N2 choisie. On n'exige PAS que le N2
    appartienne a la fonction N1 : un acteur peut porter des capacites d'autres fonctions.
    Retourne la liste des erreurs (vide = OK)."""
    labels = load(DATA / "nist_labels_fr.json", {})
    valid_l2 = set(labels.get("level2", {}))
    valid_l3 = set(labels.get("level3", {}))
    l2 = nist.get("level2") or []
    l3 = nist.get("level3") or []
    errs = []
    for c in l2:
        if c not in valid_l2:
            errs.append(f"catégorie N2 inconnue : {c}")
    for c in l3:
        if c not in valid_l3:
            errs.append(f"sous-catégorie N3 inconnue : {c}")
        elif l2 and not any(c.startswith(p + "-") for p in l2):
            errs.append(f"la sous-catégorie N3 {c} ne se rattache à aucune catégorie N2 choisie")
    return errs


def fail_if_invalid_nist(nist):
    errs = validate_nist(nist)
    if errs:
        print("ERREUR : classification NIST invalide :")  # en-tete repris dans le commentaire de l'issue
        for e in errs:
            print(f"   - {e}")
        sys.exit(1)


def main():
    number, mode = sys.argv[1], sys.argv[2]
    issue = fetch_issue(number)
    body = issue.get("body") or ""

    name = field(body, "Nom de l'entreprise ou de la solution") or \
        field(body, "Nom exact de l'entreprise ou de la solution a modifier")
    if not name:
        print("ERREUR : nom d'entreprise introuvable dans le formulaire")
        sys.exit(1)
    slug = slugify(name)

    fonction = FONCTION_MAP.get(strip_accents(field(body, "Fonction NIST CSF 2.0 principale")
                                              or field(body, "Nouvelle fonction NIST (si changement)")).lower())
    size = SIZE_MAP.get(field(body, "Taille de l'entreprise").lower()) or \
        SIZE_MAP.get(field(body, "Nouvelle taille (si changement)").lower())
    desc = field(body, "Description courte") or field(body, "Nouvelle description (si changement)")
    website = field(body, "Site web") or field(body, "Nouveau site web (si changement)")
    contact = field(body, "Contact (email ou page contact)") or field(body, "Nouveau contact (si changement)")
    # Logo : un seul champ qui accepte une image deposee (PNG/GIF/JPG/SVG/WebP) OU une URL collee.
    upload = field(body, "Logo (fichier ou URL)") or \
        field(body, "Nouveau logo (fichier ou URL, si changement)")
    logo_url = image_url_from(upload)
    # Libelles ajout = sans "(optionnel)" (tout est obligatoire a l'ajout) ; on tente aussi la variante
    nis2 = field(body, "Objectif NIS2 principal") or field(body, "Nouvel objectif NIS2 (si changement)")
    # Description longue : affichee nulle part, elle sert au moteur de recherche (indexation du contenu).
    detailed = field(body, "Description longue") or field(body, "Nouvelle description longue (si changement)")
    # N2 (categories) : menu multi-choix (ajout) ou texte libre (modif). N3 (sous-categories) : texte libre.
    level2 = codes_from_text(field(body, "Categories NIST CSF 2.0 - N2 (1 a 3)")) \
        or codes_from_text(field(body, "Nouvelles categories NIST N2 (si changement)"))
    level3 = codes_from_text(field(body, "Sous-categories NIST CSF 2.0 - N3")
                             or field(body, "Nouvelles sous-categories NIST N3 (si changement)"))

    logo_file = download_logo(logo_url, slug) if logo_url else None
    contact_field = "email_contact" if contact and "@" in contact else "contact_url"

    if mode == "add":
        # A l'ajout, TOUT est obligatoire (cote formulaire ET cote serveur, au cas ou un champ serait vide).
        for label_, val in (("fonction NIST", fonction), ("catégories N2", level2),
                            ("sous-catégories N3", level3), ("taille", size), ("description courte", desc),
                            ("description longue", detailed),
                            ("objectif NIS2", nis2), ("site web", website), ("contact", contact),
                            ("logo", logo_file)):
            if not val:
                print(f"ERREUR : champ obligatoire manquant pour un ajout : {label_}")
                sys.exit(1)
        entry = {
            "id": slug, "solution_name": name, "company_name": name,
            "logo_path": f"assets/logos/{logo_file}", "logo_file": logo_file, "logo_source": "submission",
            "size": size, "nist": {"level1": fonction, "level2": level2, "level3": level3},
            "description": desc, "website": website, "country": "France", "is_french": True,
            # Plus de champ mots-cles : la recherche s'appuie sur la description longue (indexation).
            "indexation": [],
        }
        fail_if_invalid_nist(entry["nist"])
        if contact:
            entry[contact_field] = contact
        if nis2:
            entry["nis2_objective"] = nis2
        if detailed:
            entry["detailed_description"] = detailed
        path = DATA / "solutions.json"
        items = load(path, [])
        # Un ajout ne doit JAMAIS ecraser un acteur existant (collision de slug = usurpation possible).
        if any(it.get("id") == slug for it in items):
            print(f"ERREUR : un acteur avec l'id '{slug}' existe deja. Utilisez le formulaire de MODIFICATION.")
            sys.exit(1)
        items = items + [entry]
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Ajout préparé : {name} ({slug})")
    else:
        # edit : retrouver l'entree existante (par nom ou slug) et modifier ses champs en place.
        path = DATA / "solutions.json"
        items = load(path, [])
        cur = next((s for s in items
                    if (s.get("solution_name", "").lower() == name.lower()) or s.get("id") == slug), None)
        if cur is None:
            print(f"ERREUR : entreprise '{name}' introuvable dans le panorama")
            sys.exit(1)
        tid = cur.get("id")
        if desc:
            cur["description"] = desc
        if website:
            cur["website"] = website
        if contact:
            cur[contact_field] = contact
        if size:
            cur["size"] = size
        if fonction:
            cur.setdefault("nist", {})["level1"] = fonction
        if level2:
            cur.setdefault("nist", {})["level2"] = level2
        if level3:
            cur.setdefault("nist", {})["level3"] = level3
        fail_if_invalid_nist(cur.get("nist") or {})
        if logo_file:
            cur["logo_path"] = f"assets/logos/{logo_file}"
            cur["logo_file"] = logo_file
            cur["logo_source"] = "submission"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Modification préparée : {name} ({tid})")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_app_data.py")], check=True)
    emit("company_name", name)
    emit("slug", slug)


if __name__ == "__main__":
    main()
