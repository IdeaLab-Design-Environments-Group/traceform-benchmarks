"""Signed outer-fibre strain in the copper at a fold.

After kiri/src/model/fold-strain.ts, which states the model as:

    R   = w / theta                        the hinge is an arc of width w
    eps = (h/2 + t) / R = (h/2+t)*theta/w  Euler-Bernoulli outer-fibre strain

with h the substrate thickness, t the copper foil thickness, w the measured
hinge width.  Ordinary beam bending; the same quantity a flex-PCB bend-radius
rule states in its own units.

Sign is the whole point.  Nakaya, Fujino, He & Narumi ("4D Leaf Circuits",
SCF '25) measured a trace over a *mountain* rising in resistance and fracturing
inside a hundred folding cycles, while the same trace on a *valley* stayed
flat.  The geometry does not distinguish them -- |eps| is equal either way --
so a model taking |theta| would flatten that result away.  On a mountain the
copper is on the convex side and goes into tension, which opens cracks across
the trace; on a valley it is compressed, which wrinkles the foil but does not
part it.  Mountain positive, therefore, and tension is what gets charged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SheetSpec:
    substrate_mm: float
    foil_mm: float
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
            substrate_gpa=s["substrate_gpa"],
            foil_gpa=s["foil_gpa"],
            fatigue_strain=s["fatigue_strain"],
            hinge_width_mm=s["hinge_width_mm"],
        )

    @property
    def fibre_offset_mm(self) -> float:
        """Distance from the neutral plane to the copper's outer fibre."""
        return self.substrate_mm / 2.0 + self.foil_mm


def bend_radius_mm(spec: SheetSpec, theta_rad: float) -> float:
    """R = w / theta.  A wider hinge or a shallower fold is a gentler bend."""
    theta = max(abs(theta_rad), 1e-9)
    return spec.hinge_width_mm / theta


def fold_strain(spec: SheetSpec, theta_rad: float) -> float:
    """Signed strain: positive in tension (mountain), negative in compression.

    NOT clipped.  kiri charges min(1, eps/eps_fatigue), and its own wiki records
    that this ceiling is reached at about 12 degrees of fold on the default
    sheet -- past which every mountain costs the same.  Clipped, the measure is
    binary and the traceform router degenerates into the mountain_penalty
    baseline.  The ordering between a shallow and a steep mountain is exactly
    what this benchmark is testing, so it is preserved here.
    """
    eps = spec.fibre_offset_mm / bend_radius_mm(spec, theta_rad)
    return -eps if theta_rad < 0 else eps


def max_trace_width_mm(spec: SheetSpec, hinge_len_mm: float,
                       stiffening_share: float = 0.5) -> float:
    """w <= share * L * (E_s h^3) / (E_cu t^3).

    Copper is some thirty times stiffer than the substrate, so a strip laid
    across a hinge resists the fold.  Plate bending stiffness goes as E*h^3 per
    unit width; holding the copper's added share below `stiffening_share` gives
    this bound.  Reported, not enforced -- on the shipped sheet it sits two
    orders of magnitude above the tape width and never binds.
    """
    foil = spec.foil_gpa * spec.foil_mm ** 3
    sheet = spec.substrate_gpa * spec.substrate_mm ** 3
    return (stiffening_share * max(hinge_len_mm, 0.0) * sheet) / foil
