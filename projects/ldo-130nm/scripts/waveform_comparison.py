"""Compare exported saved piecewise-linear waveforms; no simulator needed."""
import math

def waveform_error(coarse, fine):
    """Exact integrals of the difference between two saved linear interpolants.

    Visit the union of every original time knot, without decimating the traces.
    Between adjacent union knots the difference is linear; its maximum absolute
    value occurs at a boundary. Its squared integral is evaluated analytically.
    """
    if coarse[0][0] != fine[0][0] or coarse[-1][0] != fine[-1][0]:
        raise ValueError("waveforms must have exactly the same saved time coverage")
    if len(coarse[0]) != len(fine[0]):
        raise ValueError("channel counts differ")
    channels = len(coarse[0]) - 1
    current = coarse[0][0]
    duration = coarse[-1][0] - current
    if duration <= 0:
        raise ValueError("waveform duration must be positive")
    indices = [0, 0]
    sums = [{"signed": 0.0, "absolute": 0.0, "squared": 0.0,
             "maximum_abs": 0.0, "maximum_abs_time_s": current} for index in range(channels)]

    def at(points, index, time):
        left = points[index]
        if left[0] == time or index == len(points) - 1:
            return left[1:]
        right = points[index + 1]
        fraction = (time - left[0]) / (right[0] - left[0])
        return [a + fraction * (b - a) for a, b in zip(left[1:], right[1:])]

    previous = [a - b for a, b in zip(coarse[0][1:], fine[0][1:])]
    for item, difference in zip(sums, previous):
        item["maximum_abs"] = abs(difference)
    union_count = 1
    while current < coarse[-1][0]:
        next_coarse = coarse[indices[0] + 1][0] if indices[0] + 1 < len(coarse) else math.inf
        next_fine = fine[indices[1] + 1][0] if indices[1] + 1 < len(fine) else math.inf
        next_time = min(next_coarse, next_fine)
        if next_time <= current or not math.isfinite(next_time):
            raise ValueError("non-increasing or incomplete union axis")
        if next_time == next_coarse:
            indices[0] += 1
        if next_time == next_fine:
            indices[1] += 1
        differences = [a - b for a, b in zip(at(coarse, indices[0], next_time), at(fine, indices[1], next_time))]
        interval = next_time - current
        for item, left, right in zip(sums, previous, differences):
            item["signed"] += interval * (left + right) / 2
            item["squared"] += interval * (left * left + left * right + right * right) / 3
            if left * right >= 0:
                item["absolute"] += interval * (abs(left) + abs(right)) / 2
            else:
                item["absolute"] += interval * (left * left + right * right) / (2 * (abs(left) + abs(right)))
            if abs(right) > item["maximum_abs"]:
                item["maximum_abs"], item["maximum_abs_time_s"] = abs(right), next_time
        current, previous = next_time, differences
        union_count += 1
    result = []
    for item in sums:
        result.append({"maximum_absolute_error": item["maximum_abs"], "maximum_absolute_error_time_s": item["maximum_abs_time_s"],
                       "rms_error": math.sqrt(max(0, item["squared"]) / duration),
                       "mean_absolute_error": item["absolute"] / duration, "mean_signed_error": item["signed"] / duration})
    return {"coverage_s": [coarse[0][0], coarse[-1][0]], "coarse_saved_samples": len(coarse), "fine_saved_samples": len(fine),
            "union_time_knots": union_count, "channel_metrics": result,
            "method": "all saved knots, linear interpolation, exact linear-segment integral of error squared",
            "qualification": "comparison of saved interpolants; cannot bound unsaved internal-solver excursions"}

