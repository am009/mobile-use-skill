---
name: mobile-use
description: This skill should be used when the user asks to control an Android phone, tap the screen, take a phone screenshot, automate Android via ADB, type into a mobile app, swipe on screen, navigate back/home, or interact with UI elements on a connected device.
---

# Mobile Use

Control Android devices through ADB with screenshot-based interaction.

## Default Path

Capture a screenshot, then let the grounding workflow interpret the image and execute the action directly.

Write the operation description as clearly and specifically as possible so the model can distinguish the target from nearby controls and avoid accidental taps on the wrong UI element.

```python
from mobile_use import get_screenshot, interact_with_screen

get_screenshot("/tmp/screen.png")
result = interact_with_screen("/tmp/screen.png", "点击微信")
```

This is the recommended way to click, long-press, or swipe based on a screenshot. Prefer natural-language targets over hard-coded coordinates.

Typical tuned call:

```python
from mobile_use import get_screenshot, interact_with_screen

get_screenshot("/tmp/screen.png")
result = interact_with_screen(
    "/tmp/screen.png",
    "点击底部中间的登录按钮",
    reasoning_effort="low",
    max_rounds=3,
)
```

`result` includes the grounding decision and an `execution` field. When the action is accepted, `execution.performed` is `True` and `execution.controller_result` contains the ADB-layer result.

## API

### `get_screenshot()`

Capture a device screenshot.

```python
get_screenshot(save_path: str = None) -> str
```

This is usually the first step before calling `interact_with_screen(...)`.

### `interact_with_screen()`

Interpret a screenshot plus a natural-language instruction, then execute the grounded action on the device.

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

Notes:

- Recommended default for screenshot-based interaction.
- Use clear target descriptions such as `点击底部中间的“继续”按钮`.
- Low-level coordinate actions are intentionally not the main public workflow here.

### Navigation Keys

#### `back()`

Press the back button.

```python
back() -> str
```

#### `home()`

Press the Home key.

```python
home() -> str
```

#### `enter()`

Press the Enter key.

```python
enter() -> str
```

#### `keyevent()`

Send any Android keycode.

```python
keyevent(code: str) -> str
```

Common key codes:

- `KEYCODE_BACK`
- `KEYCODE_HOME`
- `KEYCODE_MENU`
- `KEYCODE_ENTER`
- `KEYCODE_VOLUME_UP`
- `KEYCODE_VOLUME_DOWN`
- `KEYCODE_POWER`
- `KEYCODE_CAMERA`
- `KEYCODE_SEARCH`
- `KEYCODE_DPAD_UP`
- `KEYCODE_DPAD_DOWN`
- `KEYCODE_DPAD_LEFT`
- `KEYCODE_DPAD_RIGHT`
- `KEYCODE_DPAD_CENTER`
- `KEYCODE_TAB`
- `KEYCODE_SPACE`
- `KEYCODE_DEL`
- `KEYCODE_ESCAPE`

### `text()`

Type text into the currently focused input field.

```python
text(input_str: str) -> str
```

### `get_device_size()`

Get screen dimensions.

```python
get_device_size() -> Tuple[int, int]
```

Returns `(width, height)` in pixels.

## Environment

- `ANDROID_SERIAL`: target device serial number. Defaults to the first connected device.

Example:

```bash
export ANDROID_SERIAL=emulator-5554
```

Requirements:

- `adb` installed and available in `PATH`
- An Android device connected with USB debugging enabled
- Python dependencies: `opencv-python>=4.5.0`, `pyshine>=0.0.6`

Install dependencies:

```bash
pip install opencv-python pyshine
```

## Errors

Grounding or controller execution may raise `RuntimeError` when:

- No Android device is connected
- An ADB command fails
- The device serial in `ANDROID_SERIAL` is not found

Example:

```python
try:
    result = interact_with_screen("/tmp/screen.png", "点击微信")
except RuntimeError as e:
    print(f"ADB error: {e}")
```
