"""Signed outer-fibre copper strain at a fold, after kiri/src/model/fold-strain.ts.

eps = (h/2 + a + t) * theta / w, with h substrate, a adhesive, t foil, w hinge width.
Mountain positive: traces crack over mountains and hold over valleys
(Nakaya, Fujino, He & Narumi, "4D Leaf Circuits", SCF '25).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SheetSpec:
    substrate_mm: float
    foil_mm: float
    adhesive_mm: float
    substrate_gpa: float
    foil_gpa: float
    fatigue_strain: float
    hinge_width_mm: float

    @classmethod
    def from_config(cls, cfg: dict) -> "SheetSpec":
        s = cfg["sheet_spec"]
        return cls(
            substrate_mm=s["substrate_mm"],
            foil_mm=s["foil_mm"],
            adhesive_mm=s.get("adhesive_mm", 0.0),
            substrate_gpa=s["substrate_gpa"],
            foil_gpa=s["foil_gpa"],
            fatigue_strain=s["fatigue_strain"],
            hinge_width_mm=s["hinge_width_mm"],
        )

    @property
    def fibre_offset_mm(self) -> float:
        """Distance from the neutral plane to the copper's outer fibre."""
        return self.substrate_mm / 2.0 + self.adhesive_mm + self.foil_mm


def bend_radius_mm(spec: SheetSpec, theta_rad: float) -> float:
    """R = w / theta.  A wider hinge or a shallower fold is a gentler bend."""
    theta = max(abs(theta_rad), 1e-9)
    return spec.hinge_width_mm / theta


def fold_strain(spec: SheetSpec, theta_rad: float) -> float:
    """Signed strain, positive in tension (mountain), negative in compression.

    Unclipped: kiri's min(1, eps/eps_fatigue) saturates near 12 degrees of fold,
    which would erase the shallow-versus-steep mountain ordering under test.
    """
    eps = spec.fibre_offset_mm / bend_radius_mm(spec, theta_rad)
    return -eps if theta_rad < 0 else eps


def max_trace_width_mm(spec: SheetSpec, hinge_len_mm: float,
                       stiffening_share: float = 0.5) -> float:
    """Max copper width before it stiffens the hinge: w <= share * L * (E_s h^3) / (E_cu t^3).

    Reported only. On the shipped sheet it sits far above the tape width.
    """
    foil = spec.foil_gpa * spec.foil_mm ** 3
    sheet = spec.substrate_gpa * spec.substrate_mm ** 3
    return (stiffening_share * max(hinge_len_mm, 0.0) * sheet) / foil
