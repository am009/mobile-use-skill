"""
Deterministic overlay renderer for grounding actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

from .types import OperatorAction, OverlayArtifact


def render_overlay(image_path: Path, action: OperatorAction, output_path: Path) -> OverlayArtifact:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError("Failed to load screenshot for overlay rendering: %s" % image_path)

    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    overlay = image.copy()

    cross_size = max(18, min(width, height) // 24)
    thickness = max(2, min(width, height) // 220)
    description = visual_description(action)

    if action.action_type in ("tap", "long_press") and action.point_px:
        _draw_cross(mask, action.point_px, cross_size, thickness)
        if action.action_type == "long_press":
            ring_radius = max(cross_size, 28)
            cv2.circle(mask, action.point_px, ring_radius, 255, thickness, cv2.LINE_AA)
        overlay = _blend_inverse_mask(overlay, mask)
        _draw_focus_point(overlay, action.point_px)
        if action.action_type == "long_press" and action.duration_ms:
            _draw_anchor_text(
                overlay,
                "long press %dms" % action.duration_ms,
                (action.point_px[0] + cross_size + 12, action.point_px[1] - 8),
            )
    elif action.action_type == "swipe" and action.start_px and action.end_px:
        _draw_cross(mask, action.start_px, cross_size, thickness)
        _draw_cross(mask, action.end_px, cross_size, thickness)
        cv2.arrowedLine(
            mask,
            action.start_px,
            action.end_px,
            255,
            thickness,
            line_type=cv2.LINE_AA,
            tipLength=0.04,
        )
        overlay = _blend_inverse_mask(overlay, mask)
        _draw_focus_point(overlay, action.start_px, filled=True)
        _draw_focus_point(overlay, action.end_px, filled=False)
        if action.duration_ms:
            mid_x = int(round((action.start_px[0] + action.end_px[0]) / 2.0))
            mid_y = int(round((action.start_px[1] + action.end_px[1]) / 2.0))
            _draw_anchor_text(overlay, "swipe %dms" % action.duration_ms, (mid_x + 12, mid_y - 8))
    else:
        raise RuntimeError("Unsupported action for rendering: %s" % action.action_type)

    _draw_top_banner(overlay, description)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), overlay):
        raise RuntimeError("Failed to write overlay image: %s" % output_path)

    return OverlayArtifact(path=output_path, description=description, image_size=(width, height))


def visual_description(action: OperatorAction) -> str:
    width, height = action.screen_size
    if action.action_type == "swipe" and action.start_px and action.end_px:
        if action.target_desc.startswith("从"):
            return action.target_desc
        start_zone = _describe_zone(action.start_px[0], action.start_px[1], width, height)
        end_zone = _describe_zone(action.end_px[0], action.end_px[1], width, height)
        return "从%s拖动到%s以%s" % (start_zone, end_zone, action.target_desc)

    if not action.point_px:
        return action.target_desc

    verb = "点击" if action.action_type == "tap" else "长按"
    if _contains_location_hint(action.target_desc):
        return "%s%s" % (verb, action.target_desc)
    zone = _describe_zone(action.point_px[0], action.point_px[1], width, height)
    return "%s%s的%s" % (verb, zone, action.target_desc)


def _blend_inverse_mask(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    result = image.copy()
    active = mask > 0
    if not np.any(active):
        return result
    base = image.astype(np.float32)
    inverted = 255.0 - base
    blended = (base * 0.35) + (inverted * 0.65)
    result[active] = np.clip(blended[active], 0, 255).astype(np.uint8)
    return result


def _draw_cross(mask: np.ndarray, point: Tuple[int, int], size: int, thickness: int) -> None:
    x, y = point
    cv2.line(mask, (x - size, y), (x + size, y), 255, thickness, cv2.LINE_AA)
    cv2.line(mask, (x, y - size), (x, y + size), 255, thickness, cv2.LINE_AA)


def _draw_focus_point(image: np.ndarray, point: Tuple[int, int], filled: bool = True) -> None:
    radius = max(4, min(image.shape[:2]) // 140)
    outline = _contrast_color(image, point)
    if filled:
        fill_color = tuple(int(channel) for channel in outline)
        cv2.circle(image, point, radius, fill_color, -1, cv2.LINE_AA)
        border = (255 - fill_color[0], 255 - fill_color[1], 255 - fill_color[2])
        cv2.circle(image, point, radius + 2, border, 1, cv2.LINE_AA)
        return
    cv2.circle(image, point, radius + 2, outline, 2, cv2.LINE_AA)


def _contrast_color(image: np.ndarray, point: Tuple[int, int]) -> Tuple[int, int, int]:
    x = max(0, min(point[0], image.shape[1] - 1))
    y = max(0, min(point[1], image.shape[0] - 1))
    b, g, r = image[y, x]
    luminance = (0.114 * b) + (0.587 * g) + (0.299 * r)
    if luminance >= 128:
        return (20, 20, 20)
    return (245, 245, 245)


def _draw_anchor_text(image: np.ndarray, text: str, origin: Tuple[int, int]) -> None:
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = max(0.45, min(image.shape[:2]) / 1400.0)
    thickness = 1
    text_size, baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x = max(8, min(origin[0], image.shape[1] - text_size[0] - 16))
    y = max(text_size[1] + 12, min(origin[1], image.shape[0] - baseline - 8))
    overlay = image.copy()
    cv2.rectangle(
        overlay,
        (x - 6, y - text_size[1] - 8),
        (x + text_size[0] + 6, y + baseline + 6),
        (0, 0, 0),
        -1,
    )
    cv2.addWeighted(overlay, 0.45, image, 0.55, 0.0, image)
    cv2.putText(image, text, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)


def _draw_top_banner(image: np.ndarray, text: str) -> None:
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = max(0.55, min(image.shape[:2]) / 1250.0)
    thickness = 1
    text_size, baseline = cv2.getTextSize(text, font, font_scale, thickness)
    banner_height = text_size[1] + baseline + 18
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (image.shape[1], banner_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.4, image, 0.6, 0.0, image)
    cv2.putText(
        image,
        text,
        (12, banner_height - 8),
        font,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def _describe_zone(x: int, y: int, width: int, height: int) -> str:
    norm_x = x / float(max(width - 1, 1))
    norm_y = y / float(max(height - 1, 1))

    if norm_x <= 0.33 and norm_y <= 0.25:
        return "屏幕左上角"
    if norm_x >= 0.67 and norm_y <= 0.25:
        return "屏幕右上角"
    if norm_x <= 0.33 and norm_y >= 0.75:
        return "屏幕左下角"
    if norm_x >= 0.67 and norm_y >= 0.75:
        return "屏幕右下角"

    horiz = _describe_horizontal(norm_x)
    vert = _describe_vertical(norm_y)
    if vert == "中部" and horiz == "中间":
        return "屏幕中部"
    if horiz == "中间" and vert != "中部":
        return "屏幕%s" % vert
    if vert == "中部" and horiz != "中间":
        return "屏幕%s" % horiz
    return "屏幕%s%s" % (horiz, vert)


def _describe_horizontal(value: float) -> str:
    if value < 0.28:
        return "左侧"
    if value < 0.45:
        return "偏左"
    if value < 0.55:
        return "中间"
    if value < 0.72:
        return "偏右"
    return "右侧"


def _describe_vertical(value: float) -> str:
    if value < 0.16:
        return "上方"
    if value < 0.38:
        return "上部"
    if value < 0.62:
        return "中部"
    if value < 0.82:
        return "下部"
    return "底部"


def _contains_location_hint(text: str) -> bool:
    hints = [
        "左上",
        "右上",
        "左下",
        "右下",
        "上方",
        "上部",
        "下方",
        "下部",
        "底部",
        "中间",
        "中部",
        "左侧",
        "右侧",
        "偏左",
        "偏右",
        "顶部",
    ]
    return any(hint in text for hint in hints)
