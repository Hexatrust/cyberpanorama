#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point d'entree UNIQUE du pipeline de donnees CyberPanorama.

L'EXCEL (data/solutions_master.xlsx) est la SOURCE DE VERITE. Par defaut on part donc de l'Excel :
on le reinjecte dans le JSON, puis on regenere le site et l'Excel. Si l'Excel et le JSON different,
c'est l'Excel qui gagne.

  python3 scripts/build.py                # defaut : l'Excel est la source -> reinjecte dans le JSON,
                                          #   puis regenere le site (solutions.generated.js) ET l'Excel
  python3 scripts/build.py --from-json    # cas rare : tu as edite directement le JSON (sans l'Excel)
                                          #   -> regenere site + Excel depuis le JSON, sans lire l'Excel

Ce script ne fait qu'enchainer les scripts specialises (xlsx_to_json / build_app_data / build_master_xlsx).
Le detail du flux est dans scripts/README.md.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script, label):
    print(f"-> {label}")
    subprocess.run([sys.executable, str(HERE / script)], check=True)


def main():
    # Par defaut on part de l'Excel (source de verite). --from-json saute cette etape.
    from_json = "--from-json" in sys.argv[1:]
    if not from_json:
        run("xlsx_to_json.py", "Excel -> JSON (l'Excel est la source de verite)")
    run("build_app_data.py", "JSON -> site (data/solutions.generated.js)")
    run("build_master_xlsx.py", "JSON -> Excel (data/solutions_master.xlsx)")
    print("OK : site et Excel a jour.")


if __name__ == "__main__":
    main()
