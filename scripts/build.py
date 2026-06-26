#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point d'entree UNIQUE du pipeline de donnees CyberPanorama.

Deux usages, selon ce que tu as edite :

  python3 scripts/build.py                # sens direct : tu as edite data/solutions.json
                                          #   -> regenere le site (solutions.generated.js) ET l'Excel
  python3 scripts/build.py --from-excel   # sens inverse : tu as edite data/solutions_master.xlsx
                                          #   -> reinjecte dans les JSON, puis regenere site + Excel

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
    from_excel = "--from-excel" in sys.argv[1:]
    if from_excel:
        run("xlsx_to_json.py", "Excel -> JSON (reinjection des modifications de l'Excel)")
    run("build_app_data.py", "JSON -> site (data/solutions.generated.js)")
    run("build_master_xlsx.py", "JSON -> Excel (data/solutions_master.xlsx)")
    print("OK : site et Excel a jour.")


if __name__ == "__main__":
    main()
