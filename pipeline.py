#!/usr/bin/env python3
"""
CrashLogic / DentScan — Full two-model pipeline
===============================================
Implements the architecture diagram end-to-end:

    image ──► 1. PART model   (YOLO11-seg, carparts-seg)      ─┐
          ──► 2. DAMAGE model (YOLO11-seg, CarDD: scratch/     ├─► fusion (IoU)
                               dent/crack/glass/lamp/tire)     ─┘      │
                                                                       ▼
                                            recommendation engine (repair vs replace)
                                              parts price CSV + repair price CSV
                                                                       │
                                                                       ▼
                                                            report + TOTAL (AZN)

Usage:
    pip install ultralytics numpy python-dotenv
    python pipeline.py --image crash.jpg --brand mercedes --model "e class" --year 2018 \
        --part-weights parts_best.pt --damage-weights cardd_best.pt
    python pipeline.py --selftest          # offline, mock models, no weights needed

Weights:
    part model   — train on Ultralytics carparts-seg (see train_and_eval.py)
    damage model — CarDD checkpoint (harpreetsahota/car-dd-segmentation-yolov11)
                   or your fine-tuned version (train_and_eval.py)
"""

import os
import sys
import json
import argparse

import numpy as np

from car_price_agent import PriceDB, CSV_PATH
from recommendation import RecommendationEngine, format_report
from fusion import fuse, merge_findings, dets_from_ultralytics


# ─────────────────────────────────────────────────────────────────────────
class SegModel:
    """Thin wrapper over a YOLO segmentation checkpoint."""
    def __init__(self, weights: str):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.names = self.model.names

    def detect(self, image_path: str, conf: float, iou: float) -> list:
        results = self.model.predict(source=image_path, conf=conf, iou=iou,
                                     save=False, verbose=False, retina_masks=True)
        return dets_from_ultralytics(results[0], self.names)


class DamagePipeline:
    def __init__(self, db: PriceDB, part_model, damage_model,
                 part_conf=0.35, damage_conf=0.25, iou=0.45):
        self.db = db
        self.engine = RecommendationEngine(db)
        self.part_model = part_model
        self.damage_model = damage_model
        self.part_conf, self.damage_conf, self.iou = part_conf, damage_conf, iou

    def analyze(self, image_path: str, brand: str, model: str, year: int,
                annotate_path: str = None) -> dict:
        part_dets = self.part_model.detect(image_path, self.part_conf, self.iou)
        damage_dets = self.damage_model.detect(image_path, self.damage_conf, self.iou)

        # optional annotated overlay (uses masks in-scope; not stored in JSON)
        if annotate_path:
            from annotate import draw_annotations
            from fusion import assign_damages
            assignments = assign_damages(part_dets, damage_dets)
            draw_annotations(image_path, part_dets, damage_dets, annotate_path, assignments)

        findings, orphans = fuse(part_dets, damage_dets)

        if not findings:
            info = self.db.vehicle_info(brand, model, year)
            return {"found": info is not None,
                    "vehicle": info, "findings": [], "orphans": orphans,
                    "annotated_path": annotate_path,
                    "message": "Şəkildə qiymətləndirilə bilən zədə tapılmadı."}

        report = self.engine.recommend(brand, model, year, findings)
        report["findings"] = findings
        report["orphans"] = orphans
        report["annotated_path"] = annotate_path
        report["detections"] = {
            "parts": [{"class": d["class_name"], "conf": round(d["confidence"], 2)}
                      for d in part_dets],
            "damages": [{"class": d["class_name"], "conf": round(d["confidence"], 2)}
                        for d in damage_dets],
        }
        return report

    def analyze_many(self, image_paths: list, brand: str, model: str, year: int,
                     annotate_paths: list = None) -> dict:
        """Analyze several photos of the SAME damaged vehicle and return ONE
        merged report. A part visible in more than one photo (e.g. the front
        bumper shot head-on and from the side) is priced only once — see
        fusion.merge_findings — so the total is never double-counted."""
        if annotate_paths is not None and len(annotate_paths) != len(image_paths):
            raise ValueError("annotate_paths must match image_paths in length")

        per_image = []
        for i, image_path in enumerate(image_paths):
            part_dets = self.part_model.detect(image_path, self.part_conf, self.iou)
            damage_dets = self.damage_model.detect(image_path, self.damage_conf, self.iou)

            annotate_path = annotate_paths[i] if annotate_paths else None
            if annotate_path:
                from annotate import draw_annotations
                from fusion import assign_damages
                assignments = assign_damages(part_dets, damage_dets)
                draw_annotations(image_path, part_dets, damage_dets, annotate_path, assignments)

            findings, orphans = fuse(part_dets, damage_dets)
            per_image.append({
                "image": image_path, "annotated_path": annotate_path,
                "findings": findings, "orphans": orphans,
                "detections": {
                    "parts": [{"class": d["class_name"], "conf": round(d["confidence"], 2)}
                              for d in part_dets],
                    "damages": [{"class": d["class_name"], "conf": round(d["confidence"], 2)}
                                for d in damage_dets],
                },
            })

        merged_findings = merge_findings([pi["findings"] for pi in per_image])
        all_orphans = [o for pi in per_image for o in pi["orphans"]]

        if not merged_findings:
            info = self.db.vehicle_info(brand, model, year)
            return {"found": info is not None,
                    "vehicle": info, "findings": [], "orphans": all_orphans,
                    "per_image": per_image,
                    "message": "Şəkillərdə qiymətləndirilə bilən zədə tapılmadı."}

        report = self.engine.recommend(brand, model, year, merged_findings)
        report["findings"] = merged_findings
        report["orphans"] = all_orphans
        report["per_image"] = per_image
        return report


