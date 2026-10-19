from __future__ import annotations

from typing import Any

import numpy as np

from .contracts import SelectionConfig
from .geometry import Geometry, metrics


def select(g: Geometry, eligible: list[int], concern: dict[int, float], config: SelectionConfig) -> dict[str, Any]:
    if len(set(eligible)) != len(eligible) or any(i < 0 or i >= len(g.occurrences) for i in eligible):
        raise ValueError("foreign or duplicated eligible identity")
    if any(not np.all(np.isfinite(g.to_train[i])) for i in eligible):
        raise ValueError("unsupported eligible candidate feature evidence")
    eligible = sorted(eligible, key=lambda i: (g.occurrences[i]["source_occurrence_ordinal"], g.occurrences[i]["occurrence_id"]))
    cover = g.cover(config.coverage_radius)
    weights = g.balanced_weights if config.strategy == "quality-coverage" else g.uniform_weights
    covered = np.zeros(len(g.regions), dtype=bool)
    selected: list[int] = []; trace = []; used = set()
    available_minority = len({g.feature_ids[i] for i in eligible if g.occurrences[i]["payload"][g.target] == g.minority})
    requested_quota = int(config.budget*config.minority_quota_fraction) if config.strategy == "quality-coverage" else 0
    quota = min(requested_quota, available_minority)
    for step in range(min(config.budget, len(eligible))):
        remaining = [i for i in eligible if i not in selected and (config.strategy != "quality-coverage" or g.feature_ids[i] not in used)]
        minority_selected = sum(g.occurrences[i]["payload"][g.target] == g.minority for i in selected)
        quota_active = config.strategy == "quality-coverage" and minority_selected < quota
        if quota_active:
            remaining = [i for i in remaining if g.occurrences[i]["payload"][g.target] == g.minority]
        if not remaining:
            break
        gains = {i: float(weights[cover[i] & ~covered].sum()) for i in remaining}
        separations = {i: float(g.pairwise[i, selected].min()) if selected else 0. for i in remaining}
        def objective(i: int, gains: dict[int, float] = gains,
                      separations: dict[int, float] = separations) -> tuple[float, ...]:
            if config.strategy == "source-order": return (0.,)
            if config.strategy == "farthest-first": return (round(separations[i], 12),)
            if config.strategy == "coverage-greedy": return (round(gains[i], 12),)
            near = int(np.sum(g.pairwise[i, selected] <= config.near_duplicate_tolerance)) if selected else 0
            return (round(gains[i], 12), -near, round(separations[i], 12), -round(concern[i], 12))
        # max retains the first member on equal keys: stable source-order tie breaking.
        chosen = max(remaining, key=objective)
        selected_key = list(objective(chosen))
        newly = int(np.sum(cover[chosen] & ~covered))
        covered |= cover[chosen]; selected.append(chosen); used.add(g.feature_ids[chosen])
        trace.append({"selection_rank": step+1, "occurrence_id": g.occurrences[chosen]["occurrence_id"],
            "objective_key": selected_key, "marginal_weighted_coverage": gains[chosen],
            "marginal_regions_covered": newly, "nearest_previously_selected_distance": separations[chosen] if step else None,
            "cumulative_objective": float(weights[covered].sum()), "quota_active": quota_active,
            "selection_reason": config.strategy + (":MINORITY_QUOTA_FIRST" if quota_active else ":DECLARED_OBJECTIVE"),
            "uncalibrated_concern": concern[chosen]})
    return {"selected_indices": selected, "trace": trace,
        "budget_requested": config.budget, "budget_achieved": len(selected),
        "shortfall": config.budget-len(selected),
        "stopping_reason": "BUDGET_REACHED" if len(selected) == config.budget else "ELIGIBLE_OR_DISTINCT_FEATURE_EXHAUSTION",
        "minority_quota_requested": requested_quota, "minority_quota_feasible": quota,
        "minority_quota_unavailable": requested_quota-quota,
        "metrics": metrics(g, selected, eligible, config.coverage_radius, config.near_duplicate_tolerance)}
