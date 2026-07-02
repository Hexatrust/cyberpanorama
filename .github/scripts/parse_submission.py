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


# Libelles de section CONNUS (formulaires add + edit), sans accents ni casse. Un '### <titre>' n'est
# traite comme separateur de section QUE si son titre est dans cet ensemble. Ainsi un '###' present
# dans la VALEUR d'un champ (titre markdown dans une description, ou injection type '### Logo ...')
# ne casse pas le parsing et ne peut pas detourner un autre champ.
KNOWN_SECTION_LABELS = {
    "nom de l'entreprise ou de la solution",
    "nom exact de l'entreprise ou de la solution a modifier",
    "fonction nist csf 2.0 principale",
    "nouvelle fonction nist (si changement)",
    "categories nist csf 2.0 - n2 (1 a 3)",
    "nouvelles categories nist n2 (si changement)",
    "sous-categories nist csf 2.0 - n3",
    "nouvelles sous-categories nist n3 (si changement)",
    "taille de l'entreprise",
    "nouvelle taille (si changement)",
    "description courte",
    "nouvelle description (si changement)",
    "description longue",
    "objectif nis2 principal",
    "site web",
    "nouveau site web (si changement)",
    "contact (email ou page contact)",
    "nouveau contact (si changement)",
    "logo (fichier ou url)",
    "nouveau logo (fichier ou url, si changement)",
    "suppression",
    "raison de la modification",
    "engagement",
}


def field(body, label):
    """Valeur sous un titre de section '### <label>'. Le titre est compare SANS accents ni casse.
    Seuls les '### <libelle connu>' (KNOWN_SECTION_LABELS) delimitent les sections : un '###' quelconque
    dans la valeur d'un champ reste dans la valeur (pas de troncature, pas de detournement de champ)."""
    target = strip_accents(label).strip().lower()
    cur, buf, found = None, [], None
    for line in body.splitlines():
        m = re.match(r"###[ \t]*(.+?)[ \t]*$", line)
        head = strip_accents(m.group(1)).strip().lower() if m else None
        if head is not None and head in KNOWN_SECTION_LABELS:
            if cur == target and found is None:
                found = "\n".join(buf).strip()
            cur, buf = head, []
        elif cur is not None:
            buf.append(line)
    if cur == target and found is None:
        found = "\n".join(buf).strip()
    if found is None:
        return ""
    return "" if strip_accents(found).lower() in EMPTY else found


def reject_duplicate_sections(body):
    """Un formulaire GitHub produit chaque section une seule fois. Si un libelle CONNU apparait en
    double, c'est qu'un champ (ex. une description) contient un faux '### <libelle>' pour detourner un
    autre champ : on refuse (le vrai champ serait sinon ambigu)."""
    seen = {}
    for line in body.splitlines():
        m = re.match(r"###[ \t]*(.+?)[ \t]*$", line)
        if not m:
            continue
        h = strip_accents(m.group(1)).strip().lower()
        if h in KNOWN_SECTION_LABELS:
            seen[h] = seen.get(h, 0) + 1
    dups = sorted(h for h, n in seen.items() if n > 1)
    if dups:
        raise ValueError(
            "un de vos textes contient une ligne qui commence par « ### » suivie d'un intitulé de "
            "champ du formulaire (" + ", ".join(dups) + "), ce qui empêche de lire correctement la "
            "soumission. Retirez le « ### » au début de cette ligne dans votre description, puis "
            "relancez.")


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
        if re.fullmatch(r"[A-Z]{2}\.[A-Z]{2}(?:-\d{2})?", c) and c not in out:
            out.append(c)                              # dedup : pas de code en double
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
    renvoye vers une cible interne apres coup. Et retire l'en-tete Authorization sur la redirection :
    GitHub redirige les images (user-attachments) vers une URL signee (jwt en query) qui REFUSE un
    'Authorization: token' en plus -> HTTP 400. On ne renvoie donc jamais le token sur une redirection."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ensure_public_url(newurl)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            for k in [h for h in list(new.headers) if h.lower() == "authorization"]:
                del new.headers[k]
        return new


IMG_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
           "image/svg+xml": "svg", "image/webp": "webp"}


# Elements et attributs qui rendent un SVG "actif" (executent du JS, chargent du distant, ouvrent un
# vecteur XXE). Un logo n'en a jamais besoin : on les retire systematiquement.
_SVG_BAD_TAGS = {"script", "foreignobject", "iframe", "object", "embed",
                 "animate", "animatetransform", "animatemotion", "set", "handler"}
