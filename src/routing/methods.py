"""Edge-cost functions: length_only, mountain_penalty and the withheld traceform.

mountain_penalty: Nakaya, Fujino, He & Narumi, "4D Leaf Circuits", SCF '25, Alg. 1.
"""
from __future__ import annotations

import math
from typing import Callable

from routing.graph import CREASE, INTRA, SEAM, VIA, Edge, RoutingGraph

WeightFn = Callable[[Edge], float]


def make_weight(method: str, graph: RoutingGraph, cfg: dict) -> WeightFn:
    seam_cost = cfg["routing"]["seam_cost_mm"]
    via_cost = cfg["routing"].get("sides", {}).get("via_cost_mm", 0.0)
    diagonal = graph.diagonal

    def fixed(e: Edge) -> float:
        """Fabrication costs every method pays alike: a taped seam joint, a via."""
        if e.kind == SEAM:
            return seam_cost
        if e.kind == VIA:
            return via_cost
        return 0.0

    if method == "traceform":
        # traceform cost is withheld. Without traceform_impl, fail with no substitute.
        try:
            from routing import traceform_impl
        except ImportError:
            raise ValueError(
                "the traceform router is not part of this repository; "
                "see README. length_only and mountain_penalty reproduce "
                "from source, traceform does not.")
        return make_weight(traceform_impl.secondary_method(cfg), graph, cfg)

    if method == "length_only":
        def w_length(e: Edge) -> float:
            return e.length + fixed(e)
        return w_length

    if method == "mountain_penalty":
        params = cfg["methods_params"]["mountain_penalty"]
        penalty = diagonal * params["diagonal_multiplier"]
        steep = math.radians(params["steep_valley_deg"])

        def w_mountain(e: Edge) -> float:
            base = e.length + fixed(e)
            if e.kind in (INTRA, VIA):
                return base
            if e.theta > 0.0:
                return base + penalty
            if abs(e.theta) > steep:
                # A valley folded past closure lies back on itself and can short.
                return base + penalty
            return base
        return w_mountain

    raise ValueError(f"unknown routing method: {method}")
