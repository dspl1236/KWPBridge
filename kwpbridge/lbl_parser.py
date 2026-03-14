"""
KWPBridge .lbl file parser.

Parses Ross-Tech / VCDS-format label files (.lbl) into structured data.

File format (plain text, latin-1 encoding):
  ; comment lines
  group,cell,label[,note1[,note2,...]]   — measuring block cell definition
  Cn,value = description                 — coding value
  A,channel,label[,note1[,note2,...]]    — adaptation channel
  Basic settings lines vary by ECU

Notes often encode formulas in plain text, e.g.:
  "Anzeige mal 25 = U/min."  → multiply by 25, unit = RPM
  "Anzeigewert mal 1.33 = °v.OT"  → multiply by 1.33, unit = ° BTDC
  "Anzeige minus 50 = °C"  → subtract 50, unit = °C

The parser extracts labels, notes, and attempts to parse formula hints
from the note text so gauges can display meaningful values.

Label file location (Windows VCDS install):
  C:\\Ross-Tech\\VCDS\\Labels\\  or  C:\\VCDS\\Labels\\
  Filename: {part-number}.lbl  e.g. 893-906-266-D.lbl

Community label files are user-authored and distributed with VCDS.
Authors are credited in file comment headers. KWPBridge includes a
curated subset; see labels/CREDITS.md for attribution.
"""

import re
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CellDef:
    """Definition for one measuring block cell."""
    group:    int
    cell:     int
    label:    str
    notes:    list[str]        = field(default_factory=list)
    formula:  Callable | None  = None    # decoded from note text if possible
    unit:     str              = ""
    min_val:  float | None     = None    # from note text (spec range)
    max_val:  float | None     = None


@dataclass
class CodingValue:
    """One coding option."""
    index:       int
    value:       str     # raw coding value string
    description: str


@dataclass
class AdaptChannel:
    """One adaptation channel."""
    channel:  int
    label:    str
    notes:    list[str] = field(default_factory=list)


@dataclass
class LBLFile:
    """
    Parsed contents of a .lbl file.

    cells:    {group: {cell: CellDef}}
    coding:   list of CodingValue
    adapt:    {channel: AdaptChannel}
    meta:     dict of header comments (part_number, author, etc.)
    """
    part_number:  str
    filename:     str
    meta:         dict[str, str]                    = field(default_factory=dict)
    cells:        dict[int, dict[int, CellDef]]     = field(default_factory=dict)
    coding:       list[CodingValue]                 = field(default_factory=list)
    adapt:        dict[int, AdaptChannel]           = field(default_factory=dict)

    def get_label(self, group: int, cell: int) -> str:
        """Get label for a group/cell, or a generic fallback."""
        return (self.cells.get(group, {})
                          .get(cell, CellDef(group, cell, f"Group {group} Cell {cell}"))
                          .label)

    def get_cell(self, group: int, cell: int) -> CellDef | None:
        return self.cells.get(group, {}).get(cell)

    def groups(self) -> list[int]:
        return sorted(self.cells.keys())

    def summary(self) -> str:
        n_cells  = sum(len(c) for c in self.cells.values())
        n_groups = len(self.cells)
        return (f"{self.part_number}  {n_groups} groups  "
                f"{n_cells} cells  {len(self.coding)} coding values")


# ---------------------------------------------------------------------------
# Formula hint parser
# ---------------------------------------------------------------------------

# Patterns found in 7A and other MMS ECU label files
_FORMULA_PATTERNS = [
    # "Anzeige mal 25 = U/min."  → ×25, RPM
    (re.compile(r'mal\s+([\d.]+)\s*=\s*(.+)', re.I),
     lambda m: (float(m.group(1)), m.group(2).strip())),
    # "Anzeigewert mal 1.33 = °v.OT"
    (re.compile(r'anzeigewert\s+mal\s+([\d.]+)\s*=\s*(.+)', re.I),
     lambda m: (float(m.group(1)), m.group(2).strip())),
    # "Anzeige minus 50 = °C"  → -50 offset
    (re.compile(r'minus\s+([\d.]+)\s*=\s*(.+)', re.I),
     lambda m: (-float(m.group(1)), m.group(2).strip())),
    # "Anzeige plus 50 = ..."  → +50 offset (rare)
    (re.compile(r'plus\s+([\d.]+)\s*=\s*(.+)', re.I),
     lambda m: (float(m.group(1)), m.group(2).strip())),
    # "x 0.1 = bar"
    (re.compile(r'x\s+([\d.]+)\s*=\s*(.+)', re.I),
     lambda m: (float(m.group(1)), m.group(2).strip())),
]

