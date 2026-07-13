#!/usr/bin/env python3
"""
CrashLogic / DentScan — Train & Evaluate (Colab / GPU machine)
==============================================================
Measures BOTH models BEFORE and AFTER fine-tuning and writes a
precision/recall/mAP comparison table.

    Stage A  PART model   — base: COCO-pretrained yolo11n-seg
                            data: Ultralytics carparts-seg (auto-downloads)
    Stage B  DAMAGE model — base: CarDD checkpoint (scratch/dent/crack/
                            glass shatter/lamp broken/tire flat)
                            data: your CarDD-format dataset yaml

Run in Colab (GPU runtime):
    !pip install -q ultralytics huggingface_hub
    !python train_and_eval.py --stage parts  --epochs 60
    !python train_and_eval.py --stage damage --data cardd.yaml --epochs 60

Outputs:
    metrics_comparison.csv   — baseline vs fine-tuned, per model
    runs/segment/...         — standard ultralytics training artifacts
    parts_best.pt / cardd_best.pt — copied best weights for pipeline.py

Notes on the BASELINE numbers (important for the jury/README):
  * PART baseline = COCO yolo11n-seg evaluated on carparts val. COCO has no
    "hood"/"bumper" classes, so P/R/mAP ≈ 0. That IS the honest "untrained"
    number — it shows why fine-tuning is necessary.
  * DAMAGE baseline = the public CarDD checkpoint evaluated as-is on your
    val split, i.e. real transfer performance before your fine-tune.
"""

import os
import csv
import shutil
import argparse

from ultralytics import YOLO


def metrics_row(tag, model_name, m):
    """Extract box+mask P/R/mAP from an ultralytics val() result."""
    return {
        "stage": tag, "model": model_name,
        "precision_box": round(float(m.box.mp), 4),
        "recall_box": round(float(m.box.mr), 4),
        "mAP50_box": round(float(m.box.map50), 4),
        "mAP50_95_box": round(float(m.box.map), 4),
        "precision_mask": round(float(m.seg.mp), 4),
        "recall_mask": round(float(m.seg.mr), 4),
        "mAP50_mask": round(float(m.seg.map50), 4),
        "mAP50_95_mask": round(float(m.seg.map), 4),
    }


def append_csv(row, path="metrics_comparison.csv"):
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)


def print_table(rows):
    cols = ["stage", "model", "precision_mask", "recall_mask",
            "mAP50_mask", "mAP50_95_mask"]
    print("\n" + " | ".join(f"{c:>16}" for c in cols))
    print("-" * (19 * len(cols)))
    for r in rows:
        print(" | ".join(f"{str(r[c]):>16}" for c in cols))


def run_stage(stage, data, base_weights, epochs, imgsz, out_name):
    rows = []

    # ── 1) BASELINE: evaluate the un-fine-tuned model on the val split ──
    print(f"\n=== [{stage}] BASELINE evaluation: {base_weights} on {data} ===")
    base = YOLO(base_weights)
    try:
        m0 = base.val(data=data, imgsz=imgsz, split="val", plots=False)
        row0 = metrics_row("baseline (untrained)", base_weights, m0)
    except Exception as e:
        # class mismatch (e.g. COCO model on carparts yaml) → score is 0
        print(f"Baseline val degraded to zeros ({type(e).__name__}: {e})")
        row0 = {"stage": "baseline (untrained)", "model": base_weights,
                **{k: 0.0 for k in ("precision_box", "recall_box", "mAP50_box",
                                     "mAP50_95_box", "precision_mask", "recall_mask",
                                     "mAP50_mask", "mAP50_95_mask")}}
    append_csv(row0); rows.append(row0)

    # ── 2) FINE-TUNE ─────────────────────────────────────────────────────
    print(f"\n=== [{stage}] TRAINING {epochs} epochs, imgsz={imgsz} ===")
    model = YOLO(base_weights)
    model.train(
        data=data, epochs=epochs, imgsz=imgsz, batch=-1,          # auto batch
        optimizer="AdamW", lr0=1e-3, lrf=0.01, cos_lr=True,
        patience=15, dropout=0.1,
        mosaic=1.0, mixup=0.1, copy_paste=0.1,
        hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
        overlap_mask=True, amp=True, plots=True,
    )

    # ── 3) FINAL: evaluate best.pt on the same val split ────────────────
    best_pt = os.path.join(model.trainer.save_dir, "weights", "best.pt")
    print(f"\n=== [{stage}] FINAL evaluation: {best_pt} ===")
    tuned = YOLO(best_pt)
    m1 = tuned.val(data=data, imgsz=imgsz, split="val", plots=True)
    row1 = metrics_row("after fine-tune", best_pt, m1)
    append_csv(row1); rows.append(row1)

    shutil.copy(best_pt, out_name)
    print(f"\nSaved weights → {out_name}")
    print_table(rows)

    d_map = row1["mAP50_mask"] - row0["mAP50_mask"]
    d_p = row1["precision_mask"] - row0["precision_mask"]
    print(f"\nΔ mAP50(mask): +{d_map:.4f}   Δ precision(mask): +{d_p:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["parts", "damage"], required=True)
    ap.add_argument("--data", default=None,
                    help="dataset yaml (default: carparts-seg.yaml for parts)")
    ap.add_argument("--base-weights", default=None)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=None)
    args = ap.parse_args()

    if args.stage == "parts":
        data = args.data or "carparts-seg.yaml"        # ships with ultralytics
        base = args.base_weights or "yolo11n-seg.pt"   # COCO pretrain
        imgsz = args.imgsz or 640
        run_stage("parts", data, base, args.epochs, imgsz, "parts_best.pt")
    else:
        if not args.data:
            raise SystemExit("--data cardd.yaml tələb olunur (CarDD formatlı dataset)")
        if args.base_weights:
            base = args.base_weights
        else:
            from huggingface_hub import hf_hub_download
            base = hf_hub_download(
                repo_id="harpreetsahota/car-dd-segmentation-yolov11",
                filename="best.pt")
        imgsz = args.imgsz or 1024                     # small cracks need res
        run_stage("damage", args.data, base, args.epochs, imgsz, "cardd_best.pt")


if __name__ == "__main__":
    main()
