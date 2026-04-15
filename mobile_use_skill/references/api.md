# Mobile Use API Reference

Complete API documentation for the mobile_use module.

## Screen Capture

### get_screenshot()

Capture a device screenshot.

```python
get_screenshot(save_path: str = None) -> str
```

This is the usual first step before calling `interact_with_screen(...)`.

---

## Language-Grounded Interaction

### interact_with_screen()

Interpret a screenshot plus a natural-language instruction, then immediately execute the grounded action on the device.

```python
interact_with_screen(
    image: str,
    instruction: str,
    *,
    config: GroundingConfig | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_rounds: int | None = None,
    out: str | None = None,
    workdir: str | None = None,
    timeout_sec: int | None = None,
) -> dict
```

**Typical usage:**

```python
from mobile_use import get_screenshot, interact_with_screen

get_screenshot("/tmp/screen.png")
result = interact_with_screen(
    "/tmp/screen.png",
    "点击微信",
    reasoning_effort="low",
    max_rounds=1,
)
```

**Return shape:**
- Includes the normal grounding result.
- Adds an `execution` field describing whether the controller call was performed.
- On success, `action` contains the grounded action and `execution.controller_result` contains the controller return value.

**Notes:**
- This is the recommended way to click, long-press, or swipe based on a screenshot.
- Low-level coordinate actions are intentionally not the main public workflow here.

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

Grounding or controller execution may raise `RuntimeError` when:
- No Android device is connected
- ADB command fails
- Device serial specified in `ANDROID_SERIAL` is not found

Example:
```python
try:
    result = interact_with_screen("/tmp/screen.png", "点击微信")
except RuntimeError as e:
    print(f"ADB error: {e}")
```
