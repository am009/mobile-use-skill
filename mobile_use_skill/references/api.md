# Mobile Use API Reference

Complete API documentation for the mobile_use module.

## Screen Capture

### get_screenshot()

Capture device screenshot with optional UI element annotation.

```python
get_screenshot(
    save_path: str = None,      # Output path (default: temp directory)
    with_ui: bool = False,      # Annotate with numbered elements
    dark_mode: bool = False,    # Light text on dark background
    min_dist: int = 30          # Minimum pixel distance between elements
) -> str                        # Returns path to saved PNG
```

**Behavior:**
- When `with_ui=False`: Captures plain screenshot
- When `with_ui=True`: Captures screenshot, parses UI hierarchy, draws numbered labels on interactive elements, and generates `{save_path}.json` with coordinates

**JSON Output Format:**
```json
{"1": [540, 200], "2": [540, 400], "3": [270, 600]}
```
Keys are label numbers, values are `[x, y]` center coordinates.

**Element Detection:**
Finds elements with `clickable="true"` or `focusable="true"` in the UI hierarchy. Elements closer than `min_dist` pixels are filtered to prevent label overlap.

---

## Coordinate-Based Actions

### tap()

Tap at screen coordinates.

```python
tap(x: int, y: int) -> str
```

### long_press()

Long press at coordinates.

```python
long_press(x: int, y: int, duration: int = 1000) -> str
```
- `duration`: Press duration in milliseconds

### swipe()

Swipe between two points.

```python
swipe(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    duration: int = 400
) -> str
```
- `duration`: Swipe duration in milliseconds

---

## Navigation Keys

### back()

Press the back button.

```python
back() -> str
```

### home()

Press the home button.

```python
home() -> str
```

### enter()

Press the enter key.

```python
enter() -> str
```

### keyevent()

Send any Android keycode.

```python
keyevent(code: str) -> str
```

**Common Key Codes:**

| Key Code | Action |
|----------|--------|
| `KEYCODE_BACK` | Back button |
| `KEYCODE_HOME` | Home button |
| `KEYCODE_MENU` | Menu/recent apps |
| `KEYCODE_ENTER` | Enter key |
| `KEYCODE_VOLUME_UP` | Volume up |
| `KEYCODE_VOLUME_DOWN` | Volume down |
| `KEYCODE_POWER` | Power button |
| `KEYCODE_CAMERA` | Camera button |
| `KEYCODE_SEARCH` | Search |
| `KEYCODE_DPAD_UP` | D-pad up |
| `KEYCODE_DPAD_DOWN` | D-pad down |
| `KEYCODE_DPAD_LEFT` | D-pad left |
| `KEYCODE_DPAD_RIGHT` | D-pad right |
| `KEYCODE_DPAD_CENTER` | D-pad center/select |
| `KEYCODE_TAB` | Tab key |
| `KEYCODE_SPACE` | Space key |
| `KEYCODE_DEL` | Delete/backspace |
| `KEYCODE_ESCAPE` | Escape key |

---

## Text Input

### text()

Type text into the currently focused input field.

```python
text(input_str: str) -> str
```

**Note:** Spaces are converted to `%s` for ADB compatibility. Single quotes are stripped.

---

## Device Info

### get_device_size()

Get screen dimensions.

```python
get_device_size() -> Tuple[int, int]  # Returns (width, height) in pixels
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANDROID_SERIAL` | Target device serial number | First connected device |

Set explicitly for multiple devices:
```bash
export ANDROID_SERIAL=emulator-5554
```

---

## Requirements

- **ADB**: Installed and in PATH
- **Device**: Android device connected with USB debugging enabled
- **Python packages**: `opencv-python>=4.5.0`, `pyshine>=0.0.6`

Install dependencies:
```bash
pip install opencv-python pyshine
```

---

## Error Handling

All functions raise `RuntimeError` when:
- No Android device is connected
- ADB command fails
- Device serial specified in `ANDROID_SERIAL` is not found

Example:
```python
try:
    tap(100, 200)
except RuntimeError as e:
    print(f"ADB error: {e}")
```
