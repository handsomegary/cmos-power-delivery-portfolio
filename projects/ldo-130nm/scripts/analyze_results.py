#!/usr/bin/env python3
"""Analyze exported Spectre CSV files without requiring third-party packages.

No simulator completion or design pass is inferred from CSV presence. Optional
matplotlib plots are created only if matplotlib is already installed. Event
windows must be explicit; the script never guesses the load pulse schedule.
Run with --help for the interface and --schema for the complete input contract.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMAS = {
    "transient": ["time_s", "vout_v", "gate_v", "fb_v", "vin_v", "load_a"],
    "dc": ["vin_v", "load_a", "vout_v", "iq_a"],
    "stb": ["frequency_hz", "loop_real", "loop_imag"],
    "ac": ["frequency_hz", "vout_real", "vout_imag", "vin_real", "vin_imag"],
}
CONTRACT = {
    "csv": SCHEMAS,
    "events_json": [{
        "name": "unique event label", "edge_start_s": "number", "edge_end_s": "number",
        "pre_window_s": ["start", "end"], "post_window_s": ["start", "end"],
        "analysis_window_s": ["edge start or later", "before next edge"],
    }],
    "stb_native_json": {
        "phase_margin_deg": "number or null", "gain_margin_db": "number or null",
        "pm_frequency_hz": "number or null", "gm_frequency_hz": "number or null",
    },
    "rules": [
        "All CSV units are SI; iq_a is the supplied measured core IQ, not inferred here.",
        "A file represents one run/condition. Extra CSV columns are ignored and recorded.",
        "Rows with blank/nonfinite/invalid numbers are retained as missing observations.",
        "Time/frequency axes must be strictly increasing; never silently sorted.",
        "JSON unavailable measurements use null plus an explicit status/reason.",
        "Recovery defaults to target_v +/- target_v * tolerance_fraction.",
        "post_mean center uses the same absolute band width, only after post-window checks.",
        "No interpolation across missing observations or extrapolation beyond CSV coverage.",
        "Spectre AF convention uses critical point +1; classical T uses critical point -1.",
        "Estimated margins are not native Spectre results and are not a stability verdict.",
    ],
}


def unavailable(reason, **extra):
    return {"status": "unavailable", "reason": reason, "value": None, **extra}


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        answer = float(value)
        return answer if math.isfinite(answer) else None
    except (TypeError, ValueError):
        return None


def read_json(path):
    if not path:
        return None, "not_provided"
    try:
        with Path(path).open(encoding="utf-8-sig") as handle:
            return json.load(handle), None
    except (OSError, ValueError) as error:
        return None, str(error)


def read_csv(path, kind):
    data = {"kind": kind, "path": str(Path(path).resolve()) if path else None,
            "status": "unavailable", "rows": [], "diagnostics": []}
    if not path:
        data["reason"] = "not_provided"
        return data
    try:
        raw = Path(path).read_bytes()
        data["sha256"] = hashlib.sha256(raw).hexdigest()
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            names = reader.fieldnames or []
            data["columns"] = names
            data["missing_columns"] = [key for key in SCHEMAS[kind] if key not in names]
            data["extra_columns"] = [key for key in names if key not in SCHEMAS[kind]]
            if len(names) != len(set(names)):
                data["reason"] = "duplicate_column_names"
                return data
            for row_number, row in enumerate(reader, 2):
                if not any(value not in (None, "") for value in row.values()):
                    continue
                converted = {key: finite(row.get(key)) for key in SCHEMAS[kind]}
                converted["csv_row"] = row_number
                missing = [key for key in SCHEMAS[kind] if converted[key] is None]
                if missing:
                    data["diagnostics"].append({"csv_row": row_number, "missing_or_invalid": missing})
                if None in row:
                    data["diagnostics"].append({"csv_row": row_number, "reason": "more_fields_than_header"})
                data["rows"].append(converted)
        data["row_count"] = len(data["rows"])
        if not data["rows"]:
            data["reason"] = "no_data_rows"
        else:
            data["status"] = "partial" if data["diagnostics"] or data["missing_columns"] else "loaded"
    except (OSError, UnicodeError, csv.Error) as error:
        data["reason"] = str(error)
    return data


def series(data, xkey, ykeys, positive_x=False):
    if not data["rows"]:
        return None, data.get("reason", "no_data")
    result = []
    for row in data["rows"]:
        values = [row.get(xkey)] + [row.get(key) for key in ykeys]
        if any(value is None for value in values):
            return None, "missing_observation_in_required_channel"
        if positive_x and values[0] <= 0:
            return None, "frequency_must_be_positive"
        if result and values[0] <= result[-1][0]:
            return None, "axis_not_strictly_increasing"
        result.append(values)
    if len(result) < 2:
        return None, "insufficient_points"
    return result, None


def clipped(points, interval):
    if not isinstance(interval, list) or len(interval) != 2:
        return None, "window_must_be_a_two_element_array"
    start, stop = (finite(value) for value in interval)
    if start is None or stop is None or start >= stop:
        return None, "window_bounds_invalid"
    if start < points[0][0] or stop > points[-1][0]:
        return None, "window_outside_csv_coverage"
    xs = [point[0] for point in points]

    def at(x):
        index = bisect.bisect_left(xs, x)
        if index < len(points) and points[index][0] == x:
            return points[index][:]
        left, right = points[index - 1], points[index]
        weight = (x - left[0]) / (right[0] - left[0])
        return [x] + [a + weight * (b - a) for a, b in zip(left[1:], right[1:])]

    return [at(start)] + [point for point in points if start < point[0] < stop] + [at(stop)], None


def window_stats(points, interval):
    selected, error = clipped(points, interval)
    if error:
        return unavailable(error, window_s=interval)
    duration = selected[-1][0] - selected[0][0]
    integral = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(selected, selected[1:]))
    values = [point[1] for point in selected]
    return {"status": "computed", "window_s": interval,
            "mean_v": integral / duration, "minimum_v": min(values), "maximum_v": max(values),
            "peak_to_peak_v": max(values) - min(values),
            "endpoint_drift_v": values[-1] - values[0],
            "endpoint_slope_v_per_s": (values[-1] - values[0]) / duration,
            "sample_count_including_interpolated_bounds": len(selected),
            "maximum_sample_interval_s": max(b[0] - a[0] for a, b in zip(selected, selected[1:])),
            "mean_method": "time_weighted_trapezoidal"}


def transient_analysis(data, events, events_error, args):
    points, error = series(data, "time_s", ["vout_v"])
    if error:
        return unavailable(error, events=[])
    result = {"status": "computed", "coverage_s": [points[0][0], points[-1][0]], "events": []}
    if events_error or not isinstance(events, list) or not events:
        result["event_measurements"] = unavailable(events_error or "events_array_required")
        return result
    tolerance = abs(args.target_v) * args.tolerance_fraction
    ripple_limit = args.post_ripple_max_v if args.post_ripple_max_v is not None else tolerance
    drift_limit = args.post_drift_max_v if args.post_drift_max_v is not None else tolerance / 2
    for event in events:
        if not isinstance(event, dict):
            result["events"].append(unavailable("event_must_be_an_object"))
            continue
        item = {"name": event.get("name"), "definition": event}
        start, end = finite(event.get("edge_start_s")), finite(event.get("edge_end_s"))
        pre, post, interval = event.get("pre_window_s"), event.get("post_window_s"), event.get("analysis_window_s")
        intervals = [pre, post, interval]
        if any(not isinstance(window, list) or len(window) != 2 or
               any(finite(bound) is None for bound in window) for window in intervals):
            item.update(unavailable("all_windows_require_two_finite_numeric_bounds"))
            result["events"].append(item)
            continue
        pre, post, interval = ([finite(bound) for bound in window] for window in intervals)
        if start is None or end is None or end < start:
            item.update(unavailable("edge_times_invalid"))
            result["events"].append(item)
            continue
        selected, window_error = clipped(points, interval)
        before = window_stats(points, pre)
        after = window_stats(points, post)
        item.update({"pre_event_window": before, "post_event_window": after})
        if window_error or before["status"] != "computed" or after["status"] != "computed":
            item.update(unavailable(window_error or "pre_or_post_window_unavailable"))
            result["events"].append(item)
            continue
        if not (pre[1] <= start <= end <= post[0] < post[1] <= interval[1] and interval[0] == start):
            item.update(unavailable("windows_must_follow_pre_then_edge_then_post_and_analysis_start_at_edge"))
            result["events"].append(item)
            continue
        next_edges = [finite(other.get("edge_start_s")) for other in events if isinstance(other, dict)]
        next_edges = [value for value in next_edges if value is not None and value > start]
        if next_edges and interval[1] >= min(next_edges):
            item.update(unavailable("analysis_window_includes_the_next_known_edge"))
            result["events"].append(item)
            continue
        settled = after["peak_to_peak_v"] <= ripple_limit and abs(after["endpoint_drift_v"]) <= drift_limit
        after["settled_candidate"] = settled
        after["settling_checks"] = {"ripple_limit_v": ripple_limit, "endpoint_drift_limit_v": drift_limit}
        values = [point[1] for point in selected]
        minimum, maximum = min(values), max(values)
        item.update({"status": "computed", "minimum_v": minimum, "maximum_v": maximum,
                     "minimum_time_s": selected[values.index(minimum)][0],
                     "maximum_time_s": selected[values.index(maximum)][0],
                     "undershoot_from_target_v": max(0.0, args.target_v - minimum),
                     "overshoot_from_target_v": max(0.0, maximum - args.target_v),
                     "undershoot_from_post_mean_v": max(0.0, after["mean_v"] - minimum),
                     "overshoot_from_post_mean_v": max(0.0, maximum - after["mean_v"]),
                     "pre_to_post_mean_change_v": after["mean_v"] - before["mean_v"],
                     "post_mean_error_from_target_v": after["mean_v"] - args.target_v,
                     "edge_duration_s": end - start})
        center = args.target_v if args.recovery_center == "target" else after["mean_v"]
        recovery_points, recovery_error = clipped(points, [end, interval[1]])
        recovery = {"status": "not_settled", "value": None, "unit": "s",
                    "band_center_v": center, "band_half_width_v": tolerance,
                    "band_v": [center - tolerance, center + tolerance],
                    "method": "last_outside_sample_then_linear_boundary_interpolation",
                    "observation_end_s": interval[1]}
        if recovery_error:
            recovery = unavailable(recovery_error)
        elif not settled:
            recovery["reason"] = "post_window_ripple_or_drift_exceeds_limit"
        else:
            outside = [index for index, point in enumerate(recovery_points) if abs(point[1] - center) > tolerance]
            if outside and outside[-1] == len(recovery_points) - 1:
                recovery["reason"] = "outside_band_at_observation_end"
            else:
                if not outside:
                    recovered_at = end
                else:
                    index = outside[-1]
                    left, right = recovery_points[index], recovery_points[index + 1]
                    boundary = center + (tolerance if left[1] > center else -tolerance)
                    fraction = (boundary - left[1]) / (right[1] - left[1])
                    recovered_at = left[0] + fraction * (right[0] - left[0])
                recovery.update({"status": "computed_estimate", "value": recovered_at - end,
                                 "from_edge_end_s": recovered_at - end,
                                 "from_edge_start_s": recovered_at - start, "recovered_at_s": recovered_at,
                                 "qualification": "remains_in_band_only_until_observation_end"})
        item["recovery"] = recovery
        item["sampling"] = {"maximum_sample_interval_s": max(b[0] - a[0] for a, b in zip(selected, selected[1:])),
                            "edge_interval_count": sum(start <= point[0] <= end for point in points),
                            "numerical_convergence": "not_checked_compare_independent_runs"}
        result["events"].append(item)
    return result


def extrema(values, unit):
    if not values:
        return unavailable("no_finite_observations", unit=unit)
    return {"status": "computed", "minimum": min(values), "maximum": max(values), "unit": unit}


def dc_analysis(data, args):
    if not data["rows"]:
        return unavailable(data.get("reason", "no_data"))
    points = [row for row in data["rows"] if all(row.get(key) is not None for key in ("vin_v", "load_a", "vout_v"))]
    result = {"status": "computed" if len(points) == len(data["rows"]) else "partial",
              "operating_points": data["rows"], "target_v": args.target_v,
              "vout_error_v": extrema([row["vout_v"] - args.target_v for row in points], "V"),
              "iq_a": extrema([row["iq_a"] for row in data["rows"] if row.get("iq_a") is not None], "A"),
              "iq_definition": "input CSV must document measurement boundary and ideal bias/reference exclusion",
              "line_regulation": [], "load_regulation": [], "dropout": []}
    if any(row.get("iq_a") is not None and row["iq_a"] < 0 for row in data["rows"]):
        result["warning"] = "negative_iq_review_supply_current_sign_and_measurement_boundary"
    duplicate = len({(row["vin_v"], row["load_a"]) for row in points}) != len(points)
    for fixed_key, varied_key, label in [("vin_v", "load_a", "load_regulation"), ("load_a", "vin_v", "line_regulation")]:
        groups = {}
        for row in points:
            if args.reg_vin_min is not None and row["vin_v"] < args.reg_vin_min:
                continue
            if args.reg_vin_max is not None and row["vin_v"] > args.reg_vin_max:
                continue
            groups.setdefault(row[fixed_key], []).append(row)
        for fixed, rows in sorted(groups.items()):
            rows = sorted(rows, key=lambda row: row[varied_key])
            item = {fixed_key: fixed}
            if len(rows) < 2 or rows[0][varied_key] == rows[-1][varied_key] or duplicate:
                item.update(unavailable("duplicate_conditions" if duplicate else "insufficient_points"))
            else:
                delta = rows[-1]["vout_v"] - rows[0]["vout_v"]
                slope = delta / (rows[-1][varied_key] - rows[0][varied_key])
                item.update({"status": "computed", "slope_v_per_a" if label == "load_regulation" else "slope_v_per_v": slope,
                             "slope_mv_per_ma" if label == "load_regulation" else "slope_mv_per_v": slope if label == "load_regulation" else slope * 1000,
                             "varied_range": [rows[0][varied_key], rows[-1][varied_key]],
                             "vout_range_v": [min(row["vout_v"] for row in rows), max(row["vout_v"] for row in rows)],
                             "scope": "user_selected_vin_range" if args.reg_vin_min is not None or args.reg_vin_max is not None else "sampled_range_not_confirmed_regulation_region"})
            result[label].append(item)
    if args.dropout_fraction is None:
        result["dropout"] = unavailable("threshold_not_requested")
    else:
        groups = {}
        for row in points:
            groups.setdefault(row["load_a"], []).append(row)
        for load, rows in sorted(groups.items()):
            rows = sorted(rows, key=lambda row: row["vin_v"], reverse=True)
            item = {"load_a": load, "drop_fraction": args.dropout_fraction}
            if duplicate or len(rows) < 2:
                item.update(unavailable("duplicate_conditions" if duplicate else "insufficient_points"))
            elif abs(rows[0]["vout_v"] - args.target_v) > abs(args.target_v) * args.tolerance_fraction:
                item.update(unavailable("high_vin_baseline_outside_target_tolerance"))
            else:
                threshold = rows[0]["vout_v"] * (1 - args.dropout_fraction)
                item.update({"baseline_vin_v": rows[0]["vin_v"], "baseline_vout_v": rows[0]["vout_v"], "threshold_vout_v": threshold})
                crossing = None
                for left, right in zip(rows, rows[1:]):
                    if left["vout_v"] >= threshold > right["vout_v"]:
                        weight = (threshold - left["vout_v"]) / (right["vout_v"] - left["vout_v"])
                        vin = left["vin_v"] + weight * (right["vin_v"] - left["vin_v"])
                        crossing = {"status": "computed_estimate", "vin_at_threshold_v": vin,
                                    "dropout_v": vin - threshold, "vin_bracket_v": [right["vin_v"], left["vin_v"]]}
                        break
                item.update(crossing or unavailable("no_threshold_crossing_within_sampled_range"))
            result["dropout"].append(item)
    return result


def unwrap_phase(values):
    result = []
    for value in values:
        if result:
            while value - result[-1] > 180:
                value -= 360
            while value - result[-1] <= -180:
                value += 360
        result.append(value)
    return result


def crossings(xs, ys, level=0.0):
    found = []
    for index in range(len(xs) - 1):
        a, b = ys[index] - level, ys[index + 1] - level
        if a == 0:
            found.append((index, 0.0, xs[index]))
        elif a * b < 0:
            weight = -a / (b - a)
            found.append((index, weight, xs[index] + weight * (xs[index + 1] - xs[index])))
    if ys[-1] == level:
        found.append((len(xs) - 2, 1.0, xs[-1]))
    return found


def stb_analysis(data, native, native_error, args):
    native_result = {key: unavailable(native_error or "missing_or_nonfinite_native_metric") for key in CONTRACT["stb_native_json"]}
    if isinstance(native, dict):
        for key in native_result:
            value = finite(native.get(key))
            if value is not None:
                native_result[key] = {"status": "native_export", "value": value}
    points, error = series(data, "frequency_hz", ["loop_real", "loop_imag"], True)
    if error:
        return unavailable(error, native=native_result)
    if any(math.hypot(point[1], point[2]) == 0 for point in points):
        return unavailable("zero_complex_loop_gain_phase_undefined", native=native_result)
    logs = [math.log10(point[0]) for point in points]
    gains = [20 * math.log10(math.hypot(point[1], point[2])) for point in points]
    multiplier = -1 if args.loop_convention == "spectre" else 1
    phases = unwrap_phase([math.degrees(math.atan2(multiplier * point[2], multiplier * point[1])) for point in points])
    unity, critical = [], []
    for index, weight, log_frequency in crossings(logs, gains):
        phase = phases[index] + weight * (phases[index + 1] - phases[index])
        margin = (180 + phase + 180) % 360 - 180
        if margin == -180:
            margin = 180.0
        unity.append({"frequency_hz": 10 ** log_frequency, "phase_deg_normalized": phase,
                      "phase_margin_deg_estimate": margin if args.loop_convention != "unspecified" else None})
    if args.loop_convention != "unspecified":
        lo, hi = min(phases), max(phases)
        for k in range(math.ceil((lo + 180) / 360), math.floor((hi + 180) / 360) + 1):
            level = -180 + 360 * k
            for index, weight, log_frequency in crossings(logs, phases, level):
                gain = gains[index] + weight * (gains[index + 1] - gains[index])
                critical.append({"frequency_hz": 10 ** log_frequency, "phase_deg_normalized": level,
                                 "loop_gain_db": gain, "gain_margin_db_estimate": -gain})
    result = {"status": "computed_estimates", "loop_convention": args.loop_convention,
              "native": native_result, "preferred_margin_source": "native_export_when_available",
              "frequency_range_hz": [points[0][0], points[-1][0]], "unity_gain_crossings": unity,
              "critical_phase_crossings": critical,
              "phase_margin_estimate": extrema([row["phase_margin_deg_estimate"] for row in unity if row["phase_margin_deg_estimate"] is not None], "deg"),
              "gain_margin_estimate": extrema([row["gain_margin_db_estimate"] for row in critical], "dB"),
              "stability_verdict": "not_determined",
              "qualification": "log_frequency_interpolation; all crossings retained; no Nyquist/pole-count test"}
    if args.loop_convention == "spectre" and points[0][1] >= 0:
        result["warning"] = "lowest_frequency_real_AF_nonnegative_review_sign_convention_loop_polarity_and_sweep_start"
    if not unity:
        result["phase_margin_estimate"] = unavailable("no_unity_gain_crossing_in_sampled_range", unit="deg")
    if not critical:
        result["gain_margin_estimate"] = unavailable("no_critical_phase_crossing_in_sampled_range", unit="dB")
    return result


def ac_analysis(data):
    points, error = series(data, "frequency_hz", ["vout_real", "vout_imag", "vin_real", "vin_imag"], True)
    if error:
        return unavailable(error)
    curve = []
    for frequency, out_real, out_imag, in_real, in_imag in points:
        output, input_ = math.hypot(out_real, out_imag), math.hypot(in_real, in_imag)
        item = {"frequency_hz": frequency}
        if input_ == 0:
            item.update(unavailable("zero_ac_input_magnitude"))
        elif output == 0:
            item.update(unavailable("zero_ac_output_no_finite_psrr_claim"))
        else:
            transfer = 20 * (math.log10(output) - math.log10(input_))
            item.update({"status": "computed", "transfer_gain_db": transfer, "psrr_db": -transfer})
        curve.append(item)
    return {"status": "computed" if all(row["status"] == "computed" for row in curve) else "partial",
            "psrr_definition": "-20log10(abs(Vout_ac/Vin_ac)); positive rejection", "curve": curve,
            "psrr_range_db": extrema([row["psrr_db"] for row in curve if row["status"] == "computed"], "dB"),
            "scope": "core_with_ideal_reference_if_reference_supply_coupling_was_not_modelled"}


def plots(datasets, analyses, output_dir, args):
    if args.no_plots:
        return unavailable("disabled_by_argument")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        return unavailable("matplotlib_not_installed", detail=str(error))
    created, errors = [], []
    context, _ = read_json(args.context_json)
    caption_parts = []
    if isinstance(context, dict):
        capacitance = finite(context.get("cout_f"))
        if capacitance is not None and context.get("capacitor_scope"):
            capacitance_text = f"{capacitance * 1e9:g} nF" if capacitance >= 1e-9 else f"{capacitance * 1e12:g} pF"
            caption_parts.append("External ideal Cout=" + capacitance_text)
        reference = finite(context.get("reference_v"))
        if reference is not None and context.get("reference") == "ideal":
            caption_parts.append(f"Ideal Vref={reference:g} V")
    caption = "; ".join(caption_parts)

    def save(figure, filename):
        figure.tight_layout()
        path = output_dir / filename
        figure.savefig(path, dpi=180)
        plt.close(figure)
        created.append(str(path.resolve()))

    try:
        rows = datasets["transient"]["rows"]
        if rows:
            figure, axes = plt.subplots(3, 1, sharex=True, figsize=(9, 7))
            for key in ("vout_v", "gate_v", "fb_v", "vin_v"):
                x = [row["time_s"] * 1e6 if row["time_s"] is not None else math.nan for row in rows]
                y = [row[key] if row[key] is not None else math.nan for row in rows]
                axes[0 if key == "vout_v" else 1].plot(x, y, label=key)
            axes[0].axhline(args.target_v, color="black", ls="--", lw=0.7)
            band = abs(args.target_v) * args.tolerance_fraction
            axes[0].axhspan(args.target_v - band, args.target_v + band, alpha=0.12, color="green")
            axes[2].plot(x, [row["load_a"] * 1e3 if row["load_a"] is not None else math.nan for row in rows])
            axes[0].set_title("Exported transient: " + args.run_id + ("\n" + caption if caption else ""))
            axes[0].set_ylabel("Vout (V)")
            axes[1].set_ylabel("Voltage (V)")
            axes[2].set_ylabel("Load (mA)")
            axes[2].set_xlabel("Time (µs)")
            for axis in axes:
                axis.grid(True, alpha=0.3)
            axes[0].legend(loc="upper right")
            axes[1].legend(loc="upper right")
            save(figure, "transient.png")
        points, error = series(datasets["stb"], "frequency_hz", ["loop_real", "loop_imag"], True)
        if not error and all(math.hypot(row[1], row[2]) > 0 for row in points):
            figure, axes = plt.subplots(2, 1, sharex=True, figsize=(8, 6))
            frequency = [row[0] for row in points]
            axes[0].semilogx(frequency, [20 * math.log10(math.hypot(row[1], row[2])) for row in points])
            axes[0].axhline(0, color="black", lw=0.7)
            axes[1].semilogx(frequency, unwrap_phase([math.degrees(math.atan2(row[2], row[1])) for row in points]))
            axes[0].set_ylabel("Loop magnitude (dB)")
            axes[1].set_ylabel("Raw exported phase (deg)")
            axes[1].set_xlabel("Frequency (Hz)")
            axes[0].set_title("STB raw loopGain: " + args.run_id)
            for axis in axes:
                axis.grid(True, which="both", alpha=0.3)
            save(figure, "stb.png")
        curve = analyses["ac"].get("curve", [])
        if any(row["status"] == "computed" for row in curve):
            figure, axis = plt.subplots(figsize=(8, 4))
            axis.semilogx([row["frequency_hz"] for row in curve], [row.get("psrr_db", math.nan) for row in curve])
            axis.set_xlabel("Frequency (Hz)")
            axis.set_ylabel("PSRR = -20log10|Vout/Vin| (dB)")
            axis.set_title("Core PSRR; check ideal-reference scope: " + args.run_id)
            axis.grid(True, which="both", alpha=0.3)
            save(figure, "psrr.png")
        rows = datasets["dc"]["rows"]
        valid = [row for row in rows if all(row[key] is not None for key in ("vin_v", "load_a", "vout_v"))]
        if valid:
            figure, axes = plt.subplots(1, 2, figsize=(10, 4))
            for vin in sorted({row["vin_v"] for row in valid}):
                group = sorted([row for row in valid if row["vin_v"] == vin], key=lambda row: row["load_a"])
                axes[0].plot([row["load_a"] * 1e3 for row in group], [row["vout_v"] for row in group], "o-", label=f"Vin={vin:g} V")
            for load in sorted({row["load_a"] for row in valid}):
                group = sorted([row for row in valid if row["load_a"] == load], key=lambda row: row["vin_v"])
                axes[1].plot([row["vin_v"] for row in group], [row["vout_v"] for row in group], "o-", label=f"Load={load * 1e3:g} mA")
            axes[0].set_xlabel("Load (mA)")
            axes[1].set_xlabel("Vin (V)")
            for axis in axes:
                axis.set_ylabel("Vout (V)")
                axis.grid(True, alpha=0.3)
                if len(axis.lines) <= 12:
                    axis.legend(fontsize=7)
            figure.suptitle("Exported DC points: " + args.run_id)
            save(figure, "dc.png")
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
        plt.close("all")
    return {"status": "created" if created and not errors else "partial" if created else "unavailable",
            "files": created, "errors": errors, "reason": None if created else "no_plottable_data"}


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    for kind in SCHEMAS:
        command.add_argument("--" + kind, metavar="CSV", help="Columns: " + ",".join(SCHEMAS[kind]))
    command.add_argument("--events-json", help="Explicit transient edge and pre/post/analysis windows; see --schema")
    command.add_argument("--stb-native-json", help="Native Spectre margin export; see --schema")
    command.add_argument("--context-json", help="Optional run/model/temperature/Cout metadata; copied without treating it as evidence")
    command.add_argument("--outdir", default="analysis", help="Summary and optional plot destination")
    command.add_argument("--run-id", default="unspecified")
    command.add_argument("--target-v", type=float, default=0.9)
    command.add_argument("--tolerance-fraction", type=float, default=0.01)
    command.add_argument("--recovery-center", choices=("target", "post_mean"), default="target")
    command.add_argument("--post-ripple-max-v", type=float)
    command.add_argument("--post-drift-max-v", type=float)
    command.add_argument("--loop-convention", choices=("spectre", "classical", "unspecified"), default="spectre")
    command.add_argument("--reg-vin-min", type=float, help="User-qualified Vin bound for line/load regulation calculations")
    command.add_argument("--reg-vin-max", type=float)
    command.add_argument("--dropout-fraction", type=float, help="Optional dropout loss fraction, e.g. 0.01; no default inference")
    command.add_argument("--no-plots", action="store_true")
    command.add_argument("--schema", action="store_true", help="Print input contract and exit without creating output")
    return command


def main(argv=None):
    command = parser()
    args = command.parse_args(argv)
    if args.schema:
        print(json.dumps(CONTRACT, indent=2, ensure_ascii=False))
        return 0
    for key in ("target_v", "tolerance_fraction", "post_ripple_max_v", "post_drift_max_v", "reg_vin_min", "reg_vin_max", "dropout_fraction"):
        value = getattr(args, key)
        if value is not None and not math.isfinite(value):
            command.error(key + " must be finite")
    if args.target_v <= 0 or args.tolerance_fraction <= 0:
        command.error("target-v and tolerance-fraction must be positive")
    if any(value is not None and value < 0 for value in (args.post_ripple_max_v, args.post_drift_max_v)):
        command.error("post-window limits must be nonnegative")
    if args.dropout_fraction is not None and not 0 < args.dropout_fraction < 1:
        command.error("dropout-fraction must be between zero and one")
    if args.reg_vin_min is not None and args.reg_vin_max is not None and args.reg_vin_min >= args.reg_vin_max:
        command.error("reg-vin-min must be below reg-vin-max")
    datasets = {kind: read_csv(getattr(args, kind), kind) for kind in SCHEMAS}
    events, events_error = read_json(args.events_json)
    native, native_error = read_json(args.stb_native_json)
    context, context_error = read_json(args.context_json)
    analyses = {"transient": transient_analysis(datasets["transient"], events, events_error, args),
                "dc": dc_analysis(datasets["dc"], args),
                "stb": stb_analysis(datasets["stb"], native, native_error, args),
                "ac": ac_analysis(datasets["ac"])}
    output_dir = Path(args.outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {"schema_version": 1, "run_id": args.run_id,
               "generated_utc": datetime.now(timezone.utc).isoformat(),
               "simulation_status": "not_verified_by_this_analysis_script",
               "status": "analysis_generated" if any(data["rows"] for data in datasets.values()) else "no_data",
               "settings": vars(args), "context": context if context_error is None else unavailable(context_error),
               "inputs": {kind: {key: value for key, value in data.items() if key != "rows"} for kind, data in datasets.items()},
               "analyses": analyses, "plots": plots(datasets, analyses, output_dir, args)}
    destination = output_dir / "summary.json"
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(destination.resolve()), "status": summary["status"], "plots": summary["plots"]["status"]}, ensure_ascii=False))
    return 0 if summary["status"] == "analysis_generated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