_SVG_HREF_ATTRS = {"href", "{http://www.w3.org/1999/xlink}href", "src", "xlink:href"}
# <use> et <image> chargent une ressource : on ne garde qu'une reference INTERNE (#id) ou une image
# raster embarquee (data:image/png...). Tout ce qui est http externe, ou data:image/svg (SVG imbrique
# potentiellement piege), fait retirer l'element.
_SVG_SAFE_REF_DATA = ("data:image/png", "data:image/jpeg", "data:image/jpg",
                      "data:image/gif", "data:image/webp")


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

    def drop(el):
        p = parents.get(el)
        if p is not None:
            p.remove(el)

    for el in list(root.iter()):
        local = el.tag.split("}")[-1].lower()
        # <use>/<image> : uniquement une reference interne (#id) ou une image raster embarquee.
        # Sinon (http externe, data:image/svg imbrique) on retire l'element : pas de ressource distante.
        if local in ("use", "image"):
            ref = next((el.attrib[a] for a in el.attrib if a.split("}")[-1].lower().endswith("href")), "").strip().lower()
            if ref and not ref.startswith("#") and not ref.startswith(_SVG_SAFE_REF_DATA):
                drop(el)
                continue
        if local in _SVG_BAD_TAGS:
            drop(el)
            continue
        # <style> : CSS interne. On neutralise l'import distant, expression() (IE) et url() externe,
        # tout en gardant les url(#id) internes (degrades, filtres) legitimes.
        if local == "style" and el.text:
            css = re.sub(r"@import[^;]*;?", "", el.text, flags=re.I)
            css = re.sub(r"expression\s*\(", "blocked(", css, flags=re.I)
            css = re.sub(r"url\(\s*['\"]?\s*(?:https?:|ftp:|//)[^)]*\)", "url(#)", css, flags=re.I)
            el.text = css
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


def _image_ext_from_magic(data):
    """Type d'image d'apres la signature d'octets (independant du Content-Type de l'hebergeur, souvent
    generique). Renvoie png/jpg/gif/webp, ou None si la signature n'est pas reconnue."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


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
        # On lit 1 octet de plus que la limite : si on l'atteint, l'image depasse 4 Mo -> on refuse
        # au lieu de la tronquer silencieusement (fichier corrompu).
        data = r.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("logo trop lourd (maximum 4 Mo). Fournissez une image plus légère.")
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    is_svg = data[:300].lstrip().lower().startswith(b"<svg") or b"<svg" in data[:300]
    magic = _image_ext_from_magic(data)            # type reel d'apres les octets (fiable)
    # On accepte des qu'un indice dit "image" : Content-Type image connu, signature d'octets, ou SVG.
    # Beaucoup d'hebergeurs servent une image avec un Content-Type generique (octet-stream, vide...) :
    # on ne veut PAS rejeter un vrai logo pour ca. On refuse seulement si rien n'indique une image.
    ext = IMG_EXT.get(ctype) or magic
    if not ext and not is_svg and not ctype.startswith("image/"):
        raise ValueError("le logo fourni n'est pas une image reconnue (formats acceptés : PNG, JPG, GIF, SVG, WebP).")
    if is_svg:
        ext = "svg"
    elif not ext:                                  # Content-Type 'image/...' sans sous-type connu
        tail = url.lower().split("?")[0].rsplit(".", 1)[-1]
        ext = tail if tail in ("png", "jpg", "jpeg", "gif", "webp") else "png"
    if ext == "jpeg":
        ext = "jpg"
    if is_svg:
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
    if len(l2) > 3:
        errs.append(f"maximum 3 catégories N2 (vous en avez indiqué {len(l2)})")
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
    reject_duplicate_sections(body)          # refuse une section de formulaire en double (injection)

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
        # edit ou SUPPRESSION : retrouver l'entree existante (par nom ou slug).
        want_delete = "[x]" in field(body, "Suppression").lower()
        path = DATA / "solutions.json"
        items = load(path, [])
        cur = next((s for s in items
                    if (s.get("solution_name", "").lower() == name.lower()) or s.get("id") == slug), None)
        if cur is None:
            print(f"ERREUR : entreprise '{name}' introuvable dans le panorama")
            sys.exit(1)
        tid = cur.get("id")
        if want_delete:
            # Suppression demandee : on retire l'entree. Les autres champs du formulaire sont ignores.
            lf = cur.get("logo_file")
            if lf and (LOGOS / lf).exists():
                (LOGOS / lf).unlink()                 # on retire aussi le fichier logo (pas d'orphelin)
            items = [s for s in items if s.get("id") != tid]
            path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Suppression préparée : {name} ({tid})")
            emit("company_name", name)
            emit("slug", tid)
            return
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
    # Les erreurs attendues (logo non-image, SVG piege, SSRF, URL invalide...) sont levees en ValueError.
    # On les affiche proprement ("ERREUR : ...") au lieu d'un traceback Python illisible dans le commentaire.
    try:
        main()
    except ValueError as exc:
        print(f"ERREUR : {exc}")
        sys.exit(1)
