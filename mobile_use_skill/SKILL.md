---
name: mobile-use
description: This skill should be used when the user asks to control an Android phone, tap the screen, take a phone screenshot, automate Android via ADB, type into a mobile app, swipe on screen, navigate back/home, or interact with UI elements on a connected device.
---

# Mobile Use

Control Android devices through ADB with screenshot-based interaction.

## Default Path

Use `get_screenshot(..., with_ui=True)` before most actions. The generated `{image}.json` label-to-center map is usually reliable and should be the first choice for taps.

```python
import json
from mobile_use import get_screenshot, tap

get_screenshot("/tmp/screen.png", with_ui=True, min_dist=15)
with open("/tmp/screen.png.json") as f:
    elements = json.load(f)

x, y = elements["3"]
tap(x, y)
```

## When To Use Precision Tap

Use the precision workflow only when:

- the target is missing from the annotated screenshot
- the label appears attached to the wrong UI region
- a tap from `{image}.json` did not produce the expected UI change
- the target is too small or dense for a safe first-pass click

## Precision Tap

1. Capture a plain screenshot with `get_screenshot("/tmp/raw.png")`.
2. Prefer delegating localization to a short-lived sub-agent.
3. If needed, add a normalized grid:

```bash
python mobile_use_skill/scripts/box_tool.py grid \
  --image /tmp/raw.png \
  --output /tmp/raw-grid.png
```

4. Estimate a rough bbox in `[x_min, y_min, x_max, y_max]` format using `0..999` coordinates.
5. Create a crop:

```bash
python mobile_use_skill/scripts/box_tool.py crop \
  --image /tmp/raw.png \
  --bbox 380 640 620 700 \
  --normalized \
  --output /tmp/raw-crop.png
```

6. Refine the target inside the crop.
7. Map the refined crop bbox back to original pixels:

```bash
python mobile_use_skill/scripts/box_tool.py map \
  --crop-box 320 1460 760 1900 \
  --bbox 430 410 602 575 \
  --normalized \
  --image-size 1080 2400
```

8. Tap the mapped center and verify the UI changed. If not, crop tighter and repeat.

## Sub-agent Guidance

For precision localization, give the sub-agent only:

- the target description
- the current screenshot or crop path
- the required output schema

Ask it to return JSON only:

```json
{
  "bbox": [430, 410, 602, 575],
  "center": [516, 492],
  "need_more_cropping": false,
  "reason": "Target is clearly separated from adjacent controls."
}
```

The main agent should perform the actual tap and verification.

## API

Common functions:

- `get_screenshot(save_path, with_ui=False, dark_mode=False, min_dist=30)`
- `tap(x, y)`
- `text(input_str)`
- `swipe(x1, y1, x2, y2, duration=400)`
- `long_press(x, y, duration=1000)`
- `back()`, `home()`, `enter()`, `keyevent(code)`
- `get_device_size()`

Package source:

`/home/wjk/Mobile-UI-Skill/mobile_use_src/`

## References

- `references/api.md` for the full API
- `references/precision.md` for the full precision localization workflow
