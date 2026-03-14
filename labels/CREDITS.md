# Label File Credits

Label files (`.lbl`) in this directory are plain-text community-authored
files distributed with VCDS. They are **not** Ross-Tech's encrypted `.clb`
files and are not Ross-Tech's proprietary work.

Authors are credited in each file's comment header (lines starting with `;`).
KWPBridge includes a curated subset of community-written files for the ECUs
it directly supports. All other label files can be sourced from your VCDS
installation at:

```
Windows: C:\Ross-Tech\VCDS\Labels\
         C:\VCDS\Labels\
```

KWPBridge will automatically use label files from your VCDS installation
if you configure the path via `--labels-path` or in the GUI settings.

---

## Included Files

| File | ECU | Engine | Author |
|------|-----|--------|--------|
| 893-906-266-D.lbl | 893906266D (MMS05C) | 7A 2.3 20v | schorsch9999 |

---

## Adding Label Files

To add a label file:
1. Copy the `.lbl` file to this directory
2. Filename must match the ECU part number: `893-906-266-D.lbl`
3. KWPBridge auto-detects and loads it on next connection

---

## Ross-Tech

[Ross-Tech](https://www.ross-tech.com) makes the HEX+KKL and HEX-NET
diagnostic interfaces that KWPBridge is designed to work with.
Their VCDS software is the reference implementation for KWP1281 diagnostics
on VAG vehicles. KWPBridge is not affiliated with or endorsed by Ross-Tech.

The genuine Ross-Tech cable is the **recommended** interface for KWPBridge —
it handles the 5-baud K-line initialisation in hardware, making connections
significantly more reliable than generic KKL cables.

If you find KWPBridge useful, consider buying a genuine Ross-Tech cable.
