#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse une GitHub Issue (formulaire add_company / edit_company) et prepare les changements de donnees.

Mode "add"  : ajoute une entree dans data/solutions.json (le fichier unique de donnee).
Mode "edit" : modifie l'entree ciblee dans data/solutions.json.
Dans les deux cas le logo fourni est telecharge dans assets/logos/, puis build_app_data.py regenere
data/solutions.generated.js. Le workflow ouvre ensuite une Pull Request pour validation manuelle.

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
    """Valeur sous un titre de section '### <label>' jusqu'au prochain titre."""
    pat = r"###\s*" + re.escape(label) + r"\s*\n+(.+?)(?=\n###|\Z)"
    m = re.search(pat, body, re.DOTALL)
    if not m:
        return ""
    val = m.group(1).strip()
    return "" if val.lower() in EMPTY else val


def checked_codes(body, label, limit=3):
    """Codes coches dans une liste de checkboxes (lignes '- [x] CODE : ...')."""
    sec = re.search(r"###\s*" + re.escape(label) + r"\s*\n(.+?)(?=\n###|\Z)", body, re.DOTALL)
    if not sec:
        return []
    items = re.findall(r"-\s*\[x\]\s*([^\n:]+)", sec.group(1), re.IGNORECASE)
    return [it.split(":")[0].strip() for it in items][:limit]


def image_url_from(text):
    """Extrait l'URL d'une image depuis un champ : image markdown `![](url)` (cas d'un fichier glisse
    dans le formulaire, heberge par GitHub), pieces jointes GitHub, ou URL d'image nue."""
    if not text:
        return ""
    m = re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)            # ![alt](url) (drag & drop)
    if m:
        return m.group(1)
    m = re.search(r"https?://(?:user-images\.githubusercontent\.com|github\.com/user-attachments)/\S+", text)
    if m:
        return m.group(0).rstrip(").,")
    m = re.search(r"https?://\S+\.(?:png|gif|jpe?g|svg|webp)", text, re.I)  # URL d'image nue
    return m.group(0) if m else ""


def ensure_public_url(url):
    """Anti-SSRF : n'accepte que http(s) vers une IP publique (rejette loopback, LAN, link-local
    169.254.169.254 metadata, etc.). Leve une erreur sinon. Resout le DNS et verifie chaque IP."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError(f"URL refusee (schema/hote) : {url!r}")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(p.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"resolution DNS impossible pour {p.hostname!r}") from exc
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"IP non publique bloquee ({ip}) pour {p.hostname!r}")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Revalide chaque redirection (les CDN GitHub redirigent vers S3) pour qu'on ne soit pas
    renvoye vers une cible interne apres coup."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ensure_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


IMG_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
           "image/svg+xml": "svg", "image/webp": "webp"}


def download_logo(url, slug):
    ensure_public_url(url)                         # anti-SSRF avant toute requete
    headers = {"User-Agent": UA}
    # Image deposee dans le formulaire (depot prive) : l'URL GitHub exige le token du runner. On ne
    # joint le token QUE pour les hotes GitHub (jamais vers un hote arbitraire).
    token = os.environ.get("GITHUB_TOKEN", "")
    host = (urlparse(url).hostname or "").lower()
    if token and (host.endswith("githubusercontent.com") or host == "github.com"):
        headers["Authorization"] = f"token {token}"
    opener = urllib.request.build_opener(_SafeRedirect)   # verification TLS par defaut (active)
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=30) as r:
        data = r.read(4_000_000)
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    is_svg = data[:300].lstrip().lower().startswith(b"<svg") or b"<svg" in data[:300]
    ext = IMG_EXT.get(ctype)
    if not ext and not (is_svg or ctype.startswith("image/")):
        raise ValueError(f"contenu non-image refuse (Content-Type={ctype!r}) pour {url!r}")
    if not ext:
        tail = url.lower().split("?")[0].rsplit(".", 1)[-1]
        ext = tail if tail in ("png", "jpg", "jpeg", "gif", "svg", "webp") else "png"
    if is_svg:
        ext = "svg"
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
    # Logo : priorite a l'image deposee dans le formulaire (PNG/GIF/JPG/SVG), sinon l'URL fournie.
    upload = field(body, "Logo (glissez ou collez une image PNG, GIF, JPG, SVG)")
    logo_url = (image_url_from(upload)
                or field(body, "URL du logo (si pas d'upload ci-dessus)")
                or field(body, "URL du logo")
                or field(body, "Nouvelle URL de logo (si changement)"))
    keywords = [k.strip() for k in field(body, "Mots-cles (optionnel)").split(",") if k.strip()]
    nis2 = field(body, "Objectif NIS2 principal (optionnel)")
    detailed = field(body, "Description detaillee (optionnel)")
    level2 = checked_codes(body, "Sous-categories NIST CSF 2.0 (optionnel, 3 maximum)")

    logo_file = download_logo(logo_url, slug) if logo_url else None
    contact_field = "email_contact" if contact and "@" in contact else "contact_url"

    if mode == "add":
        for label_, val in (("fonction NIST", fonction), ("taille", size), ("description", desc),
                            ("site web", website), ("logo", logo_file)):
            if not val:
                print(f"ERREUR : champ obligatoire manquant pour un ajout : {label_}")
                sys.exit(1)
        entry = {
            "id": slug, "solution_name": name, "company_name": name,
            "logo_path": f"assets/logos/{logo_file}", "logo_file": logo_file, "logo_source": "submission",
            "size": size, "nist": {"level1": fonction, "level2": level2, "level3": []},
            "description": desc, "website": website, "country": "France", "is_french": True,
            "indexation": keywords,
        }
        if contact:
            entry[contact_field] = contact
        if nis2:
            entry["nis2_objective"] = nis2
        if detailed:
            entry["detailed_description"] = detailed
        path = DATA / "solutions.json"
        items = load(path, [])
        items = [it for it in items if it.get("id") != slug] + [entry]
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Ajout prepare : {name} ({slug})")
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
        if logo_file:
            cur["logo_path"] = f"assets/logos/{logo_file}"
            cur["logo_file"] = logo_file
            cur["logo_source"] = "submission"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Modification preparee : {name} ({tid})")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_app_data.py")], check=True)
    emit("company_name", name)
    emit("slug", slug)


if __name__ == "__main__":
    main()
