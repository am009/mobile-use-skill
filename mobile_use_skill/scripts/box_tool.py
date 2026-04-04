#!/usr/bin/env python3
"""
Bounding-box crop and map-back helper for multi-pass mobile localization.
"""

import argparse
import json
from pathlib import Path
from typing import List, Sequence

import cv2


def _load_image(path: str):
    image = cv2.imread(path)
    if image is None:
        raise RuntimeError(f"Failed to read image: {path}")
    return image


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def _normalize_point(x: int, y: int, width: int, height: int) -> List[int]:
    max_x = max(width - 1, 1)
    max_y = max(height - 1, 1)
    x = _clamp(x, 0, max_x)
    y = _clamp(y, 0, max_y)
    return [
        int(round((x * 999) / max_x)),
        int(round((y * 999) / max_y)),
    ]


def _normalize_bbox(bbox: Sequence[int], width: int, height: int) -> List[int]:
    x1, y1, x2, y2 = bbox
    nx1, ny1 = _normalize_point(x1, y1, width, height)
    nx2, ny2 = _normalize_point(x2, y2, width, height)
    return [nx1, ny1, nx2, ny2]


def _denormalize_axis(value: int, size: int) -> int:
    max_pos = max(size - 1, 1)
    return int(round((value * max_pos) / 999))


def _bbox_from_values(
    values: Sequence[int],
    width: int,
    height: int,
    normalized: bool,
) -> List[int]:
    if len(values) != 4:
        raise ValueError("bbox must contain exactly 4 integers")
    x1, y1, x2, y2 = map(int, values)
    if normalized:
        x1 = _denormalize_axis(x1, width)
        y1 = _denormalize_axis(y1, height)
        x2 = _denormalize_axis(x2, width)
        y2 = _denormalize_axis(y2, height)
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return [left, top, right, bottom]


def _expand_bbox(
    bbox: Sequence[int],
    image_width: int,
    image_height: int,
    padding_ratio: float,
    min_size: int,
) -> List[int]:
    x1, y1, x2, y2 = bbox
    box_width = max(x2 - x1, 1)
    box_height = max(y2 - y1, 1)
    target_width = max(int(round(box_width * (1 + padding_ratio * 2))), min_size)
    target_height = max(int(round(box_height * (1 + padding_ratio * 2))), min_size)

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    crop_x1 = int(round(cx - target_width / 2.0))
    crop_y1 = int(round(cy - target_height / 2.0))
    crop_x2 = crop_x1 + target_width
    crop_y2 = crop_y1 + target_height

    if crop_x1 < 0:
        crop_x2 -= crop_x1
        crop_x1 = 0
    if crop_y1 < 0:
        crop_y2 -= crop_y1
        crop_y1 = 0
    if crop_x2 > image_width:
        overflow = crop_x2 - image_width
        crop_x1 = max(0, crop_x1 - overflow)
        crop_x2 = image_width
    if crop_y2 > image_height:
        overflow = crop_y2 - image_height
        crop_y1 = max(0, crop_y1 - overflow)
        crop_y2 = image_height

    return [crop_x1, crop_y1, crop_x2, crop_y2]


def _center_from_bbox(bbox: Sequence[int]) -> List[int]:
    x1, y1, x2, y2 = bbox
    return [int(round((x1 + x2) / 2)), int(round((y1 + y2) / 2))]


def _relative_bbox(inner: Sequence[int], outer: Sequence[int]) -> List[int]:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, _, _ = outer
    return [ix1 - ox1, iy1 - oy1, ix2 - ox1, iy2 - oy1]


def _draw_grid(image, step: int):
    height, width = image.shape[:2]
    overlay = image.copy()
    line_color = (0, 255, 255)
    text_color = (255, 255, 255)
    bg_color = (0, 0, 0)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1

    marks = list(range(0, 1000, step))
    if marks[-1] != 999:
        marks.append(999)

    for mark in marks:
        x = _denormalize_axis(mark, width)
        y = _denormalize_axis(mark, height)
        cv2.line(overlay, (x, 0), (x, height - 1), line_color, 1)
        cv2.line(overlay, (0, y), (width - 1, y), line_color, 1)

        x_label = f"x={mark}"
        y_label = f"y={mark}"
        cv2.rectangle(overlay, (max(x + 4, 0), 4), (min(x + 54, width - 1), 22), bg_color, -1)
        cv2.rectangle(overlay, (4, max(y + 4, 0)), (58, min(y + 22, height - 1)), bg_color, -1)
        cv2.putText(overlay, x_label, (min(x + 6, width - 48), 17), font, font_scale, text_color, thickness, cv2.LINE_AA)
        cv2.putText(overlay, y_label, (6, min(y + 17, height - 6)), font, font_scale, text_color, thickness, cv2.LINE_AA)

    return cv2.addWeighted(overlay, 0.35, image, 0.65, 0)


