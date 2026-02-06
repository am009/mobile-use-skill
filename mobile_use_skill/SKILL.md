---
name: mobile-use
description: This skill should be used when the user asks to "control my phone", "tap on the screen", "take a screenshot of my phone", "automate Android", "interact with mobile app", "click element on phone", "type text on phone", "swipe on screen", "navigate back on phone", or needs to capture, annotate, or interact with an Android device via ADB.
---

# Mobile Use

Control Android devices via ADB with automatic UI element detection and coordinate-based interaction.

## Core Workflow

To automate interaction with an Android device:

1. **Capture screenshot with UI annotations** to see numbered interactive elements
2. **Read the JSON coordinates file** to get element positions
3. **Tap elements by coordinates** using the label numbers from the screenshot
4. **Repeat** for multi-step interactions

```python
import json
from mobile_use import get_screenshot, tap, text, back

# Step 1: Capture with UI annotations
get_screenshot("/tmp/screen.png", with_ui=True)
# Creates: /tmp/screen.png (annotated image) + /tmp/screen.png.json (coordinates)

# Step 2: Load coordinates
with open("/tmp/screen.png.json") as f:
    elements = json.load(f)  # {"1": [x, y], "2": [x, y], ...}

# Step 3: Tap element by number
x, y = elements["3"]
tap(x, y)

# Step 4: Continue interaction
text("search query")
back()
```

## Key Functions

### Screenshot and UI Detection

```python
get_screenshot(save_path, with_ui=True, dark_mode=False, min_dist=30)
```

- `with_ui=True`: Annotate screenshot with numbered labels and generate JSON coordinate file
- `dark_mode=True`: Use light text on dark background for visibility on light apps
- `min_dist`: Minimum pixel distance between elements (prevents label overlap)

### Device Control

| Function | Purpose |
|----------|---------|
| `tap(x, y)` | Tap at coordinates |
| `text(input_str)` | Type text into focused field |
| `swipe(x1, y1, x2, y2, duration=400)` | Swipe gesture |
| `long_press(x, y, duration=1000)` | Long press |
| `back()`, `home()`, `enter()` | Navigation keys |
| `keyevent(code)` | Send any Android keycode |
| `get_device_size()` | Get screen dimensions |

## JSON Coordinate Format

When `with_ui=True`, a JSON file is created alongside the screenshot:

```json
{"1": [540, 200], "2": [540, 400], "3": [270, 600]}
```

- Keys: Label numbers shown on the annotated screenshot
- Values: `[x, y]` center coordinates for tapping

## Practical Examples

### Open an app and search

```python
import json
from mobile_use import get_screenshot, tap, text, enter

# Capture home screen
get_screenshot("/tmp/home.png", with_ui=True)
with open("/tmp/home.png.json") as f:
    elements = json.load(f)

# Tap app icon (element 5)
x, y = elements["5"]
tap(x, y)

# Wait for app, capture new screen
import time; time.sleep(2)
get_screenshot("/tmp/app.png", with_ui=True)
with open("/tmp/app.png.json") as f:
    elements = json.load(f)

# Tap search field and type
x, y = elements["1"]
tap(x, y)
text("hello world")
enter()
```

### Scroll through content

```python
from mobile_use import get_screenshot, swipe, get_device_size

w, h = get_device_size()

# Swipe up to scroll down
swipe(w // 2, h * 3 // 4, w // 2, h // 4, duration=400)

# Capture after scroll
get_screenshot("/tmp/scrolled.png", with_ui=True)
```

### Handle dense UI

For screens with many close elements:

```python
# Reduce minimum distance to capture more elements
get_screenshot("/tmp/dense.png", with_ui=True, min_dist=15)
```

## Element Detection

`get_screenshot(with_ui=True)` identifies interactive elements from the UI hierarchy:

- Elements with `clickable="true"`
- Elements with `focusable="true"`

Elements too close together are filtered based on `min_dist` to prevent overlapping labels.

## Setup

**Requirements:**
- ADB installed and in PATH
- Android device with USB debugging enabled

**Python Package:**

`mobile_use` 已作为独立 Python 包全局安装（editable mode），源码位于：
```
/home/wjk/Mobile-UI-Skill/mobile_use/
```

无需额外安装依赖，直接 `import mobile_use` 即可使用。

如需重新安装：
```bash
pip install -e /home/wjk/Mobile-UI-Skill/mobile_use
```

## Additional Resources

### Reference Files

For complete API documentation including all parameters, return types, and key codes:

- **`references/api.md`** - Full API reference with all functions and Android key codes
