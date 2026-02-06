"""
Android设备控制模块
封装ADB命令为简洁的skill函数
"""

import os
import subprocess
from typing import Tuple


def _get_device() -> str:
    """获取设备序列号，优先使用环境变量ANDROID_SERIAL"""
    return os.environ.get("ANDROID_SERIAL", None)

def _adb(command: list, is_binary: bool = False):
    """执行ADB命令

    Args:
        command: ADB命令
        is_binary: 若为True，返回二进制数据(bytes)；否则返回文本(str)

    Returns:
        is_binary=True时返回bytes，否则返回str
    """
    device = _get_device()
    if device:
        full_cmd = ['adb', '-s', device] + command
    else:
        full_cmd = ['adb'] + command
    full_cmd_s = ' '.join(full_cmd)

    if is_binary:
        result = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(f"ADB命令失败: {full_cmd_s}\n{result.stderr.decode()}")
    else:
        result = subprocess.run(
            full_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"ADB命令失败: {full_cmd_s}\n{result.stderr}")


def get_device_size() -> Tuple[int, int]:
    """获取设备屏幕尺寸"""
    result = _adb(["shell", "wm", "size"])
    # 输出格式: "Physical size: 1080x2400"
    size_str = result.split(": ")[1]
    w, h = map(int, size_str.split("x"))
    return w, h


def tap(x: int, y: int) -> str:
    """点击屏幕坐标"""
    return _adb(["shell", "input", "tap", str(x), str(y)])

def init_device():
    result = _adb(["shell", "md5sum", "/data/local/tmp/yadb"])
    if "29a0cd3b3adea92350dd5a25594593df" not in result:
        # to push yadb into the device
        print(f"YADB is not installed on the device. Installing now...")
        _adb(["push", os.path.expanduser("~/Mobile-UI-Skill/yadb"), "/data/local/tmp"])
    else:
        print("yadb is already installed on the device.")

def text(input_str: str) -> str:
    """输入文本"""
    init_device()
    return _adb(["shell", "app_process", "-Djava.class.path=/data/local/tmp/yadb", "/data/local/tmp", "com.ysbing.yadb.Main", "-keyboard", input_str])


def long_press(x: int, y: int, duration: int = 1000) -> str:
    """长按屏幕坐标"""
    return _adb(["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration)])


def swipe(start_x: int, start_y: int, end_x: int, end_y: int, duration: int = 400) -> str:
    """
    滑动操作

    参数:
        start_x, start_y: 起点坐标
        end_x, end_y: 终点坐标
        duration: 滑动持续时间(毫秒)
    """
    return _adb(["shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y), str(duration)])


def back() -> str:
    """按返回键"""
    return _adb(["shell", "input", "keyevent", "KEYCODE_BACK"])


def home() -> str:
    """按Home键"""
    return _adb(["shell", "input", "keyevent", "KEYCODE_HOME"])


def enter() -> str:
    """按回车键"""
    return _adb(["shell", "input", "keyevent", "KEYCODE_ENTER"])


def keyevent(code: str) -> str:
    """发送按键事件"""
    return _adb(["shell", "input", "keyevent", str(code)])
