# Precision Tap Workflow

Use this workflow only when the default `with_ui=True` path is not enough, for example:

- the target was not detected in the annotated screenshot
- the label appears to be attached to the wrong region
- a click using the JSON center coordinates did not produce the expected UI change
- the tap target is so small or dense that a first-pass click is risky

## Rules

- Prefer `with_ui=True` first. Its JSON center coordinates are the default path for normal interactions.
- Fall back to raw screenshot localization only when `with_ui` is incomplete, clearly wrong, or the click result is wrong.
- Prefer using a short-lived sub-agent for precision localization so the main agent does not accumulate crop-by-crop visual context.
- Do not trust a first-pass guessed point for small icons, inline buttons, list-row affordances, or dense toolbars.
- Use bounding boxes, not prose-only coordinates.
- Keep a fixed normalized coordinate contract when reasoning about crops: `[x_min, y_min, x_max, y_max]` in `0..999`.
- Always verify after tapping by taking a fresh screenshot and checking that the UI state changed.

## Recommended Loop

1. Capture a plain screenshot.
2. Try the normal `with_ui=True` path first.
3. Only continue if the target is missing, mislabeled, or a previous click did not work.
4. Prefer spawning a focused sub-agent for the localization loop.
5. If the raw screen is dense, generate a coordinate grid image first.
6. Estimate a rough target bbox in full-image `0..999` coordinates.
7. Crop around that rough box with padding.
8. Reinspect the crop and produce a refined bbox inside the crop.
9. Map the refined bbox back to original pixels.
10. Tap the mapped center.
11. Re-capture and verify that the screen changed as expected.

Repeat the crop/refine cycle if the target is still too small.

## Suggested Sub-agent Output

Ask the sub-agent to return JSON only:

```json
{
  "bbox": [430, 410, 602, 575],
  "center": [516, 492],
  "need_more_cropping": false,
  "reason": "Target icon is centered in the crop and separated from adjacent controls."
}
```

- `bbox`: use crop `0..999` coordinates unless you explicitly ask for pixels
- `center`: click point in the same coordinate space as `bbox`
- `need_more_cropping`: `true` when the crop is still too coarse to click safely
- `reason`: one short sentence only

## Grid Helper

Overlay a normalized grid on the raw screenshot:

```bash
python mobile_use_skill/scripts/box_tool.py grid \
  --image /tmp/raw.png \
  --output /tmp/raw-grid.png \
  --step 100
```

This is useful when `with_ui` misses the target or a direct click failed and Codex needs a stable first-pass coordinate frame.

## Crop Helper

Create a crop from a rough normalized bbox:

```bash
python mobile_use_skill/scripts/box_tool.py crop \
  --image /tmp/screen.png \
  --bbox 380 640 620 700 \
  --normalized \
  --output /tmp/rough-crop.png
```

The script prints JSON with:

- `crop_bbox`: the crop region in original image pixels
- `target_bbox_in_crop`: the original rough target inside the crop
- `target_bbox_in_crop_999`: the same box normalized inside the crop

## Map Refined Crop Box Back

If a second-pass inspection says the real target inside the crop is `[430, 410, 602, 575]` in crop `0..999` space:

```bash
python mobile_use_skill/scripts/box_tool.py map \
  --crop-box 320 1460 760 1900 \
  --bbox 430 410 602 575 \
  --normalized \
  --image-size 1080 2400
```

The script prints:

- `mapped_bbox`: refined bbox in original pixels
- `mapped_center`: click point in original pixels
- `mapped_bbox_999`: refined bbox normalized against the full screenshot

## Python Example

```python
import json
import subprocess
from mobile_use import get_screenshot, tap

get_screenshot("/tmp/screen.png", with_ui=True, min_dist=15)

crop_info = json.loads(subprocess.check_output([
    "python", "mobile_use_skill/scripts/box_tool.py", "crop",
    "--image", "/tmp/screen.png",
    "--bbox", "388", "641", "610", "690",
    "--normalized",
    "--output", "/tmp/label-7-crop.png",
], text=True))

# After inspecting /tmp/label-7-crop.png, suppose the refined bbox in crop 0..999
# coordinates is [430, 410, 602, 575].
map_info = json.loads(subprocess.check_output([
    "python", "mobile_use_skill/scripts/box_tool.py", "map",
    "--crop-box", *map(str, crop_info["crop_bbox"]),
    "--bbox", "430", "410", "602", "575",
    "--normalized",
    "--image-size", "1080", "2400",
], text=True))

x, y = map_info["mapped_center"]
tap(x, y)
```
