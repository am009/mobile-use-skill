"""
Mobile Use Skills
基于AppAgent封装的Android设备控制技能模块
"""

from .screen import get_screenshot
from .controller import (
    tap,
    text,
    long_press,
    swipe,
    back, home, enter, keyevent,
    get_device_size,
)

__all__ = [
    # 屏幕
    "get_screenshot",
    # 控制
    "tap",
    "text",
    "long_press",
    "swipe",
    "back", "home", "enter", "keyevent",
    "get_device_size",
]
