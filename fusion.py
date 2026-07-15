#!/usr/bin/env python3
"""
CrashLogic / DentScan — Fusion layer
====================================
Combines the two segmentation models' outputs:

    part model    -> [(part_class_name, mask), ...]      e.g. ("front_bumper", HxW bool)
    damage model  -> [(damage_class_name, mask), ...]    e.g. ("scratch", HxW bool)

For every damage mask we find the part mask it overlaps most
(overlap ratio = |damage ∩ part| / |damage|) and compute severity from
how much of the part is affected (|damage ∩ part| / |part|):

    < 10%  -> minor      (polish / PDR territory)
    < 35%  -> moderate   (repair + paint)
    >= 35% -> severe     (replacement candidate)

Output findings feed straight into recommendation.RecommendationEngine:
    [{"part_code", "damage_type", "severity", "confidence", "overlap"}, ...]
"""

import numpy as np

# ── carparts-seg class names -> CSV part_code ────────────────────────────
# Covers the Ultralytics carparts-seg label set; anything unknown falls back
# to PriceDB.resolve_part_code at recommendation time.
PARTCLASS_TO_CODE = {
    "front_bumper": "front_bumper_cover",
    "back_bumper": "rear_bumper_cover",
    "rear_bumper": "rear_bumper_cover",
    "grille": "front_grille",
    "hood": "hood", "bonnet": "hood",
    "trunk": "trunk_lid", "boot": "trunk_lid",
    "tailgate": "tailgate",
    "roof": "roof_panel",
    "front_left_door": "front_left_door",
    "front_right_door": "front_right_door",
    "back_left_door": "rear_left_door",
    "back_right_door": "rear_right_door",
    "front_door": "front_left_door",           # side unknown → L/R same price
    "back_door": "rear_left_door",
    "front_left_light": "left_headlight",
    "front_right_light": "right_headlight",
    "front_light": "left_headlight",
    "back_left_light": "left_taillight",
    "back_right_light": "right_taillight",
    "back_light": "left_taillight",
    "fender": "front_left_fender",
    "front_fender": "front_left_fender",
    "quarter_panel": "rear_left_quarter_panel",
    "rocker_panel": "rocker_panel",
    "front_glass": "front_windshield", "windshield": "front_windshield",
    "back_glass": "rear_windshield",
    "left_mirror": "left_side_mirror_assembly",
    "right_mirror": "right_side_mirror_assembly",
    "mirror": "left_side_mirror_assembly",
    "wheel": "front_left_wheel",               # position unknown → same price
    "tire": "front_left_tire",
    "door_handle": "door_handle",
    "fuel_door": "fuel_filler_door",
}

SEV_MINOR = 0.10     # damage covers <10% of the part
SEV_MODERATE = 0.35  # <35% → moderate, otherwise severe
MIN_OVERLAP = 0.30   # damage must land ≥30% inside a part to be assigned


def part_class_to_code(name: str) -> str:
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    return PARTCLASS_TO_CODE.get(key, key)   # unknown → let PriceDB resolve it


def severity_from_ratio(part_cover: float) -> str:
    if part_cover < SEV_MINOR:
        return "minor"
    if part_cover < SEV_MODERATE:
        return "moderate"
    return "severe"


def assign_damages(part_dets: list, damage_dets: list) -> list:
    """Per-damage assignment (aligned with damage_dets order), used for both
    fusion and annotation. Each entry:
        {damage_idx, damage_type, confidence, orphan,
         part_name, part_code, severity, overlap, part_cover, part_confidence}
    'orphan' entries have no part fields (damage didn't land on any part)."""
    parts = [(p["class_name"], p["mask"].astype(bool), p.get("confidence", 0.0))
             for p in part_dets]
    out = []
    for i, d in enumerate(damage_dets):
        dmask = d["mask"].astype(bool)
        darea = int(dmask.sum())
        rec = {"damage_idx": i, "damage_type": d["class_name"],
               "confidence": round(float(d.get("confidence", 0.0)), 3)}
        if darea == 0:
            rec["orphan"] = True; out.append(rec); continue
        best = None  # (overlap, part_name, part_cover, part_conf)
        for pname, pmask, pconf in parts:
            inter = int(np.logical_and(dmask, pmask).sum())
            if inter == 0:
                continue
            overlap = inter / darea                       # share of the damage on this part
            part_cover = inter / max(int(pmask.sum()), 1) # share of the part damaged
            if best is None or overlap > best[0]:
                best = (overlap, pname, part_cover, pconf)
        if best is None or best[0] < MIN_OVERLAP:
            rec["orphan"] = True; out.append(rec); continue
        overlap, pname, part_cover, pconf = best
        rec.update({"orphan": False, "part_name": pname,
                    "part_code": part_class_to_code(pname),
                    "severity": severity_from_ratio(part_cover),
                    "overlap": round(overlap, 3), "part_cover": round(part_cover, 3),
                    "part_confidence": round(float(pconf), 3)})
        out.append(rec)
    return out


