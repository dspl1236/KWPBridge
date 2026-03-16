"""
KWPBridge data models.
"""

from dataclasses import dataclass, field
from typing      import Any
import time


@dataclass
class MeasuringCell:
    """Single value within a measuring block group."""
    index:    int          # 1-4
    formula:  int          # raw formula byte from ECU
    raw_a:    int          # raw byte A
    raw_b:    int          # raw byte B
    value:    float        # decoded value
    unit:     str          # unit string
    display:  str          # formatted display string
    label:    str = ""     # label from ECU definition (if known)


@dataclass
class MeasuringBlock:
    """One measuring block group (4 cells)."""
    group:     int                       # group number (1-255)
    cells:     list[MeasuringCell]       # up to 4 cells
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "group":     self.group,
            "timestamp": self.timestamp,
            "cells":     [
                {
                    "index":   c.index,
                    "formula": c.formula,
                    "value":   c.value,
                    "unit":    c.unit,
                    "display": c.display,
                    "label":   c.label,
                }
                for c in self.cells
            ],
        }

    def get(self, cell_index: int) -> MeasuringCell | None:
        """Get cell by 1-based index."""
        for c in self.cells:
            if c.index == cell_index:
                return c
        return None


@dataclass
class FaultCode:
    """A single DTC (Diagnostic Trouble Code) from the ECU."""
    code:        int         # raw 2-byte fault code
    status:      int         # status byte
    description: str = ""    # human-readable description (from ECU def)

    @property
    def code_str(self) -> str:
        """Format as VAG fault code string e.g. '00515'."""
        return f"{self.code:05d}"

    @property
    def status_str(self) -> str:
        """Human-readable status."""
        statuses = []
        if self.status & 0x01: statuses.append("intermittent")
        if self.status & 0x02: statuses.append("current")
        if self.status & 0x04: statuses.append("stored")
        if self.status & 0x08: statuses.append("warning light")
        return ", ".join(statuses) if statuses else f"0x{self.status:02X}"

    def as_dict(self) -> dict:
        return {
            "code":        self.code,
            "code_str":    self.code_str,
            "status":      self.status,
            "status_str":  self.status_str,
            "description": self.description,
        }


@dataclass
class ECUIdentification:
    """ECU identification strings received on connection."""
    part_number:  str = ""    # e.g. "893906266D"
    component:    str = ""    # e.g. "2.3 20V MOTRONIC"
    extra:        list[str] = field(default_factory=list)
    coding:       str = ""
    wsc:          str = ""    # workshop code

    def as_dict(self) -> dict:
        return {
            "part_number": self.part_number,
            "component":   self.component,
            "extra":       self.extra,
            "coding":      self.coding,
            "wsc":         self.wsc,
        }


@dataclass
class BridgeState:
    """
    Complete snapshot of KWPBridge state — broadcast to all clients.
    """
    connected:       bool                          = False
    ecu_address:     int                           = 0x00
    ecu_id:          ECUIdentification | None      = None
    groups:          dict[int, MeasuringBlock]     = field(default_factory=dict)
    faults:          list[FaultCode]               = field(default_factory=list)
    fault_count:     int                           = 0
    cable_type:      str                           = ""
    port:            str                           = ""
    error:           str                           = ""
    protocol:        str                           = ""   # "kwp1281" / "kwp2000" / ""
    detect_status:   str                           = ""   # live detection progress message
    timestamp:       float                         = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "connected":      self.connected,
            "ecu_address":    self.ecu_address,
            "ecu_id":         self.ecu_id.as_dict() if self.ecu_id else None,
            "groups":         {k: v.as_dict() for k, v in self.groups.items()},
            "faults":         [f.as_dict() for f in self.faults],
            "fault_count":    self.fault_count,
            "cable_type":     self.cable_type,
            "port":           self.port,
            "error":          self.error,
            "protocol":       self.protocol,
            "detect_status":  self.detect_status,
            "timestamp":      self.timestamp,
        }
