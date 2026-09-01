"""Assemble one CSV row per instance, and the per-trace detail file."""
from __future__ import annotations

import math
import statistics
from typing import Dict, List, Sequence

from fold.unfold import FlatPattern
from layouts import Layout
from routing.graph import RoutingGraph
from routing.router import RouteResult
from validate import ValidationReport

COLUMNS = [
    # identity
    "model_id", "layout_id", "routing_method",
    # geometry -- fixed by the model, identical across layouts and methods
    "face_count", "crease_count", "cut_count",
    "triangle_count", "cycle_count",
    # circuit -- fixed by the layout, identical across methods
    "component_count", "net_count", "terminal_count",
    # routing outcome
    "connected_terminals", "stranded_terminals", "total_trace_length_mm",
    "tensile_crossing_count", "compression_crossing_count",
    "sum_predicted_tensile_strain", "maximum_predicted_tensile_strain",
    # added outcome columns
    "crossing_count", "seam_crossing_count", "side_transition_count",
    "sum_predicted_compressive_strain", "mean_predicted_tensile_strain",
    "nets_fully_connected", "max_fold_angle_deg_crossed",
    # constraint checks -- from the validator, not the router
    "cut_violation_count", "clearance_violation_count",
    "short_pair_count", "keepout_violation_count", "min_separation_mm",
    # discretisation provenance
    "routing_graph_node_count", "routing_graph_edge_count",
    "sheet_area_mm2", "grid_pitch_mm", "pattern_diagonal_mm",
    # timing
    "runtime_ms", "runtime_ms_stdev", "nodes_expanded",
    # provenance
    "mesh_sha256", "config_hash", "seed",
]

TRACE_COLUMNS = [
    "net", "connected", "length_mm", "segment_count",
    "panel_sequence", "fold_sequence",
    "crossing_kind", "crossing_fold_id", "crossing_theta_deg",
    "crossing_predicted_strain", "crossing_x_mm", "crossing_y_mm",
]


def _round(x: float, n: int = 4) -> float:
    """Round for the CSV so two runs on different machines agree bit for bit."""
    if x is None or (isinstance(x, float) and math.isinf(x)):
        return ""
    return round(x, n)


def build_row(model_id: str, layout_id: str, method: str, flat: FlatPattern,
              layout: Layout, graph: RoutingGraph, result: RouteResult,
              report: ValidationReport, runtimes: Sequence[float],
              cfg: dict, mesh_sha: str, config_hash: str) -> Dict[str, object]:
    crossings = [c for tr in result.traces for c in tr.crossings]
    tensile = [c for c in crossings if c.strain > 0]
    compressive = [c for c in crossings if c.strain < 0]
    seam_cross = [c for c in crossings if c.kind == "seam"]

    stranded = len(result.stranded)
    connected = layout.terminal_count - stranded
    fully = sum(1 for tr in result.traces
                if tr.connected and tr.net not in report.disconnected_nets)

    return {
        "model_id": model_id,
        "layout_id": layout_id,
        "routing_method": method,

        "face_count": len(flat.polygons),
        "crease_count": len(flat.creases),
        "cut_count": len(flat.seams),
        "triangle_count": len(flat.panel_mesh.mesh.faces),
        "cycle_count": flat.cycle_count,

        "component_count": layout.component_count,
        "net_count": layout.net_count,
        "terminal_count": layout.terminal_count,

        "connected_terminals": connected,
        "stranded_terminals": stranded,
        "total_trace_length_mm": _round(sum(t.length_mm for t in result.traces), 3),
        "tensile_crossing_count": len(tensile),
        "compression_crossing_count": len(compressive),
        "sum_predicted_tensile_strain": _round(sum(c.strain for c in tensile), 6),
        "maximum_predicted_tensile_strain": _round(
            max((c.strain for c in tensile), default=0.0), 6),

        "crossing_count": len(crossings),
        "seam_crossing_count": len(seam_cross),
        "side_transition_count": sum(t.via_count for t in result.traces),
        "sum_predicted_compressive_strain": _round(
            sum(c.strain for c in compressive), 6),
        "mean_predicted_tensile_strain": _round(
            (sum(c.strain for c in tensile) / len(tensile)) if tensile else 0.0, 6),
        "nets_fully_connected": fully,
        "max_fold_angle_deg_crossed": _round(
            max((abs(c.theta_deg) for c in crossings), default=0.0), 3),

        "cut_violation_count": report.cut_violation_count,
        "clearance_violation_count": report.clearance_violation_count,
        "short_pair_count": report.short_pair_count,
        "keepout_violation_count": report.keepout_violation_count,
        "min_separation_mm": _round(report.min_separation_mm, 4),

        "routing_graph_node_count": graph.node_count,
        "routing_graph_edge_count": graph.edge_count,
        "sheet_area_mm2": _round(cfg["sheet"]["area_mm2"], 1),
        "grid_pitch_mm": cfg["routing"]["grid_pitch_mm"],
        "pattern_diagonal_mm": _round(flat.diagonal, 3),

        "runtime_ms": _round(statistics.median(runtimes), 3),
        "runtime_ms_stdev": _round(
            statistics.stdev(runtimes) if len(runtimes) > 1 else 0.0, 3),
        "nodes_expanded": result.nodes_expanded,

        "mesh_sha256": mesh_sha,
        "config_hash": config_hash,
        "seed": cfg["seed"],
    }


def build_trace_rows(result: RouteResult,
                     report: ValidationReport) -> List[Dict[str, object]]:
    """Per-trace detail: one row per crossing, one row for a trace with none."""
    rows: List[Dict[str, object]] = []
    for tr in result.traces:
        # The path as a face/fold sequence.  Listing the lattice edges instead
        # would be some eighty indices per net -- the discretisation, not the
        # route.  The panels crossed and the folds crossed are the route.
        base = {
            "net": tr.net,
            "connected": int(tr.connected and tr.net not in report.disconnected_nets),
            "length_mm": _round(tr.length_mm, 3),
            "segment_count": len(tr.edges),
            "panel_sequence": " ".join(str(p) for p in tr.panels),
            "fold_sequence": " ".join(
                f"{c.kind[0].upper()}{c.fold_id}" for c in tr.crossings),
        }
        if not tr.crossings:
            rows.append({**base, "crossing_kind": "", "crossing_fold_id": "",
                         "crossing_theta_deg": "", "crossing_predicted_strain": "",
                         "crossing_x_mm": "", "crossing_y_mm": ""})
            continue
        for c in tr.crossings:
            rows.append({**base,
                         "crossing_kind": c.kind,
                         "crossing_fold_id": c.fold_id,
                         "crossing_theta_deg": _round(c.theta_deg, 3),
                         "crossing_predicted_strain": _round(c.strain, 6),
                         "crossing_x_mm": _round(c.at[0], 3),
                         "crossing_y_mm": _round(c.at[1], 3)})
    return rows