def fuse(part_dets: list, damage_dets: list) -> tuple[list, list]:
    """
    part_dets:   [{"class_name", "mask" (HxW bool/0-1 np.ndarray), "confidence"}, ...]
    damage_dets: same structure, damage classes.
    Returns (findings, orphans):
      findings — deduplicated per (part, damage_type), keeping the worst severity,
                 ready for the recommendation engine.
      orphans  — damage detections that didn't overlap any part enough.
    """
    sev_rank = {"minor": 0, "moderate": 1, "severe": 2}
    findings, orphans = {}, []
    for a in assign_damages(part_dets, damage_dets):
        if a.get("orphan"):
            orphans.append({"damage_type": a["damage_type"], "confidence": a["confidence"]})
            continue
        pconf = a.get("part_confidence", 0.0)
        conf = min(a["confidence"], pconf) if pconf else a["confidence"]
        key = (a["part_code"], a["damage_type"].lower())
        prev = findings.get(key)
        if prev is None or sev_rank[a["severity"]] > sev_rank[prev["severity"]]:
            findings[key] = {"part_code": a["part_code"],
                             "damage_type": a["damage_type"],
                             "severity": a["severity"],
                             "confidence": round(conf, 3),
                             "overlap": a["overlap"]}
    return list(findings.values()), orphans


def merge_findings(findings_lists: list) -> list:
    """Merge findings from several photos of the SAME damaged vehicle.

    Different photos often frame the same physical part (e.g. the front
    bumper shot both head-on and from the side), which would otherwise be
    priced/repaired twice. We dedupe by part_code alone (unlike fuse(),
    which also keys on damage_type within a single image) so every part
    contributes exactly one line to the final report, keeping whichever
    photo showed the worst damage for it.
    """
    sev_rank = {"minor": 0, "moderate": 1, "severe": 2}
    merged = {}
    for findings in findings_lists:
        for f in findings:
            code = f["part_code"]
            prev = merged.get(code)
            if prev is None or sev_rank[f["severity"]] > sev_rank[prev["severity"]]:
                merged[code] = f
    return list(merged.values())


def dets_from_ultralytics(result, names: dict) -> list:
    """Convert one ultralytics segmentation Result to our det format.
    Masks are upscaled by ultralytics to the input size; we use them as-is."""
    out = []
    if result.masks is None or result.boxes is None:
        return out
    masks = result.masks.data.cpu().numpy()          # N x H x W float
    for i, box in enumerate(result.boxes):
        out.append({"class_name": names[int(box.cls[0])],
                    "mask": masks[i] > 0.5,
                    "confidence": float(box.conf[0])})
    return out


# ── offline selftest with synthetic masks ────────────────────────────────
def _selftest():
    H = W = 100
    def rect(y0, y1, x0, x1):
        m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = True; return m

    parts = [
        {"class_name": "front_bumper", "mask": rect(70, 100, 0, 100), "confidence": 0.95},
        {"class_name": "hood",         "mask": rect(30, 70, 10, 90),  "confidence": 0.92},
        {"class_name": "front_left_light", "mask": rect(60, 72, 2, 20), "confidence": 0.90},
    ]
    damages = [
        # small scratch fully on the bumper (area 5x20=100 of bumper 3000 → 3% → minor)
        {"class_name": "scratch", "mask": rect(80, 85, 40, 60), "confidence": 0.81},
        # big dent on the hood (30x40=1200 of hood 3200 → 37% → severe)
        {"class_name": "dent",    "mask": rect(35, 65, 20, 60), "confidence": 0.77},
        # crack mostly on the headlight
        {"class_name": "crack",   "mask": rect(62, 70, 5, 18),  "confidence": 0.70},
        # orphan: damage in the background (no part there)
        {"class_name": "scratch", "mask": rect(0, 10, 0, 10),   "confidence": 0.55},
    ]

    findings, orphans = fuse(parts, damages)
    print("Findings:")
    for f in findings:
        print("  ", f)
    print("Orphans:", orphans)
    assert any(f["part_code"] == "front_bumper_cover" and f["severity"] == "minor"
               for f in findings)
    assert any(f["part_code"] == "hood" and f["severity"] == "severe"
               for f in findings)
    assert any(f["part_code"] == "left_headlight" for f in findings)
    assert len(orphans) == 1

    # a second photo re-detects the same bumper, now with severe damage —
    # merge_findings must keep ONE bumper line (the worse one), not two.
    findings2, _ = fuse(parts, [
        {"class_name": "scratch", "mask": rect(75, 100, 0, 100), "confidence": 0.88},
    ])
    merged = merge_findings([findings, findings2])
    bumper_lines = [f for f in merged if f["part_code"] == "front_bumper_cover"]
    assert len(bumper_lines) == 1 and bumper_lines[0]["severity"] == "severe"
    assert len(merged) == len(findings)  # no new parts introduced, just re-priced
    print("merge_findings OK")

    print("selftest OK")


if __name__ == "__main__":
    _selftest()