def format_full_report(res: dict) -> str:
    if not res.get("found"):
        return format_report(res)
    if not res.get("lines"):
        v = res.get("vehicle") or {}
        head = f"🚗 {v.get('brand','?')} {v.get('model','')} {v.get('year','')}"
        return head + "\n" + res.get("message", "Zədə tapılmadı.")
    out = [format_report(res)]
    if res.get("orphans"):
        out.append("\n⚠️  Hissəyə bağlanmayan zədələr: " +
                   ", ".join(o["damage_type"] for o in res["orphans"]))
    if res.get("annotated_path"):
        out.append(f"\n🖼️  Annotasiyalı şəkil: {res['annotated_path']}")
    per_image = [pi["annotated_path"] for pi in res.get("per_image", []) if pi.get("annotated_path")]
    if per_image:
        out.append("\n🖼️  Annotasiyalı şəkillər: " + ", ".join(per_image))
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────
#  Mock models for offline selftest (same synthetic scene as fusion.py)
# ─────────────────────────────────────────────────────────────────────────
class _Mock:
    """detect() ignores conf/iou; `dets` is either one fixed detection list
    (same result regardless of image path) or a {image_path: dets} map, so a
    single mock model instance can stand in for a real one that naturally
    returns different detections per photo."""
    def __init__(self, dets):
        self._dets = dets
    def detect(self, image_path, *a, **k):
        if isinstance(self._dets, dict):
            return self._dets.get(image_path, [])
        return self._dets