# Unit cleanup map
_UNIT_MAP = {
    'u/min': 'RPM', 'rpm': 'RPM',
    '°c': '°C', 'grad c': '°C', '°c': '°C',
    '°v.ot': '° BTDC', '°vor ot': '° BTDC', 'grad vor ot': '° BTDC',
    'v': 'V', 'volt': 'V',
    'ms': 'ms', 'msec': 'ms',
    '%': '%', 'prozent': '%',
    'bar': 'bar', 'mbar': 'mbar',
    'km/h': 'km/h', 'mph': 'mph',
    'nm': 'Nm',
    'lambda': 'λ', 'λ': 'λ',
    'mg/hub': 'mg/stroke',
    'g/s': 'g/s', 'kg/h': 'kg/h',
}


def _parse_formula_hint(notes: list[str]) -> tuple[Callable | None, str]:
    """
    Try to extract a formula callable and unit from note text.

    Returns (formula_fn, unit) or (None, "").
    formula_fn: callable(raw_value) -> decoded_value
    """
    for note in notes:
        for pattern, extractor in _FORMULA_PATTERNS:
            m = pattern.search(note)
            if m:
                try:
                    factor_or_offset, unit_raw = extractor(m)
                    unit = _clean_unit(unit_raw)

                    # Determine if it's multiply or offset
                    if 'minus' in note.lower() or 'plus' in note.lower():
                        # Offset formula: value = raw + offset
                        offset = factor_or_offset
                        fn = lambda raw, off=offset: raw + off
                    else:
                        # Multiply formula: value = raw * factor
                        factor = factor_or_offset
                        fn = lambda raw, f=factor: raw * f

                    return fn, unit
                except Exception:
                    continue
    return None, ""


def _clean_unit(unit_raw: str) -> str:
    """Normalise unit string."""
    u = unit_raw.strip().rstrip('.').strip()
    return _UNIT_MAP.get(u.lower(), u)


