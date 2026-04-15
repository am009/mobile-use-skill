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

## API

Common functions:

- `get_screenshot(save_path=None)`
- `interact_with_screen(image, instruction, ...)`
- `text(input_str)`
- `back()`, `home()`, `enter()`, `keyevent(code)`
- `get_device_size()`

Package source:

`/home/wjk/Mobile-UI-Skill/mobile_use_src/`

## References

- `references/api.md` for the full API
