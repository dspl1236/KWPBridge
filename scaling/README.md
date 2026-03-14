# KWPBridge Scaling Presets

Advanced Measuring Block channel presets from the VCDS distribution.

---

## .a01 / .a03 — Channel Preset Files

Define which measuring block groups and cells to poll together for a
specific diagnostic task. Format: `group,cell` one per line.

| File | Groups | Use case |
|------|--------|---------|
| `Diesel - Air Mass, Boost Control & Limitations.a01` | 3,8,11 | TDI boost/MAF diagnosis |
| `Diesel - Coolant, Injection Start, Supply Duration & Torsion Angle.a01` | 1,4 | TDI fuelling |
| `Diesel - Idle Control, Valve Status & Switch Times.a01` | 13,18,23 | TDI idle |
| `Diesel - Limitations & Air Values.a01` | 8,10 | TDI limits |
| `Gasoline (2.0 TFSI) - Boost and Fueling Diagnosis.a01` | 1,54,101,114,115 | TFSI boost/fuel |
| `Gasoline (2.0 TFSI) - Boost, EGT and Timing Diagnosis.a01` | 1,54,31,112,115 | TFSI boost/timing |
| `Gasoline (2.0 TFSI) - Detailed Timing Diagnosis.a01` | 1,54,114,112,31,20 | TFSI timing |
| `Gasoline (2.0 TFSI) - General Diagnosis.a01` | 1,54,101,3,11,114 | TFSI general |
| `Gasoline (2.0 TFSI) - Load, Operating Status & Fuel Pressure Regulation.a01` | 5,103,230 | TFSI load |
| `Gasoline (2.0 TFSI) - MAF Load-Specific Diagnosis.a01` | 1,54,101,114,115 | TFSI MAF |
| `Gasoline (2.0 TFSI) - Misfire-Specific Diagnosis.a01` | 1,54,115,3,230,15,16 | TFSI misfire |
| `Gasoline - 4 Cylinder - Misfire Recognition.a01` | 15,16,18 | 4-cyl misfire |
| `Gasoline - Air Mass or Manifold Pressure, Knock Control & Boost Control.a01` | 1,20,115 | Gas general |
| `Wheel Speed, Switches & Sensors.a03` | 1,3,4 | Wheel speed |

---

## OBD.SCL — Formula Scaling Definitions

Defines display min/max ranges per formula byte for gauge scaling.
Format: `formula_byte, min, max` (approximately).

Used by KWPBridge to set gauge ranges automatically when displaying
measuring block values.
