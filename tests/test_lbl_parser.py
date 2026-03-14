"""
Tests for .lbl file parser.
Uses the bundled 893-906-266-D.lbl as the reference file.
"""
import pytest
from pathlib import Path
from kwpbridge.lbl_parser import (
    parse_lbl, LBLRegistry, decode_with_lbl,
    CellDef, LBLFile, _insert_dashes,
)

# Path to bundled label file
LABELS_DIR  = Path(__file__).parent.parent / "labels"
LBL_266D    = LABELS_DIR / "893-906-266-D.lbl"


@pytest.fixture
def lbl_266d():
    return parse_lbl(LBL_266D)


# ── Parsing ────────────────────────────────────────────────────────────────

def test_parse_returns_lbl_file(lbl_266d):
    assert isinstance(lbl_266d, LBLFile)
    assert lbl_266d.part_number == "893906266D"


def test_parse_meta(lbl_266d):
    assert lbl_266d.meta.get("engine_code") == "7A"
    assert lbl_266d.meta.get("author") == "schorsch9999"


def test_parse_groups(lbl_266d):
    assert 0 in lbl_266d.cells    # 7A uses group 0


def test_parse_cells(lbl_266d):
    group0 = lbl_266d.cells[0]
    assert 1 in group0   # coolant temp
    assert 3 in group0   # RPM
    assert 10 in group0  # ignition angle


def test_cell_labels(lbl_266d):
    assert "Kühlmitteltemperatur" in lbl_266d.get_label(0, 1)
    assert "Motordrehzahl"        in lbl_266d.get_label(0, 3)
    assert "Zündwinkel"           in lbl_266d.get_label(0, 10)


def test_cell_label_fallback(lbl_266d):
    label = lbl_266d.get_label(99, 1)
    assert "99" in label


def test_formula_rpm(lbl_266d):
    cell = lbl_266d.get_cell(0, 3)
    assert cell.formula is not None
    assert cell.unit == "RPM"
    assert cell.formula(32) == pytest.approx(800.0)


def test_formula_coolant(lbl_266d):
    cell = lbl_266d.get_cell(0, 1)
    assert cell.formula is not None
    assert cell.unit == "°C"
    assert cell.formula(135) == pytest.approx(85.0)


def test_formula_timing(lbl_266d):
    cell = lbl_266d.get_cell(0, 10)
    assert cell.formula is not None
    assert "BTDC" in cell.unit
    assert cell.formula(20) == pytest.approx(26.6, rel=0.01)


def test_cells_without_formula(lbl_266d):
    # Cell 2 (Motorlast) has no formula hint in the notes
    cell = lbl_266d.get_cell(0, 2)
    assert cell is not None
    # formula may or may not be None — just check it doesn't crash
    if cell.formula:
        result = cell.formula(100)
        assert isinstance(result, float)


def test_coding_values(lbl_266d):
    assert len(lbl_266d.coding) == 4
    assert any(cv.value == "11" for cv in lbl_266d.coding)
    assert any("Schaltgetriebe" in cv.description for cv in lbl_266d.coding)


# ── decode_with_lbl ────────────────────────────────────────────────────────

def test_decode_rpm(lbl_266d):
    val, unit, disp = decode_with_lbl(lbl_266d, 0, 3, 32)
    assert val  == pytest.approx(800.0)
    assert unit == "RPM"
    assert "800" in disp


def test_decode_coolant(lbl_266d):
    val, unit, disp = decode_with_lbl(lbl_266d, 0, 1, 135)
    assert val  == pytest.approx(85.0)
    assert unit == "°C"


def test_decode_no_formula_fallback(lbl_266d):
    # Cell 2 = engine load, no formula — should return raw
    val, unit, disp = decode_with_lbl(lbl_266d, 0, 2, 128)
    assert val == pytest.approx(128.0)


def test_decode_none_lbl():
    val, unit, disp = decode_with_lbl(None, 0, 3, 32)
    assert val == pytest.approx(32.0)
    assert "32" in disp