def crop_command(args: argparse.Namespace) -> None:
    image = _load_image(args.image)
    height, width = image.shape[:2]

    if not args.bbox:
        raise ValueError("Provide --bbox")
    source_bbox = _bbox_from_values(args.bbox, width, height, args.normalized)

    crop_bbox = _expand_bbox(source_bbox, width, height, args.padding, args.min_size)
    crop_x1, crop_y1, crop_x2, crop_y2 = crop_bbox
    crop = image[crop_y1:crop_y2, crop_x1:crop_x2]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), crop):
        raise RuntimeError(f"Failed to write crop image: {output_path}")

    crop_height, crop_width = crop.shape[:2]
    target_in_crop = _relative_bbox(source_bbox, crop_bbox)
    result = {
        "image_size": [width, height],
        "source_bbox": source_bbox,
        "source_bbox_999": _normalize_bbox(source_bbox, width, height),
        "source_center": _center_from_bbox(source_bbox),
        "crop_bbox": crop_bbox,
        "crop_bbox_999": _normalize_bbox(crop_bbox, width, height),
        "crop_size": [crop_width, crop_height],
        "target_bbox_in_crop": target_in_crop,
        "target_bbox_in_crop_999": _normalize_bbox(target_in_crop, crop_width, crop_height),
        "target_center_in_crop": _center_from_bbox(target_in_crop),
        "output_image": str(output_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def map_command(args: argparse.Namespace) -> None:
    crop_x1, crop_y1, crop_x2, crop_y2 = map(int, args.crop_box)
    crop_width = crop_x2 - crop_x1
    crop_height = crop_y2 - crop_y1
    if crop_width <= 0 or crop_height <= 0:
        raise ValueError("crop_box must define a positive area")

    refined_in_crop = _bbox_from_values(args.bbox, crop_width, crop_height, args.normalized)
    mapped = [
        refined_in_crop[0] + crop_x1,
        refined_in_crop[1] + crop_y1,
        refined_in_crop[2] + crop_x1,
        refined_in_crop[3] + crop_y1,
    ]

    result = {
        "crop_box": [crop_x1, crop_y1, crop_x2, crop_y2],
        "refined_bbox_in_crop": refined_in_crop,
        "refined_center_in_crop": _center_from_bbox(refined_in_crop),
        "mapped_bbox": mapped,
        "mapped_center": _center_from_bbox(mapped),
    }

    if args.image_size:
        width, height = map(int, args.image_size)
        result["mapped_bbox_999"] = _normalize_bbox(mapped, width, height)
        result["mapped_center_999"] = _normalize_point(result["mapped_center"][0], result["mapped_center"][1], width, height)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def grid_command(args: argparse.Namespace) -> None:
    image = _load_image(args.image)
    height, width = image.shape[:2]
    grid = _draw_grid(image, args.step)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), grid):
        raise RuntimeError(f"Failed to write grid image: {output_path}")

    result = {
        "image_size": [width, height],
        "step": args.step,
        "output_image": str(output_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crop around a rough box and map refined boxes back to original image coordinates.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crop_parser = subparsers.add_parser("crop", help="Create a crop around a rough bbox")
    crop_parser.add_argument("--image", required=True, help="Path to the source screenshot")
    crop_parser.add_argument("--output", required=True, help="Path to the cropped output image")
    crop_parser.add_argument(
        "--bbox",
        nargs=4,
        type=int,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Bounding box in pixels unless --normalized is set",
    )
    crop_parser.add_argument(
        "--normalized",
        action="store_true",
        help="Interpret --bbox as 0..999 coordinates",
    )
    crop_parser.add_argument(
        "--padding",
        type=float,
        default=0.35,
        help="Extra padding ratio around the source bbox on each side",
    )
    crop_parser.add_argument(
        "--min-size",
        type=int,
        default=200,
        help="Minimum crop size in pixels for each axis",
    )
    crop_parser.set_defaults(func=crop_command)

    map_parser = subparsers.add_parser("map", help="Map a refined bbox from crop-space back to original image space")
    map_parser.add_argument(
        "--crop-box",
        nargs=4,
        required=True,
        type=int,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Crop bbox in original image pixels",
    )
    map_parser.add_argument(
        "--bbox",
        nargs=4,
        required=True,
        type=int,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Refined bbox inside the crop, in pixels unless --normalized is set",
    )
    map_parser.add_argument(
        "--normalized",
        action="store_true",
        help="Interpret --bbox as 0..999 coordinates inside the crop",
    )
    map_parser.add_argument(
        "--image-size",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        help="Optional original image size to also emit 0..999 mapped coordinates",
    )
    map_parser.set_defaults(func=map_command)

    grid_parser = subparsers.add_parser("grid", help="Overlay a normalized coordinate grid onto an image")
    grid_parser.add_argument("--image", required=True, help="Path to the source screenshot")
    grid_parser.add_argument("--output", required=True, help="Path to the gridded output image")
    grid_parser.add_argument(
        "--step",
        type=int,
        default=100,
        help="Grid step in normalized coordinates",
    )
    grid_parser.set_defaults(func=grid_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
