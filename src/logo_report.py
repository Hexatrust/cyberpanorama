#!/usr/bin/env python3
"""
Generate an Excel recap of logo availability.

Sheets:
- recap: high-level counts.
- logos_trouves: solutions with a matching logo.
- logos_non_trouves: solutions without a matching logo.
- logos_en_trop: logo files present on disk but unused.
"""
from pathlib import Path
import sys
import pandas as pd

# Make sure we can import helpers from src.read_solutions
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.read_solutions import find_logo_for_solution  # noqa: E402

EXCEL_PATH = ROOT_DIR / "assets" / "solutions.xlsx"
LOGOS_DIR = ROOT_DIR / "assets" / "logos"
REPORT_PATH = ROOT_DIR / "assets" / "Report" / "logo_recap.xlsx"
LOGO_EXTENSIONS = {".png", ".svg", ".webp", ".jpg", ".jpeg"}


def gather_logo_status(excel_path: Path = EXCEL_PATH, logos_dir: Path = LOGOS_DIR):
    """Return logo match status for each solution and the list of extra logos."""
    df = pd.read_excel(excel_path)
    entries = []
    used_files = set()

    for _, row in df.iterrows():
        solution_name = str(row.get("Solutions", "")).strip()
        fonction_nist = row.get("Fonction NIST", "")
        taille = row.get("Taille", "")
        expected_logo = (
            str(row.get("Logo")).strip() if pd.notna(row.get("Logo")) else ""
        )

        matched_path = None
        match_source = ""

        # First, try the explicit logo path from the Excel file.
        if expected_logo:
            candidate = logos_dir / expected_logo
            if candidate.exists():
                matched_path = candidate
                match_source = "excel_logo"

        # If not found, reuse the name-based lookup from main.py/read_solutions.py.
        if matched_path is None or not matched_path.exists():
            path_str = find_logo_for_solution(
                solution_name, logos_dir=str(logos_dir)
            )
            if path_str:
                matched_path = Path(path_str)
                match_source = match_source or "name_match"

        status = "found" if matched_path else "missing"

        logo_file = matched_path.name if matched_path else ""
        if matched_path:
            try:
                logo_rel_path = str(matched_path.relative_to(ROOT_DIR))
            except ValueError:
                logo_rel_path = str(matched_path)
        else:
            logo_rel_path = ""

        if matched_path:
            used_files.add(matched_path.resolve())

        entries.append(
            {
                "solution": solution_name,
                "fonction_nist": fonction_nist,
                "taille": taille,
                "expected_logo": expected_logo,
                "logo_file": logo_file,
                "logo_path": logo_rel_path,
                "match_source": match_source,
                "status": status,
            }
        )

    logo_files = [
        p
        for p in logos_dir.iterdir()
        if p.is_file() and p.suffix.lower() in LOGO_EXTENSIONS
    ]
    extras = [p for p in logo_files if p.resolve() not in used_files]
    return entries, extras


def build_report(
    excel_path: Path = EXCEL_PATH,
    logos_dir: Path = LOGOS_DIR,
    report_path: Path = REPORT_PATH,
):
    entries, extras = gather_logo_status(excel_path=excel_path, logos_dir=logos_dir)
    df = pd.DataFrame(entries)

    found_df = df[df["status"] == "found"].copy()
    missing_df = df[df["status"] == "missing"].copy()
    extra_rows = []
    for p in extras:
        try:
            rel_path = str(p.relative_to(ROOT_DIR))
        except ValueError:
            rel_path = str(p)
        extra_rows.append({"logo_file": p.name, "logo_path": rel_path})
    extras_df = pd.DataFrame(extra_rows)

    summary_df = pd.DataFrame(
        [
            {"metric": "solutions_total", "value": len(df)},
            {"metric": "logos_trouves", "value": len(found_df)},
            {"metric": "logos_non_trouves", "value": len(missing_df)},
            {"metric": "logos_en_trop", "value": len(extras_df)},
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="recap", index=False)
        found_df.to_excel(writer, sheet_name="logos_trouves", index=False)
        missing_df.to_excel(writer, sheet_name="logos_non_trouves", index=False)
        extras_df.to_excel(writer, sheet_name="logos_en_trop", index=False)

    print(f"Report generated: {report_path}")


if __name__ == "__main__":
    build_report()
