#!/usr/bin/env python3
"""
CrashLogic / DentScan — Annotation overlay
==========================================
Draws the two models' masks on the original photo:
  * part masks   — translucent, one colour per part class, thin outline
  * damage masks — bold red overlay, labelled with the damage type AND the
                   part it was fused onto + severity (e.g. "scratch→front_bumper_cover (minor)")

Labels are ASCII (part codes / damage types) so they render fine with OpenCV.
"""

import hashlib
import numpy as np
import cv2


def _color(name: str) -> tuple:
    """Deterministic BGR colour per class name."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    b, g, r = h & 255, (h >> 8) & 255, (h >> 16) & 255
    # push away from too-dark values for visibility
    return (int(80 + b % 176), int(80 + g % 176), int(80 + r % 176))


def _fit_mask(mask: np.ndarray, shape: tuple) -> np.ndarray:
    mask = mask.astype(np.uint8)
    if mask.shape[:2] != shape[:2]:
        mask = cv2.resize(mask, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return mask.astype(bool)


def _overlay(img, mask, color, alpha):
    mask = _fit_mask(mask, img.shape)
    if not mask.any():
        return mask
    ov = img.copy()
    ov[mask] = color
    cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(img, cnts, -1, color, 2)
    return mask


def _label(img, text, mask, color, font=0.5):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return
    x, y = int(xs.min()), int(ys.min())
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font, 1)
    y = max(y, th + 8)
    cv2.rectangle(img, (x, y - th - 8), (x + tw + 8, y), color, -1)
    cv2.putText(img, text, (x + 4, y - 5), cv2.FONT_HERSHEY_SIMPLEX, font,
                (255, 255, 255), 1, cv2.LINE_AA)


def draw_annotations(image_path, part_dets, damage_dets, out_path, assignments=None):
    """Render part + damage masks onto image_path and save to out_path."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Şəkil oxunmadı: {image_path}")

    # 1) parts — light context layer
    for d in part_dets:
        c = _color("part_" + d["class_name"])
        m = _overlay(img, d["mask"], c, alpha=0.22)
        _label(img, d["class_name"], m, c, font=0.45)

    # 2) damage — bold, with fused part label
    by_idx = {a["damage_idx"]: a for a in (assignments or [])}
    for i, d in enumerate(damage_dets):
        c = (0, 0, 220)  # red (BGR)
        m = _overlay(img, d["mask"], c, alpha=0.45)
        a = by_idx.get(i)
        if a and not a.get("orphan"):
            txt = f'{d["class_name"]}->{a["part_code"]} ({a["severity"]})'
        else:
            txt = f'{d["class_name"]} (?)'
        _label(img, txt, m, c, font=0.5)

    cv2.imwrite(out_path, img)
    return out_path


# ── offline selftest: synthetic scene, no model/photo needed ─────────────
def _selftest():
    import os
    H, W = 240, 360
    img = np.full((H, W, 3), 60, np.uint8)
    cv2.imwrite("_blank.jpg", img)

    def rect(y0, y1, x0, x1):
        m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = True; return m

    part_dets = [
        {"class_name": "front_bumper", "mask": rect(170, 240, 0, 360), "confidence": 0.95},
        {"class_name": "hood",         "mask": rect(70, 170, 40, 320), "confidence": 0.92},
    ]
    damage_dets = [
        {"class_name": "scratch", "mask": rect(190, 205, 120, 200), "confidence": 0.81},
        {"class_name": "dent",    "mask": rect(90, 150, 90, 200),   "confidence": 0.77},
    ]
    from fusion import assign_damages
    asg = assign_damages(part_dets, damage_dets)
    out = draw_annotations("_blank.jpg", part_dets, damage_dets, "_annotated.jpg", asg)
    assert os.path.exists(out) and os.path.getsize(out) > 1000
    print("annotate selftest OK →", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    _selftest()