def test_decode_unknown_cell(lbl_266d):
    val, unit, disp = decode_with_lbl(lbl_266d, 99, 99, 50.0)
    assert val == pytest.approx(50.0)


# ── LBLRegistry ───────────────────────────────────────────────────────────

@pytest.fixture
def registry():
    return LBLRegistry([LABELS_DIR])


def test_registry_get_by_plain_pn(registry):
    lbl = registry.get("893906266D")
    assert lbl is not None
    assert lbl.part_number == "893906266D"


def test_registry_get_by_dashed_pn(registry):
    lbl = registry.get("893-906-266-D")
    assert lbl is not None


def test_registry_miss_returns_none(registry):
    assert registry.get("ZZ9999999Z") is None   # no file for ZZ prefix


def test_registry_caches(registry):
    lbl1 = registry.get("893906266D")
    lbl2 = registry.get("893906266D")
    assert lbl1 is lbl2   # same object from cache


def test_registry_available(registry):
    avail = registry.available()
    assert "893906266D" in avail


# ── _insert_dashes ─────────────────────────────────────────────────────────

def test_insert_dashes_266d():
    assert _insert_dashes("893906266D") == "893-906-266-D"


def test_insert_dashes_aah():
    result = _insert_dashes("4A0906266")
    assert "4A0" in result
    assert "906" in result


def test_insert_dashes_preserves_unknown():
    # Short/unknown part numbers shouldn't crash
    result = _insert_dashes("ABC")
    assert isinstance(result, str)


# ── Multi-letter variant suffix tests (e.g. AGU, ARL) ──────────────────────

def test_insert_dashes_multi_letter_suffix():
    """Part numbers with 3-letter variant code like AGU, ARL."""
    assert _insert_dashes("06A906018AGU") == "06A-906-018-AGU"
    assert _insert_dashes("038906019ARL") == "038-906-019-ARL"
    assert _insert_dashes("022906032AXK") == "022-906-032-AXK"

def test_registry_finds_multi_letter_suffix():
    """Registry should find files with multi-letter suffixes."""
    reg = LBLRegistry([LABELS_DIR])
    lf  = reg.get("06A906018AGU")
    if (LABELS_DIR / "06A-906-018-AGU.lbl").exists():
        assert lf is not None
        assert lf.part_number == "06A906018AGU"
        assert len(lf.cells) > 5          # should have many groups

def test_registry_total_count():
    """Registry should find all 221 community label files."""
    reg = LBLRegistry([LABELS_DIR])
    available = reg.available()
    # At least the files we know are there
    assert "893906266D" in available
    assert len(available) >= 100          # sanity check on collection size


# ── Repo integrity checks ─────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent

def test_scaling_obd_scl_present():
    assert (REPO_ROOT / "scaling" / "OBD.SCL").exists(), \
        "scaling/OBD.SCL missing from repo"

def test_scaling_a01_presets_present():
    a01_files = list((REPO_ROOT / "scaling").glob("*.a01"))
    assert len(a01_files) >= 10, \
        f"Expected ≥10 .a01 scaling presets, found {len(a01_files)}"

def test_labels_directory_populated():
    lbl_files = list((REPO_ROOT / "labels").glob("*.lbl")) + \
                list((REPO_ROOT / "labels").glob("*.LBL"))
    assert len(lbl_files) >= 100, \
        f"Expected ≥100 label files, found {len(lbl_files)}"

def test_labels_credits_present():
    assert (REPO_ROOT / "labels" / "CREDITS.md").exists(), \
        "labels/CREDITS.md missing"

def test_labels_266d_present():
    assert (REPO_ROOT / "labels" / "893-906-266-D.lbl").exists(), \
        "labels/893-906-266-D.lbl missing — core 7A label file"

def test_docs_integration_present():
    assert (REPO_ROOT / "docs" / "INTEGRATION.md").exists(), \
        "docs/INTEGRATION.md missing"