def _selftest(db: PriceDB):
    H = W = 100
    def rect(y0, y1, x0, x1):
        m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = True; return m

    part_model = _Mock([
        {"class_name": "front_bumper", "mask": rect(70, 100, 0, 100), "confidence": 0.95},
        {"class_name": "hood",         "mask": rect(30, 70, 10, 90),  "confidence": 0.92},
        {"class_name": "front_left_light", "mask": rect(60, 72, 2, 20), "confidence": 0.90},
    ])
    damage_model = _Mock([
        {"class_name": "scratch", "mask": rect(80, 85, 40, 60), "confidence": 0.81},
        {"class_name": "dent",    "mask": rect(35, 65, 20, 60), "confidence": 0.77},
        {"class_name": "crack",   "mask": rect(62, 70, 5, 18),  "confidence": 0.70},
    ])

    pipe = DamagePipeline(db, part_model, damage_model)

    # write a blank canvas so the annotation path can run offline too
    try:
        import cv2
        cv2.imwrite("_selftest.jpg", np.full((H, W, 3), 60, np.uint8))
        ann = "_selftest_annotated.jpg"
    except Exception:
        ann = None

    res = pipe.analyze("_selftest.jpg" if ann else "mock.jpg",
                       "mercedes", "e class", 2018, annotate_path=ann)
    print(format_full_report(res))
    print("\n--- JSON (API üçün) ---")
    slim = {k: res[k] for k in ("vehicle", "findings", "recommended_total",
                                "replace_all_total_avg", "savings_avg") if k in res}
    print(json.dumps(slim, ensure_ascii=False, indent=1))

    # multi-photo: photo B re-detects the SAME front bumper (now worse) plus
    # a new part (rear bumper) — the merged total must count the bumper once,
    # keeping the worse of the two severities.
    print("\n--- Çoxşəkilli analiz (analyze_many) ---")
    img_a = "_selftest.jpg" if ann else "mock_a.jpg"
    img_b = "_selftest2.jpg" if ann else "mock_b.jpg"
    if ann:
        cv2.imwrite(img_b, np.full((H, W, 3), 60, np.uint8))

    part_model_multi = _Mock({
        img_a: [{"class_name": "front_bumper", "mask": rect(70, 100, 0, 100), "confidence": 0.95},
                {"class_name": "hood",         "mask": rect(30, 70, 10, 90),  "confidence": 0.92}],
        img_b: [{"class_name": "front_bumper", "mask": rect(70, 100, 0, 100), "confidence": 0.93},
                {"class_name": "back_bumper",  "mask": rect(0, 20, 0, 100),   "confidence": 0.90}],
    })
    damage_model_multi = _Mock({
        img_a: [{"class_name": "scratch", "mask": rect(80, 85, 40, 60), "confidence": 0.81}],   # minor, on bumper
        img_b: [{"class_name": "scratch", "mask": rect(75, 100, 0, 100), "confidence": 0.85},   # severe, same bumper
                {"class_name": "dent",    "mask": rect(2, 18, 10, 90),   "confidence": 0.80}],   # rear bumper, new
    })
    pipe2 = DamagePipeline(db, part_model_multi, damage_model_multi)
    res_multi = pipe2.analyze_many([img_a, img_b], "mercedes", "e class", 2018)
    print(format_full_report(res_multi))
    bumper_lines = [f for f in res_multi["findings"] if f["part_code"] == "front_bumper_cover"]
    assert len(bumper_lines) == 1 and bumper_lines[0]["severity"] == "severe", \
        "front bumper must appear ONCE, with the worse of the two photos' severity"
    assert any(f["part_code"] == "rear_bumper_cover" for f in res_multi["findings"])
    print("analyze_many dedup OK")


def main():
    ap = argparse.ArgumentParser(description="CrashLogic full pipeline")
    ap.add_argument("--image", nargs="+",
                    help="one or more photos of the same damaged vehicle")
    ap.add_argument("--brand")
    ap.add_argument("--model")
    ap.add_argument("--year", type=int)
    ap.add_argument("--part-weights", default="parts_best.pt")
    ap.add_argument("--damage-weights", default="cardd_best.pt")
    ap.add_argument("--part-conf", type=float, default=0.35,
                    help="part-model confidence threshold")
    ap.add_argument("--damage-conf", type=float, default=0.25,
                    help="damage-model confidence threshold (raise to cut false positives)")
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    ap.add_argument("--save-annotated", nargs="?", const="__auto__", default=None,
                    metavar="PATH",
                    help="save masks drawn on the image (auto-names if no PATH given)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV tapılmadı: {CSV_PATH}")
    db = PriceDB(CSV_PATH)

    if args.selftest:
        _selftest(db)
        return
    if not (args.image and args.brand and args.model and args.year):
        sys.exit("İstifadə: --image X [Y ...] --brand B --model M --year Y  (və ya --selftest)")

    pipe = DamagePipeline(db,
                          SegModel(args.part_weights),
                          SegModel(args.damage_weights),
                          part_conf=args.part_conf,
                          damage_conf=args.damage_conf)

    if len(args.image) == 1:
        annotate_path = args.save_annotated
        if annotate_path == "__auto__":
            stem = os.path.splitext(os.path.basename(args.image[0]))[0]
            annotate_path = f"{stem}_annotated.jpg"
        res = pipe.analyze(args.image[0], args.brand, args.model, args.year,
                           annotate_path=annotate_path)
    else:
        annotate_paths = None
        if args.save_annotated:
            annotate_paths = [
                f"{os.path.splitext(os.path.basename(p))[0]}_annotated.jpg"
                for p in args.image
            ]
        res = pipe.analyze_many(args.image, args.brand, args.model, args.year,
                                annotate_paths=annotate_paths)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    else:
        print(format_full_report(res))


if __name__ == "__main__":
    main()