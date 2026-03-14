# KWPBridge Label Files

VCDS-compatible `.lbl` label files for KWP1281 ECU modules.

These files provide human-readable names for measuring block groups and cells,
coding values, and adaptation channel descriptions for specific ECU part numbers.

---

## Format

Plain text, `latin-1` encoding. Lines starting with `;` are comments.

```
group, cell, label [, notes1 [, notes2]]
```

- `group` = measuring block group number (0-based on older ECUs)
- `cell`  = cell index within the group (1-4 typically)
- `label` = human-readable name
- `notes` = optional range / formula / specification text

Coding lines: `C1,value = description`

---

## Included Files

| File | ECU | Engine | Notes |
|------|-----|--------|-------|
| `893-906-266-D.lbl` | 893906266D | 7A 2.3 20v | MMS05C late 4-plug. Community file by schorsch9999. |

---

## Adding Label Files

Label files use the ECU part number as the filename with dashes:
`893-906-266-D.lbl` → ECU `893906266D`

Place `.lbl` files in this directory. KWPBridge will automatically find and
load the correct file when an ECU with a matching part number connects.

**Where to get label files:**
- Your VCDS installation: `C:\Ross-Tech\VCDS\Labels\` (Windows)
- Ross-Tech website: https://www.ross-tech.com/vag-com/labels.php
- Community contributions welcome via pull request

**Format:** Only the older plain-text `.lbl` format is supported.
The newer encrypted `.clb` format (Ross-Tech proprietary) is not supported
and should not be included in this repository.

---

## Credits

Label files in this directory are community-created contributions.
Individual file credits are noted in the file headers (`;` comment lines).

The `.lbl` file format specification was published by Ross-Tech LLC.
KWPBridge is not affiliated with or endorsed by Ross-Tech LLC.

Recommended diagnostic cable: **Ross-Tech HEX+KKL** — handles 5-baud K-line
init in hardware and is the most reliable option for KWP1281 communication.
https://www.ross-tech.com
