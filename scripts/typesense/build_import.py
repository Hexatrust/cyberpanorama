#!/usr/bin/env python3
"""Construit le fichier JSONL d'import Typesense depuis data/solutions.generated.js.

Sortie : un document par ligne, champs alignes sur scripts/typesense/schema.json.
Usage : python3 scripts/typesense/build_import.py [chemin_sortie.jsonl]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "data" / "solutions.generated.js"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_ts" / "solutions.jsonl"


def main():
    text = GEN.read_text(encoding="utf-8")
    payload = json.loads(text[text.index("{"): text.rindex("}") + 1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with OUT.open("w", encoding="utf-8") as f:
        for s in payload.get("solutions", []):
            nist = s.get("nist", {}) or {}
            doc = {
                "id": s["id"],
                "solution_name": s.get("solution_name", "") or "",
                "company_name": s.get("company_name", "") or "",
                "description": s.get("description", "") or "",
                "detailed_description": s.get("detailed_description", "") or "",
                "indexation": s.get("indexation", []) or [],
                "nis2_objective": s.get("nis2_objective", "") or "",
                "nist_l1": nist.get("level1", "") or "",
                "nist_l2": nist.get("level2", []) or [],
                "nist_l3": nist.get("level3", []) or [],
                "country": s.get("country", "") or "",
                "size": s.get("size", "") or "",
                "is_french": bool(s.get("is_french")),
                "website": s.get("website", "") or "",
                "logo_path": s.get("logo_path", "") or "",
            }
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            n += 1
    print(f"ecrit {OUT} : {n} documents")


if __name__ == "__main__":
    main()
