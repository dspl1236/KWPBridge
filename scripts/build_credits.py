#!/usr/bin/env python3
"""
Build labels/CREDITS.md from the author metadata in each .lbl file header.

Run from the KWPBridge repo root:
    python scripts/build_credits.py

Reads every .lbl file in labels/, extracts the author/description from
the comment header, and generates a sorted credits table.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from kwpbridge.lbl_parser import parse_lbl

LABELS_DIR  = Path(__file__).parent.parent / "labels"
CREDITS_OUT = LABELS_DIR / "CREDITS.md"


def _header_comments(path) -> list[str]:
    """Read raw comment lines from file header (first 30 lines)."""
    comments = []
    try:
        with open(path, encoding='latin-1', errors='replace') as f:
            for i, line in enumerate(f):
                if i > 30:
                    break
                line = line.strip()
                if line.startswith(';'):
                    c = line.lstrip('; ').strip()
                    if c and not set(c) <= set('*-='):
                        comments.append(c)
    except Exception:
        pass
    return comments


def extract_author(meta: dict, comments: list[str]) -> str:
    """Extract author from meta dict or raw comment lines."""
    # Try meta dict first (parsed key=value pairs)
    for key in ('author', 'geschrieben von', 'written by', 'erstellt von'):
        if key in meta:
            return meta[key]
    # Scan raw comment lines for email or attribution markers
    for line in comments:
        low = line.lower()
        for marker in ('geschrieben von', 'written by', 'author:', 'erstellt von',
                        'created by', 'eric maurier', 'sebastian stange',
                        'copyright'):
            if marker in low:
                after = line[low.index(marker) + len(marker):].strip(' /:')
                if after and len(after) > 2:
                    return after[:50]
        # Email address = likely author contact
        if '@' in line and len(line) < 80:
            return line.split()[0][:50] if line.split() else line[:50]
    return "unknown"


def extract_description(meta: dict, comments: list[str]) -> str:
    """Extract a short description from the header."""
    for key in ('description', 'component', 'motor', 'engine', 'engine_code'):
        if key in meta:
            v = meta[key]
            if len(v) > 2:
                return v
    # Return first comment that looks like a vehicle/component description
    for line in comments:
        line = line.strip('*- ')
        if (len(line) > 8 and
                not line.lower().startswith('steuerg') and
                not line.lower().startswith('vcds') and
                not line.lower().startswith('copyright') and
                not line.lower().startswith('measuring')):
            return line[:80]
    return ""


def main():
    lbl_files = sorted(LABELS_DIR.glob("*.lbl")) + sorted(LABELS_DIR.glob("*.LBL"))

    if not lbl_files:
        print(f"No .lbl files found in {LABELS_DIR}")
        return

    rows = []
    errors = []

    for path in lbl_files:
        if path.name.lower() in ("template.lbl", "readme.lbl"):
            continue
        try:
            lbl     = parse_lbl(path)
            author  = extract_author(lbl.meta, lbl.meta.get('_comments', []))
            desc    = extract_description(lbl.meta, lbl.meta.get('_comments', []))
            n_cells = sum(len(c) for c in lbl.cells.values())
            rows.append((path.name, lbl.part_number, author, desc, n_cells))
        except Exception as e:
            errors.append((path.name, str(e)))

    # Sort by part number
    rows.sort(key=lambda r: r[1])

    # Build markdown
    lines = [
        "# KWPBridge Label File Credits",
        "",
        "Label files are community-contributed and authored by VCDS users.",
        "Authors are credited as noted in each file's header comments.",
        "",
        "The `.lbl` file format was specified by Ross-Tech LLC.",
        "KWPBridge is not affiliated with or endorsed by Ross-Tech LLC.",
        "",
        "**Recommended cable:** Ross-Tech HEX+KKL — most reliable for KWP1281.",
        "https://www.ross-tech.com",
        "",
        "---",
        "",
        f"## {len(rows)} Label Files",
        "",
        "| File | Part Number | Author | Description | Cells |",
        "|------|-------------|--------|-------------|-------|",
    ]

    for fname, pn, author, desc, n_cells in rows:
        desc_short = (desc[:50] + "…") if len(desc) > 50 else desc
        lines.append(f"| `{fname}` | {pn} | {author} | {desc_short} | {n_cells} |")

    if errors:
        lines += [
            "",
            "---",
            "",
            "## Parse Errors",
            "",
            "| File | Error |",
            "|------|-------|",
        ]
        for fname, err in errors:
            lines.append(f"| `{fname}` | {err[:80]} |")

    lines += [
        "",
        "---",
        "",
        "*This file is auto-generated by `scripts/build_credits.py`.*",
        "*Do not edit manually — run the script to regenerate.*",
        "",
    ]

    CREDITS_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {CREDITS_OUT}")
    print(f"  {len(rows)} files credited, {len(errors)} parse errors")


if __name__ == "__main__":
    main()
