#!/usr/bin/env python3
"""
Compute all-time totals, before/after lifts, biggest month-over-month jumps and ranked
headline candidates from normalized monthly Reacher data.

Usage:
    python analyze_monthly.py monthly.json

monthly.json shape (build it from the timeseries_metrics tool output):
{
  "months": ["2025-12", "2026-01", ...],       # YYYY-MM, oldest first, contiguous
  "start_month": "2026-01",                     # first month on Reacher
  "partial_last_month": true,                   # current month still in progress?
  "currency": "$",
  "metrics": {
    "creators_reached": [..], "samples_approved": [..], "sample_requests": [..],
    "videos_posted": [..], "video_views": [..], "gmv": [..], ...
  }
}
Values may be null for months with no data. Prints a JSON report to stdout.
"""
import json
import sys

# metrics that are flows (safe to sum into all-time totals)
FLOW = {"creators_reached", "creators_messaged", "tc_invites_sent", "sample_requests",
        "samples_approved", "videos_posted", "video_views", "gmv", "total_gmv", "live_gmv",
        "new_creators_posting", "gmv_driving_videos", "emails_sent", "orders", "units_sold"}
MONEY = {"gmv", "total_gmv", "live_gmv"}
# how strongly each metric reads as a business result, for headline ranking
WEIGHT = {"gmv": 1.0, "total_gmv": 0.95, "videos_posted": 0.8, "samples_approved": 0.75,
          "sample_requests": 0.7, "video_views": 0.7, "new_creators_posting": 0.7,
          "creators_reached": 0.6, "gmv_driving_videos": 0.75, "live_gmv": 0.65}
LABEL = {"gmv": "affiliate GMV", "total_gmv": "total shop GMV", "videos_posted": "videos posted",
         "samples_approved": "sample approvals", "sample_requests": "sample requests",
         "video_views": "video views", "creators_reached": "creators reached",
         "new_creators_posting": "new creators posting", "gmv_driving_videos":
         "GMV-driving videos", "live_gmv": "LIVE GMV", "creators_messaged": "creators messaged",
         "tc_invites_sent": "Target Collab invites"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def mlabel(ym, long=False):
    y, m = ym.split("-")
    return f"{MONTHS[int(m)-1]} {y}" if long else f"{MONTHS[int(m)-1]} {y[2:]}"

def v(x):
    return float(x) if x is not None else 0.0

def main(path):
    d = json.load(open(path))
    months = d["months"]
    start = months.index(d["start_month"])
    partial = d.get("partial_last_month", False)
    last_full = len(months) - 2 if partial else len(months) - 1
    base = start - 1 if start > 0 else None
    out = {"window": {
        "on_reacher_from": mlabel(months[start], True),
        "through": mlabel(months[-1], True) + (" (month in progress)" if partial else ""),
        "baseline_month": mlabel(months[base], True) if base is not None else None,
        "latest_full_month": mlabel(months[last_full], True) if last_full >= start else None,
        "months_on_reacher": len(months) - start,
    }, "totals_since_start": {}, "lifts": [], "biggest_jumps": {}, "best_months": {},
        "headline_candidates": [], "chart_labels": [mlabel(m) for m in months]}

    for k, vals in d["metrics"].items():
        vals = [None if x is None else float(x) for x in vals]
        on = vals[start:]
        if k in FLOW:
            out["totals_since_start"][k] = round(sum(v(x) for x in on), 2)
        full = vals[start:last_full + 1]
        if not full:
            continue
        # best month on Reacher (full months only)
        bi = max(range(len(full)), key=lambda i: v(full[i]))
        out["best_months"][k] = {"month": mlabel(months[start + bi], True), "value": full[bi]}
        # biggest month-over-month jump (full months, including the step into month 1)
        rng = range(max(start, 1), last_full + 1)
        jumps = [(i, v(vals[i]) - v(vals[i - 1])) for i in rng]
        if jumps:
            ji, jv = max(jumps, key=lambda t: t[1])
            if jv > 0:
                out["biggest_jumps"][k] = {"month": mlabel(months[ji], True), "index": ji,
                                           "from": vals[ji - 1], "to": vals[ji], "increase": jv}
        # lifts: baseline -> latest full month, and baseline -> best month
        comps = []
        if base is not None and last_full >= start:
            comps.append(("baseline_to_latest", base, last_full))
            comps.append(("baseline_to_best", base, start + bi))
        if last_full > start:
            comps.append(("first_to_latest", start, last_full))
        for kind, a, b in comps:
            av, bv = v(vals[a]), v(vals[b])
            lift = {"metric": k, "kind": kind, "from_month": mlabel(months[a], True),
                    "to_month": mlabel(months[b], True), "before": vals[a], "after": vals[b],
                    "money": k in MONEY}
            if av > 0:
                lift["multiplier"] = round(bv / av, 2)
                lift["pct_change"] = round((bv / av - 1) * 100, 1)
            else:
                lift["multiplier"] = None  # from zero: frame as "from 0 to X", never "Nx"
            out["lifts"].append(lift)

    # headline candidates: multiplier lifts (>=2x) ranked by weight * log-ish strength,
    # plus record-month and all-time-total framings
    import math
    cands = []
    for L in out["lifts"]:
        m = L.get("multiplier")
        if m and m >= 2 and L["kind"] != "baseline_to_best":
            score = WEIGHT.get(L["metric"], 0.5) * math.log(m + 1)
            cands.append({"type": "lift", "score": round(score, 3), **L,
                          "pattern": f"How {{brand}} grew {LABEL.get(L['metric'], L['metric'])} "
                                     f"{m:g}x in {{period}}"})
        if L.get("multiplier") is None and L["kind"] == "baseline_to_latest" and v(L["after"]) > 0:
            cands.append({"type": "from_zero", "score": round(WEIGHT.get(L["metric"], .5) * 1.2, 3),
                          **L, "pattern": f"How {{brand}} built {LABEL.get(L['metric'], L['metric'])} "
                                          f"from zero to {{after}}"})
    for k in ("gmv", "total_gmv"):
        if k in out["best_months"]:
            b = out["best_months"][k]
            cands.append({"type": "record_month", "metric": k, "score": round(WEIGHT[k] * 1.1, 3),
                          **b, "pattern": "How {brand} hit its biggest month ever with "
                                          "{value} in " + LABEL[k]})
    cands.sort(key=lambda c: c["score"], reverse=True)
    out["headline_candidates"] = cands[:6]
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1])
