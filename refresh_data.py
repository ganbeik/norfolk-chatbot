"""Refresh the chatbot's data after rerunning the analysis notebook.

Usage:
    python refresh_data.py <norfolk_questions_outputs folder> [<NFK-Data-final-2017-2025 redacted.csv>]

Copies dashboard_data.json into ./data. If the CSV is given, rebuilds the crime-code glossary
(most common charge descriptions recorded under each crime-type code). Agency names are kept
from the existing glossary, because the CSV has agency codes only.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"


def clean(desc: str) -> str:
    desc = re.sub(r"\s+c\d+[A-Z]?\s*[?§].*$", "", desc)   # drop the statute citation
    return re.sub(r"\s+", " ", desc.replace("*", "")).strip().title()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    outputs = Path(sys.argv[1])
    src = outputs / "dashboard_data.json"
    if not src.is_file():
        sys.exit(f"{src} not found. Run the notebook first.")
    DATA.mkdir(exist_ok=True)
    shutil.copy(src, DATA / "dashboard_data.json")
    print(f"Copied {src}")

    old = {}
    gpath = DATA / "glossary.json"
    if gpath.exists():
        old = json.loads(gpath.read_text(encoding="utf-8"))
    if len(sys.argv) > 2:
        csv = Path(sys.argv[2])
        d = pd.read_csv(csv, encoding="cp1252", dtype=str, keep_default_na=False)
        crime = {}
        for code, sub in d.groupby("Crime Type"):
            if not code.strip():
                continue
            top = sub["Desc Chrg"].map(clean).value_counts()
            crime[code] = {"rows": int(len(sub)),
                           "top_charges": [f"{k} ({v / len(sub):.0%})" for k, v in top.head(3).items()]}
        old["crime_codes"] = crime
        print(f"Rebuilt glossary for {len(crime)} crime codes from {csv.name}")
    gpath.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf-8")
    print("Done. Restart the app to load the new data.")


if __name__ == "__main__":
    main()
