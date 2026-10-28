#!/usr/bin/env python3
"""Turn each Puddy Chef expression still into a looping green-screen video.

The stills are crops of the official expression sheet. Background is removed,
then each pose gets a seamless idle: bounce, squash-and-stretch, sway, blink,
and a prop or limb motion that matches the pose.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STILLS = ROOT / "assets" / "greenscreen"
OUT_DIR = ROOT / "videos"

FPS = 24
SECONDS = 4
NFRAMES = FPS * SECONDS
OUT = 800
UPSCALE = 3
# Classic chroma green.
GREEN = np.array([0.0, 1.0, 0.0], dtype=np.float32)

# Ellipse (cx, cy, rx, ry) and pivot (px, py) are fractions of the still.
# rot is degrees, bob/jump are fractions of sprite height, scale is a fraction.
EXPRESSIONS = [
    {
        "id": "happy",
        "title": "HAPPY",
        "hops": 2, "jump": 0.055, "stretch": 0.08, "squash": 0.10,
        "sway": 5.0, "sway_cycles": 2, "breath": 0.028, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.13, 0.40, 0.11, 0.20), "pivot": (0.24, 0.56), "rot": 18, "cycles": 2},
            {"e": (0.90, 0.52, 0.08, 0.10), "pivot": (0.78, 0.52), "rot": -14, "cycles": 2, "phase": 0.2},
        ],
    },
    {
        "id": "excited",
        "title": "EXCITED",
        "hops": 2, "jump": 0.085, "stretch": 0.11, "squash": 0.12,
        "sway": 6.0, "sway_cycles": 2, "breath": 0.02, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.20, 0.30, 0.16, 0.24), "pivot": (0.32, 0.42), "rot": 24, "cycles": 2},
            {"e": (0.84, 0.55, 0.13, 0.16), "pivot": (0.72, 0.52), "rot": 14, "cycles": 2, "phase": 0.2},
        ],
        "fx": ["sparkle"],
    },
    {
        "id": "love",
        "title": "LOVE",
        "hops": 2, "jump": 0.04, "stretch": 0.06, "squash": 0.07,
        "sway": 3.5, "sway_cycles": 1, "breath": 0.03, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.62, 0.62, 0.20, 0.18), "pivot": (0.62, 0.62), "scale": 0.10, "cycles": 2},
        ],
        "fx": ["hearts"],
    },
    {
        "id": "laughing",
        "title": "LAUGHING",
        "hops": 4, "jump": 0.045, "stretch": 0.07, "squash": 0.11,
        "sway": 4.5, "sway_cycles": 4, "breath": 0.02, "breath_cycles": 4,
        "blink": True,
        "parts": [
            {"e": (0.82, 0.38, 0.15, 0.26), "pivot": (0.68, 0.48), "rot": 18, "cycles": 4},
        ],
    },
    {
        "id": "sad",
        "title": "SAD",
        "hops": 1, "jump": 0.018, "stretch": 0.03, "squash": 0.05,
        "sway": 3.5, "sway_cycles": 1, "breath": 0.035, "breath_cycles": 1,
        "blink": True, "blink_at": 0.72,
        "pivot": "center",
        "parts": [
            {"e": (0.16, 0.58, 0.12, 0.16), "pivot": (0.28, 0.50), "rot": 8, "cycles": 1},
            {"e": (0.84, 0.56, 0.12, 0.16), "pivot": (0.72, 0.50), "rot": -8, "cycles": 1},
        ],
    },
    {
        "id": "surprised",
        "title": "SURPRISED",
        "hops": 2, "jump": 0.07, "stretch": 0.12, "squash": 0.13,
        "sway": 2.5, "sway_cycles": 2, "breath": 0.015, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.18, 0.52, 0.12, 0.14), "pivot": (0.30, 0.50), "rot": 12, "cycles": 2},
            {"e": (0.80, 0.50, 0.12, 0.14), "pivot": (0.68, 0.50), "rot": -12, "cycles": 2},
        ],
    },
    {
        "id": "thinking",
        "title": "THINKING",
        "hops": 1, "jump": 0.02, "stretch": 0.04, "squash": 0.05,
        "sway": 6.0, "sway_cycles": 1, "breath": 0.025, "breath_cycles": 1,
        "blink": True, "blink_at": 0.4,
        "parts": [
            {"e": (0.14, 0.30, 0.10, 0.14), "pivot": (0.14, 0.30), "bob": 0.045, "rot": -8, "cycles": 1},
        ],
    },
    {
        "id": "urgent",
        "title": "URGENT",
        "hops": 4, "jump": 0.05, "stretch": 0.08, "squash": 0.10,
        "sway": 3.5, "sway_cycles": 4, "breath": 0.015, "breath_cycles": 4,
        "blink": True,
        "parts": [
            {"e": (0.28, 0.50, 0.16, 0.26), "pivot": (0.40, 0.48), "rot": 22, "cycles": 4},
            {"e": (0.84, 0.66, 0.16, 0.18), "pivot": (0.74, 0.58), "rot": -16, "cycles": 4, "phase": 0.25},
        ],
        "fx": ["sparkle"],
    },
    {
        "id": "angry",
        "title": "ANGRY",
        "hops": 4, "jump": 0.028, "stretch": 0.05, "squash": 0.09,
        "sway": 3.2, "sway_cycles": 4, "breath": 0.02, "breath_cycles": 2,
        "blink": True,
        "parts": [],
        "fx": ["steam"],
    },
    {
        "id": "sleepy",
        "title": "SLEEPY",
        "hops": 1, "jump": 0.012, "stretch": 0.035, "squash": 0.02,
        "sway": 5.5, "sway_cycles": 1, "breath": 0.05, "breath_cycles": 1,
        "blink": False,
        "pivot": "center",
        "parts": [],
        "fx": ["zzz"],
    },
    {
        "id": "yummy",
        "title": "YUMMY",
        "hops": 2, "jump": 0.04, "stretch": 0.06, "squash": 0.08,
        "sway": 3.5, "sway_cycles": 2, "breath": 0.025, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.12, 0.58, 0.12, 0.26), "pivot": (0.24, 0.52), "rot": 22, "cycles": 1},
        ],
        "fx": ["hearts"],
    },
    {
        "id": "proud",
        "title": "PROUD",
        "hops": 2, "jump": 0.05, "stretch": 0.07, "squash": 0.08,
        "sway": 4.0, "sway_cycles": 1, "breath": 0.03, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.20, 0.36, 0.15, 0.28), "pivot": (0.34, 0.46), "rot": 16, "cycles": 1},
            {"e": (0.86, 0.58, 0.12, 0.16), "pivot": (0.74, 0.54), "rot": 12, "cycles": 1, "phase": 0.2},
        ],
        "fx": ["sparkle"],
    },
    {
        "id": "cooking",
        "title": "COOKING",
        "hops": 2, "jump": 0.035, "stretch": 0.05, "squash": 0.07,
        "sway": 3.0, "sway_cycles": 2, "breath": 0.02, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.40, 0.72, 0.14, 0.10), "pivot": (0.50, 0.78), "rot": 26, "cycles": 2},
        ],
    },
    {
        "id": "serving",
        "title": "SERVING",
        "hops": 2, "jump": 0.04, "stretch": 0.06, "squash": 0.07,
        "sway": 3.5, "sway_cycles": 1, "breath": 0.022, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.80, 0.48, 0.18, 0.16), "pivot": (0.66, 0.52), "bob": 0.035, "rot": 8, "cycles": 1},
        ],
    },
    {
        "id": "waving",
        "title": "WAVING",
        "hops": 2, "jump": 0.05, "stretch": 0.07, "squash": 0.08,
        "sway": 3.5, "sway_cycles": 2, "breath": 0.02, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.86, 0.54, 0.09, 0.09), "pivot": (0.70, 0.56), "rot": 26, "cycles": 2},
        ],
    },
    {
        "id": "running",
        "title": "RUNNING",
        "hops": 4, "jump": 0.07, "stretch": 0.10, "squash": 0.12,
        "sway": 7.0, "sway_cycles": 2, "breath": 0.015, "breath_cycles": 4,
        "blink": True,
        "parts": [
            {"e": (0.30, 0.86, 0.14, 0.12), "pivot": (0.38, 0.76), "bob": 0.05, "cycles": 4},
            {"e": (0.55, 0.88, 0.14, 0.12), "pivot": (0.48, 0.76), "bob": 0.05, "cycles": 4, "phase": 0.5},
            {"e": (0.84, 0.42, 0.12, 0.16), "pivot": (0.74, 0.55), "rot": 16, "cycles": 4},
        ],
    },
    {
        "id": "menu",
        "title": "HOLDING MENU",
        "hops": 2, "jump": 0.035, "stretch": 0.05, "squash": 0.06,
        "sway": 3.0, "sway_cycles": 1, "breath": 0.022, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.58, 0.64, 0.24, 0.26), "pivot": (0.50, 0.55), "rot": 8, "cycles": 1},
        ],
    },
    {
        "id": "gifting",
        "title": "GIFTING",
        "hops": 2, "jump": 0.045, "stretch": 0.06, "squash": 0.07,
        "sway": 3.5, "sway_cycles": 1, "breath": 0.024, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.58, 0.66, 0.22, 0.20), "pivot": (0.55, 0.58), "scale": 0.08, "bob": 0.03, "cycles": 1},
        ],
        "fx": ["sparkle"],
    },
    {
        "id": "cheering",
        "title": "CHEERING",
        "hops": 2, "jump": 0.09, "stretch": 0.12, "squash": 0.12,
        "sway": 4.0, "sway_cycles": 2, "breath": 0.02, "breath_cycles": 2,
        "blink": True,
        "parts": [
            {"e": (0.24, 0.30, 0.18, 0.28), "pivot": (0.36, 0.46), "rot": 28, "cycles": 2},
        ],
        "fx": ["sparkle"],
    },
]


def sine(t: float, cycles: float, phase: float = 0.0) -> float:
    return math.sin(2 * math.pi * (cycles * t + phase))


def bounce(t: float, hops: int, jump: float, stretch: float, squash: float):
    """Return scale_y, scale_x, translation as a fraction of height (up is negative)."""
    if hops <= 0:
        return 1.0, 1.0, 0.0
    cycle = (t * hops) % 1.0
    air = math.sin(math.pi * cycle)
    land = max(0.0, math.cos(2 * math.pi * cycle)) ** 2
    sy = 1.0 + stretch * air - squash * land
    sy = max(0.78, sy)
    sx = 1.0 / (sy ** 0.65)
    return sy, sx, -air * jump


def ellipse_weight(shape, e, pivot, bbox) -> np.ndarray:
    """Part mask. e and pivot are fractions of the opaque bounding box."""
    h, w = shape
    x0, y0, x1, y1 = bbox
    bw = max(1.0, float(x1 - x0))
    bh = max(1.0, float(y1 - y0))
    cx = x0 + e[0] * bw
    cy = y0 + e[1] * bh
    rx = max(e[2] * bw, 1.0)
    ry = max(e[3] * bh, 1.0)
    px = x0 + pivot[0] * bw
    py = y0 + pivot[1] * bh
    ys, xs = np.mgrid[0:h, 0:w]
    dx = (xs - cx) / rx
    dy = (ys - cy) / ry
    radial = np.sqrt(dx * dx + dy * dy)
    inside = np.clip((1.02 - radial) / 0.22, 0.0, 1.0).astype(np.float32)
    arm = np.array([cx - px, cy - py], dtype=np.float32)
    alen = float(np.linalg.norm(arm))
    if alen < bh * 0.05:
        weight = inside
    else:
        arm /= alen
        proj = (xs - px) * arm[0] + (ys - py) * arm[1]
        shoulder = np.clip((proj + 0.04 * bh) / (0.08 * bh), 0.0, 1.0).astype(np.float32)
        weight = inside * shoulder
    weight = cv2.GaussianBlur(weight, (0, 0), 1.2)
    return np.clip(weight, 0.0, 1.0)


def key_green(path: Path) -> np.ndarray:
    """Key a generated chroma still. Returns straight RGBA float, RGB 0..1."""
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    # The jpeg green sits near RGB(32, 212, 34), not a perfect 0,255,0.
    greenness = green - np.maximum(red, blue)
    alpha = np.clip((78.0 - greenness) / 36.0, 0.0, 1.0)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.6)
    alpha = np.clip((alpha - 0.08) / 0.92, 0.0, 1.0)
    # Pull green spill out of the edge so the fringe does not glow.
    cap = np.maximum(red, blue)
    rgb[:, :, 1] = np.minimum(green, cap + (1.0 - alpha) * 0.0)
    rgb[:, :, 1] = np.minimum(rgb[:, :, 1], cap)
    rgb = np.clip(rgb / 255.0, 0.0, 1.0)
    return np.dstack([rgb, alpha.astype(np.float32)])


def find_eyes(alpha: np.ndarray, rgb: np.ndarray):
    a = alpha
    ys, xs = np.where(a > 0.6)
    if len(xs) < 30:
        return []
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    bh = y1 - y0 + 1
    bw = x1 - x0 + 1
    # Eyes sit on the face, under the caramel band. A higher window
    # catches dark caramel spots and paints eyelids in the wrong place.
    fy0, fy1 = y0 + int(0.50 * bh), y0 + int(0.64 * bh)
    fx0, fx1 = x0 + int(0.28 * bw), x0 + int(0.74 * bw)
    fy0, fx0 = max(0, fy0), max(0, fx0)
    fy1, fx1 = min(a.shape[0], fy1), min(a.shape[1], fx1)
    if fy1 <= fy0 or fx1 <= fx0:
        return []
    sub = rgb[fy0:fy1, fx0:fx1]
    suba = a[fy0:fy1, fx0:fx1]
    lum = sub.mean(axis=2)
    dark = ((lum < 0.16) & (suba > 0.65) & (sub[:, :, 0] < 0.22)).astype(np.uint8)
    count, labels, stats, cent = cv2.connectedComponentsWithStats(dark, 8)
    eyes = []
    for i in range(1, count):
        area = int(stats[i, cv2.CC_STAT_AREA])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if area < 12 or area > 280 or hh > ww * 1.6 or ww > bw * 0.22:
            continue
        cx = fx0 + float(cent[i][0])
        cy = fy0 + float(cent[i][1])
        eyes.append((cx, cy, ww, hh, area))
    if not eyes:
        return []
    eyes.sort(key=lambda e: e[1])
    top_y = eyes[0][1]
    eyes = [e for e in eyes if e[1] <= top_y + max(12, e[3] * 1.5)]
    eyes.sort(key=lambda e: -e[4])
    return eyes[:2]


def cream_color(rgb, alpha, cx, cy) -> np.ndarray:
    h, w, _ = rgb.shape
    r = 14
    x0, x1 = max(0, int(cx) - r), min(w, int(cx) + r)
    y0, y1 = max(0, int(cy) - r), min(h, int(cy) + r)
    patch = rgb[y0:y1, x0:x1]
    pa = alpha[y0:y1, x0:x1]
    lum = patch.mean(axis=2)
    sat = patch.max(axis=2) - patch.min(axis=2)
    sel = (pa > 0.7) & (lum > 0.72) & (sat > 0.08) & (sat < 0.45)
    if sel.sum() < 8:
        return np.array([0.98, 0.86, 0.70], dtype=np.float32)
    return np.median(patch[sel], axis=0).astype(np.float32)


def apply_blink(rgba: np.ndarray, eyes, amount: float) -> np.ndarray:
    if amount <= 0.02 or not eyes:
        return rgba
    out = rgba.copy()
    rgb = out[:, :, :3]
    alpha = out[:, :, 3]
    overlay = np.zeros(alpha.shape, np.float32)
    for cx, cy, ww, hh, _area in eyes:
        color = cream_color(rgb, alpha, cx, cy)
        axes = (max(2, int(ww * 0.72)), max(2, int(hh * (0.25 + 0.85 * amount))))
        cv2.ellipse(
            overlay,
            (int(round(cx)), int(round(cy))),
            axes,
            0,
            0,
            360,
            float(amount),
            -1,
            lineType=cv2.LINE_AA,
        )
        # Paint only over the character.
        m = overlay > 0
        # Use the last color; eyes share a similar cream. Recompute per eye below.
        region = m.copy()
        # Reset and paint per eye so each eyelid matches nearby cream.
        overlay[:] = 0
        lid = np.zeros_like(rgb)
        cv2.ellipse(
            overlay,
            (int(round(cx)), int(round(cy))),
            axes,
            0,
            0,
            360,
            1.0,
            -1,
            lineType=cv2.LINE_AA,
        )
        sel = (overlay > 0.05) & (alpha > 0.45)
        lid[sel] = color
        a = (overlay * amount)[:, :, None]
        rgb[:] = rgb * (1 - a) + lid * a
        overlay[:] = 0
    return out


def opaque_bbox(alpha: np.ndarray):
    ys, xs = np.where(alpha > 0.2)
    if len(xs) == 0:
        h, w = alpha.shape
        return 0, 0, w - 1, h - 1
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def affine(px, py, ox, oy, sx, sy, rot_deg, tx, ty) -> np.ndarray:
    a = math.radians(rot_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array(
        [
            [sx * c, -sy * s, ox + tx - sx * c * px + sy * s * py],
            [sx * s, sy * c, oy + ty - sx * s * px - sy * c * py],
        ],
        dtype=np.float32,
    )


def compose(dst_rgb: np.ndarray, src: np.ndarray):
    """Src-over. src is straight RGBA float, dst is straight RGB float."""
    a = src[:, :, 3:4]
    dst_rgb[:] = src[:, :, :3] * a + dst_rgb * (1.0 - a)


def warp_rgba(rgba: np.ndarray, matrix: np.ndarray, size: int) -> np.ndarray:
    prem = rgba.copy()
    prem[:, :, :3] *= prem[:, :, 3:4]
    out = cv2.warpAffine(
        prem,
        matrix,
        (size, size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return out


def over_premul(dst_rgb: np.ndarray, prem: np.ndarray):
    a = prem[:, :, 3:4]
    dst_rgb[:] = prem[:, :, :3] + dst_rgb * (1.0 - a)


def heart_layer(size, x, y, scale, color, alpha) -> np.ndarray:
    layer = np.zeros((size, size, 4), np.float32)
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        hx = 16 * math.sin(t) ** 3
        hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append([int(x + hx * scale), int(y + hy * scale * 0.95)])
    mask = np.zeros((size, size), np.uint8)
    cv2.fillPoly(mask, [np.array(pts, np.int32)], 255, lineType=cv2.LINE_AA)
    m = mask.astype(np.float32) / 255.0 * alpha
    layer[:, :, :3] = color
    layer[:, :, 3] = m
    return layer


def draw_fx(dst_rgb: np.ndarray, kinds, t: float, anchor):
    size = dst_rgb.shape[0]
    ax, ay = anchor
    if "hearts" in kinds:
        for i, phase in enumerate((0.0, 0.33, 0.66)):
            p = (t + phase) % 1.0
            fade = math.sin(math.pi * p) ** 1.2
            x = ax + (i - 1) * 70 + math.sin(2 * math.pi * (p + i)) * 18
            y = ay - p * 150
            layer = heart_layer(size, x, y, 0.55 + 0.25 * p, np.array([0.86, 0.16, 0.22], np.float32), 0.9 * fade)
            compose(dst_rgb, layer)
    if "zzz" in kinds:
        for i, phase in enumerate((0.05, 0.38, 0.7)):
            p = (t + phase) % 1.0
            fade = math.sin(math.pi * p)
            x = int(ax + 150 + math.sin(2 * math.pi * p) * 16)
            y = int(ay + 40 - p * 170)
            scale = 0.7 + p * 0.8
            glyph = np.zeros((size, size), np.uint8)
            text = "z" if i < 2 else "Z"
            cv2.putText(
                glyph,
                text,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7 * scale + 0.35,
                255,
                2,
                cv2.LINE_AA,
            )
            layer = np.zeros((size, size, 4), np.float32)
            layer[:, :, 0] = 0.45
            layer[:, :, 1] = 0.26
            layer[:, :, 2] = 0.16
            layer[:, :, 3] = glyph.astype(np.float32) / 255.0 * fade
            compose(dst_rgb, layer)
    if "steam" in kinds:
        for i, phase in enumerate((0.0, 0.5)):
            p = (t * 2 + phase) % 1.0
            fade = math.sin(math.pi * p)
            x = int(ax + 40 + i * 36 + math.sin(2 * math.pi * p) * 10)
            y = int(ay + 10 - p * 120)
            radius = int(8 + 10 * p)
            layer = np.zeros((size, size, 4), np.float32)
            glyph = np.zeros((size, size), np.uint8)
            cv2.circle(glyph, (x, y), radius, 255, -1, lineType=cv2.LINE_AA)
            layer[:, :, 0] = 0.82
            layer[:, :, 1] = 0.75
            layer[:, :, 2] = 0.68
            layer[:, :, 3] = glyph.astype(np.float32) / 255.0 * 0.45 * fade
            compose(dst_rgb, layer)
    if "sparkle" in kinds:
        for i, phase in enumerate((0.0, 0.25, 0.5, 0.75)):
            p = (t + phase) % 1.0
            fade = math.sin(math.pi * p) ** 1.4
            ang = 2 * math.pi * (i / 4 + t)
            dist = 150 + (i % 2) * 40
            x = int(ax + math.cos(ang) * dist * 0.75)
            y = int(ay + 80 + math.sin(ang) * 70)
            layer = np.zeros((size, size, 4), np.float32)
            length = int(7 + 8 * fade)
            glyph = np.zeros((size, size), np.uint8)
            cv2.line(glyph, (x - length, y), (x + length, y), 255, 2, cv2.LINE_AA)
            cv2.line(glyph, (x, y - length), (x, y + length), 255, 2, cv2.LINE_AA)
            layer[:, :, 0] = 1.0
            layer[:, :, 1] = 0.82
            layer[:, :, 2] = 0.35
            layer[:, :, 3] = glyph.astype(np.float32) / 255.0 * fade
            compose(dst_rgb, layer)


def prepare(expr: dict):
    rgba = key_green(STILLS / f"{expr['id']}-green.jpg")
    alpha = rgba[:, :, 3]
    x0, y0, x1, y1 = opaque_bbox(alpha)
    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)
    if expr.get("pivot") == "center":
        pivot = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        # Rock around the visual center, sit the body a little lower.
        out_pivot = (OUT / 2.0, OUT * 0.56)
    else:
        pivot = ((x0 + x1) / 2.0, float(y1))
        out_pivot = (OUT / 2.0, OUT * 0.90)
    fit = min(OUT * 0.70 / bh, OUT * 0.82 / bw)
    eyes = find_eyes(alpha, rgba[:, :, :3]) if expr.get("blink", True) else []
    h, w = alpha.shape
    bbox = (x0, y0, x1, y1)
    parts = []
    remaining = np.ones((h, w), np.float32)
    for part in expr.get("parts", []):
        weight = ellipse_weight((h, w), part["e"], part["pivot"], bbox) * remaining
        remaining = remaining * (1.0 - np.clip(weight, 0, 1))
        parts.append((part, weight))
    print(
        f"  keyed {expr['id']:12} {w}x{h} bbox {bw}x{bh} fit {fit:.3f} eyes {len(eyes)} fg {alpha.mean():.2f}"
    )
    return {
        "rgba": rgba,
        "pivot": pivot,
        "out_pivot": out_pivot,
        "fit": fit,
        "bh": bh,
        "eyes": eyes,
        "parts": parts,
        "body_weight": remaining,
        "bbox": bbox,
    }


def render_frame(expr, prep, t: float) -> np.ndarray:
    rgba = prep["rgba"]
    h, w = rgba.shape[:2]
    body_sy, body_sx, ty_frac = bounce(
        t, expr["hops"], expr["jump"], expr["stretch"], expr["squash"]
    )
    breath = expr.get("breath", 0.0) * sine(t, expr.get("breath_cycles", 1))
    body_sy *= 1.0 + breath
    body_sx *= 1.0 - breath * 0.55
    sway = expr.get("sway", 0.0) * sine(t, expr.get("sway_cycles", 1))
    fit = prep["fit"]
    px, py = prep["pivot"]
    ox, oy = prep["out_pivot"]
    trans_y = ty_frac * prep["bh"] * fit
    body = affine(px, py, ox, oy, fit * body_sx, fit * body_sy, sway, 0.0, trans_y)

    blinked = rgba
    if prep["eyes"]:
        amount = 0.0
        center = expr.get("blink_at", 0.62)
        width = 0.055
        x = (t - center) / width
        if abs(x) < 1:
            amount = 0.5 * (1 + math.cos(math.pi * x))
        blinked = apply_blink(rgba, prep["eyes"], amount)

    # Whole-body motion only. Bending a single still tears the whisk and the
    # face, so each pose keeps its drawing and lives through bounce, sway, and
    # squash-and-stretch.
    canvas = np.zeros((OUT, OUT, 3), np.float32)
    canvas[:, :] = GREEN
    over_premul(canvas, warp_rgba(blinked, body, OUT))

    anchor = (ox + math.sin(sway * math.pi / 180.0) * 10, oy - prep["bh"] * fit * body_sy * 0.92 + trans_y)
    draw_fx(canvas, expr.get("fx", []), t, anchor)
    frame = np.clip(canvas * 255.0, 0, 255).astype(np.uint8)
    return frame


def encode_frames(frames, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{frames[0].shape[1]}x{frames[0].shape[0]}",
        "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-color_range", "pc",
        "-crf", "14",
        "-preset", "medium",
        "-tune", "animation",
        "-movflags", "+faststart",
        str(path),
    ]
    proc = subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode()[-2000:])
        raise RuntimeError(f"ffmpeg failed for {path}")


def render_expression(expr, prep, limit=None):
    frames = []
    count = NFRAMES if limit is None else limit
    for i in range(count):
        t = i / NFRAMES
        frames.append(render_frame(expr, prep, t))
    return frames


def save_strip(frames, path: Path):
    h, w, _ = frames[0].shape
    sheet = np.zeros((h, w * len(frames), 3), np.uint8)
    for i, frame in enumerate(frames):
        sheet[:, i * w : (i + 1) * w] = frame
    # Downscale for viewing.
    small = cv2.resize(sheet, (w * len(frames) // 2, h // 2), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), cv2.cvtColor(small, cv2.COLOR_RGB2BGR))


def test(names):
    wanted = set(names)
    exprs = [e for e in EXPRESSIONS if e["id"] in wanted] if names else EXPRESSIONS[:4]
    preview = Path("/tmp/preview")
    preview.mkdir(exist_ok=True)
    for expr in exprs:
        print("prep", expr["id"])
        prep = prepare(expr)
        # 8 poses across the loop, plus a still key check.
        frames = [render_frame(expr, prep, i / 8) for i in range(8)]
        save_strip(frames, preview / f"{expr['id']}_strip.png")
        still = (prep["rgba"][:, :, :3] * 255).astype(np.uint8)
        bg = np.zeros_like(still)
        bg[:, :] = (255, 0, 255)
        a = prep["rgba"][:, :, 3:4]
        comp = still * a + bg * (1 - a)
        comp_u8 = comp.astype(np.uint8)
        for cx, cy, ww, hh, _area in prep["eyes"]:
            cv2.rectangle(
                comp_u8,
                (int(cx - ww / 2), int(cy - hh / 2)),
                (int(cx + ww / 2), int(cy + hh / 2)),
                (0, 255, 0),
                1,
            )
        cv2.imwrite(str(preview / f"{expr['id']}_key.png"), cv2.cvtColor(comp_u8, cv2.COLOR_RGB2BGR))
        part = np.zeros(prep["body_weight"].shape, np.float32)
        for _part, weight in prep["parts"]:
            part = np.maximum(part, weight)
        overlay = still.copy()
        overlay[:, :, 0] = np.clip(overlay[:, :, 0] * (1 - part) + 255 * part, 0, 255)
        cv2.imwrite(
            str(preview / f"{expr['id']}_parts.png"),
            cv2.cvtColor(overlay.astype(np.uint8), cv2.COLOR_RGB2BGR),
        )
        print("  wrote", expr["id"])


def render_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for expr in EXPRESSIONS:
        print("render", expr["id"])
        prep = prepare(expr)
        frames = render_expression(expr, prep)
        path = OUT_DIR / f"{expr['id']}.mp4"
        encode_frames(frames, path)
        paths.append(path)
        print("  wrote", path, "bytes", path.stat().st_size)
    build_grid(paths)
    build_contact()


def build_grid(paths):
    cell = 384
    cols = 5
    rows = 4
    layout = "|".join(f"{(i % cols) * cell}_{(i // cols) * cell}" for i in range(len(paths)))
    out = OUT_DIR / "puddy-chef-all.mp4"
    cmd = ["ffmpeg", "-y"]
    for p in paths:
        cmd += ["-i", str(p)]
    scaled = "".join(f"[{i}:v]scale={cell}:{cell}:flags=lanczos,setsar=1[v{i}];" for i in range(len(paths)))
    inputs = "".join(f"[v{i}]" for i in range(len(paths)))
    fc = (
        f"{scaled}{inputs}xstack=inputs={len(paths)}:layout={layout}:fill=0x00FF00[out]"
    )
    cmd += [
        "-filter_complex", fc,
        "-map", "[out]",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-color_range", "pc",
        "-crf", "16",
        "-preset", "medium",
        "-tune", "animation",
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode()[-2500:])
        raise RuntimeError("grid ffmpeg failed")
    print("grid", out, out.stat().st_size)


def build_contact():
    """One labeled still of every expression on green, for identification."""
    cols = 5
    cell = 320
    rows = 4
    sheet = np.zeros((rows * cell, cols * cell, 3), np.uint8)
    sheet[:, :] = (0, 255, 0)
    for i, expr in enumerate(EXPRESSIONS):
        prep = prepare(expr)
        frame = render_frame(expr, prep, 0.18)
        thumb = cv2.resize(frame, (cell - 16, cell - 36), interpolation=cv2.INTER_AREA)
        r, c = divmod(i, cols)
        y = r * cell + 8
        x = c * cell + 8
        sheet[y : y + thumb.shape[0], x : x + thumb.shape[1]] = thumb
        cv2.putText(
            sheet,
            expr["title"],
            (c * cell + 12, r * cell + cell - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (70, 30, 20),
            2,
            cv2.LINE_AA,
        )
    path = OUT_DIR / "contact-sheet.png"
    cv2.imwrite(str(path), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print("contact", path)


def main():
    args = sys.argv[1:]
    if args and args[0] == "test":
        test(args[1:])
    else:
        render_all()


if __name__ == "__main__":
    main()