def _parse_spec_range(notes: list[str]) -> tuple[float | None, float | None]:
    """
    Try to extract a min/max spec range from note text.
    e.g. "135 bis 160 entspricht 85 bis 110 °C"
    or   "Sollwert: 118 bis 138"
    """
    for note in notes:
        m = re.search(r'(\d+)\s*bis\s*(\d+)', note, re.I)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass
    return None, None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_lbl(path: str | Path) -> LBLFile:
    """
    Parse a .lbl file and return a LBLFile.

    Raises FileNotFoundError or ValueError on failure.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Label file not found: {path}")

    # Try multiple encodings — community files are often latin-1 or cp1252
    content = None
    for enc in ('latin-1', 'cp1252', 'utf-8-sig', 'utf-8'):
        try:
            content = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise ValueError(f"Could not decode {path} with any supported encoding")

    # Derive part number from filename
    stem = path.stem   # e.g. "893-906-266-D"
    part_number = stem.replace('-', '').upper()   # "893906266D"

    lbl = LBLFile(part_number=part_number, filename=path.name)
    meta: dict[str, str] = {}

    for raw_line in content.splitlines():
        line = raw_line.strip()

        # Comments — extract metadata
        if line.startswith(';'):
            _parse_comment_meta(line, meta)
            continue

        if not line:
            continue

        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 2:
            continue

        # Coding line: C1,value = description
        if (parts[0].startswith('C') and
                len(parts[0]) >= 2 and parts[0][1:].isdigit()):
            _parse_coding_line(lbl, parts, raw_line)
            continue

        # Adaptation line: A,channel,label[,notes...]
        if parts[0].upper() == 'A' and len(parts) >= 3:
            _parse_adapt_line(lbl, parts)
            continue

        # Measuring block line: group,cell[,label[,notes...]]
        if parts[0].isdigit() and parts[1].isdigit():
            _parse_block_line(lbl, parts)
            continue

        # Anything else — ignore (basic settings etc.)

    lbl.meta = meta
    log.debug(f"Parsed {path.name}: {lbl.summary()}")
    return lbl


def _parse_comment_meta(line: str, meta: dict):
    """Extract metadata from comment lines."""
    text = line.lstrip(';').strip()
    if not text:
        return
    # Look for key patterns
    patterns = [
        (r'steuerger[äa]tenummer\s+([\w-]+)', 'part_number'),
        (r'geschrieben von\s+(.+)',            'author'),
        (r'motor\s+\((.+?)\)',                 'engine'),
        (r'motorkennbuchstabe\s+(\w+)',         'engine_code'),
        (r'version\s*:?\s*([\d.]+)',            'version'),
        (r'datum\s*:?\s*(.+)',                  'date'),
        (r'letzte.{0,20}nderung\s*:?\s*(.+)',  'last_modified'),
    ]
    for pattern, key in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            meta[key] = m.group(1).strip()


def _parse_coding_line(lbl: LBLFile, parts: list[str], raw_line: str):
    """Parse a coding value line: C1,00 = für Motor mit..."""
    try:
        idx = int(parts[0][1:])
        # Rest of line after first comma: "00 = description"
        rest = raw_line.split(',', 1)[1].strip() if ',' in raw_line else ''
        m = re.match(r'([^\s=]+)\s*=\s*(.+)', rest)
        if m:
            lbl.coding.append(CodingValue(
                index=idx,
                value=m.group(1).strip(),
                description=m.group(2).strip(),
            ))
    except (ValueError, IndexError):
        pass


def _parse_adapt_line(lbl: LBLFile, parts: list[str]):
    """Parse an adaptation line: A,channel,label[,notes...]"""
    try:
        channel = int(parts[1])
        label   = parts[2] if len(parts) > 2 else ""
        notes   = [p for p in parts[3:] if p]
        lbl.adapt[channel] = AdaptChannel(channel=channel, label=label, notes=notes)
    except (ValueError, IndexError):
        pass


def _parse_block_line(lbl: LBLFile, parts: list[str]):
    """Parse a measuring block line: group,cell[,label[,notes...]]"""
    try:
        group = int(parts[0])
        cell  = int(parts[1])
        label = parts[2] if len(parts) > 2 else ""
        notes = [p for p in parts[3:] if p]

        formula, unit = _parse_formula_hint(notes)
        min_val, max_val = _parse_spec_range(notes)

        cell_def = CellDef(
            group=group, cell=cell,
            label=label, notes=notes,
            formula=formula, unit=unit,
            min_val=min_val, max_val=max_val,
        )

        if group not in lbl.cells:
            lbl.cells[group] = {}
        lbl.cells[group][cell] = cell_def

    except (ValueError, IndexError):
        pass


# ---------------------------------------------------------------------------
# Label file discovery and registry
# ---------------------------------------------------------------------------

class LBLRegistry:
    """
    Registry of loaded .lbl files.

    Searches a directory (or list of directories) for .lbl files and
    loads them on demand. Caches loaded files.

    Default search paths:
      1. KWPBridge/labels/  (bundled community files)
      2. User-specified path (e.g. C:\\VCDS\\Labels\\)
    """

    def __init__(self, search_paths: list[str | Path] = None):
        self._search_paths: list[Path] = []
        self._cache: dict[str, LBLFile] = {}   # part_number → LBLFile

        # Always include bundled labels dir
        bundled = Path(__file__).parent.parent / "labels"
        if bundled.exists():
            self._search_paths.append(bundled)

        if search_paths:
            for p in search_paths:
                p = Path(p)
                if p.exists():
                    self._search_paths.append(p)

    def add_path(self, path: str | Path):
        """Add a search path (e.g. user's VCDS Labels folder)."""
        p = Path(path)
        if p.exists() and p not in self._search_paths:
            self._search_paths.append(p)
            # Clear cache so newly added files are found
            self._cache.clear()
            log.info(f"Added label search path: {p}")

    def get(self, part_number: str) -> LBLFile | None:
        """
        Load and return the LBL file for a given ECU part number.

        Tries several filename formats:
          893-906-266-D.lbl   (dashes)
          893906266D.lbl      (no dashes)
          893-906-266-d.lbl   (lowercase)
        """
        pn = part_number.upper().replace('-', '')
        if pn in self._cache:
            return self._cache[pn]

        # Generate candidate filenames
        candidates = self._make_candidates(pn)

        for search_path in self._search_paths:
            for name in candidates:
                full = search_path / name
                if full.exists():
                    try:
                        lbl = parse_lbl(full)
                        self._cache[pn] = lbl
                        log.info(f"Loaded label file: {full.name} → {lbl.summary()}")
                        return lbl
                    except Exception as e:
                        log.warning(f"Failed to parse {full}: {e}")

        log.debug(f"No label file found for {part_number}")
        return None

    def _make_candidates(self, pn: str) -> list[str]:
        """Generate candidate filenames for a part number."""
        # Insert dashes: 893906266D → 893-906-266-D
        dashed = _insert_dashes(pn)
        candidates = []
        for name in [dashed, pn]:
            candidates.append(f"{name}.lbl")
            candidates.append(f"{name.lower()}.lbl")
            candidates.append(f"{name}.LBL")
        return candidates

    def available(self) -> list[str]:
        """Return list of part numbers with label files available."""
        found = []
        for search_path in self._search_paths:
            for f in search_path.glob("*.lbl"):
                pn = f.stem.replace('-', '').upper()
                if pn not in found:
                    found.append(pn)
            for f in search_path.glob("*.LBL"):
                pn = f.stem.replace('-', '').upper()
                if pn not in found:
                    found.append(pn)
        return sorted(found)

    def stats(self) -> dict:
        return {
            "search_paths": [str(p) for p in self._search_paths],
            "cached":       list(self._cache.keys()),
            "available":    len(self.available()),
        }


def _insert_dashes(pn: str) -> str:
    """
    Convert a plain part number to dashed filename format.
    893906266D → 893-906-266-D
    4A0906266  → 4A0-906-266
    078906266  → 078-906-266
    Handles variable-length VAG part numbers.
    """
    # VAG format is typically NNN-NNN-NNN-X or NNA-NNN-NNN
    # Try to split at known boundaries
    pn = pn.upper()

    # Most common: 3-3-3-1 (e.g. 893-906-266-D)
    m = re.match(r'^(\w{3})(\d{3})(\d{3})([A-Z]?)$', pn)
    if m:
        parts = [g for g in m.groups() if g]
        return '-'.join(parts)

    # 3-3-3 (e.g. 078-906-266)
    m = re.match(r'^(\w{3})(\d{3})(\d{3})$', pn)
    if m:
        return '-'.join(m.groups())

    # Fallback: just return as-is
    return pn


# ---------------------------------------------------------------------------
# Convenience: decode a raw cell value using LBL formula
# ---------------------------------------------------------------------------

def decode_with_lbl(lbl: LBLFile, group: int, cell: int,
                    raw_value: float) -> tuple[float, str, str]:
    """
    Decode a raw measuring block cell value using LBL formula hints.

    Returns (decoded_value, unit, display_string).
    Falls back to raw value if no formula available.
    """
    cell_def = lbl.get_cell(group, cell) if lbl else None

    if cell_def and cell_def.formula:
        try:
            decoded = cell_def.formula(raw_value)
            unit    = cell_def.unit
            display = f"{decoded:.1f} {unit}".strip()
            return decoded, unit, display
        except Exception:
            pass

    # No formula — return raw
    return raw_value, "", f"{raw_value:.0f}"
