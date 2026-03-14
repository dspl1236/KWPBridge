# KWPBridge Label Files

VCDS-compatible `.lbl` label files for KWP1281 ECU modules.

**221 community-authored files** covering engine ECUs, transmission,
ABS, airbag, instruments, and other VAG modules from ~1990–2010.

---

## What's Included

Only **community-authored** plain-text `.lbl` files are included.

| Category | Count | Notes |
|----------|-------|-------|
| Engine ECUs (906 in part number) | 43 | Most relevant for tuning |
| Other modules | 178 | Transmission, ABS, cluster, etc. |
| **Total** | **221** | |

**Not included:**
- Ross-Tech redirect files (645) — Ross-Tech LLC intellectual property
- Ross-Tech authored files (302) — Ross-Tech LLC intellectual property  
- Encrypted `.clb` files — Ross-Tech LLC proprietary format, never included

---

## Scaling Presets

The `../scaling/` directory contains Advanced Measuring Block presets (`.a01`):
channel combinations optimised for specific diagnostic tasks
(boost diagnosis, misfire recognition, fuel pressure, etc.).

`OBD.SCL` contains formula scaling definitions (formula byte → display range).

---

## File Format

Plain text, `latin-1` encoding. Lines starting with `;` are comments.

```
group, cell, label [, notes1 [, notes2]]
Cn, value = coding description
```

Older ECUs (Motronic 2.x, KWP1281) use 0-based group numbering.
Newer ECUs (ME7+, KWP2000) use 1-based groups.

---

## Adding Your Own Label Files

Place `.lbl` files here or point KWPBridge at your VCDS installation:

```bash
python -m kwpbridge.gui --vcds-labels "C:/Ross-Tech/VCDS/Labels"
```

KWPBridge auto-discovers VCDS on Windows at common install paths.

File naming: `{PART-NUMBER}.lbl` — e.g. `893-906-266-D.lbl` → ECU `893906266D`

---

## Credits

See `CREDITS.md` for author attribution per file.

The `.lbl` format is published by Ross-Tech LLC.
Ross-Tech HEX+KKL is the recommended cable: https://www.ross-tech.com
