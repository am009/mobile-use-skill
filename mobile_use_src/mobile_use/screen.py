"""
屏幕截图和UI标记模块
获取截图、解析UI树、在图片上标记数字索引
"""

import io
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2

import numpy as np

from .controller import _adb


# 默认最小元素间距，防止标记重叠
MIN_DIST = 30


@dataclass
class _RawElement:
    """原始UI元素"""
    uid: str
    bbox: Tuple[Tuple[int, int], Tuple[int, int]]
    attrib: str


def _get_id_from_element(elem) -> str:
    """从XML元素生成唯一标识"""
    bounds = elem.attrib["bounds"][1:-1].split("][")
    x1, y1 = map(int, bounds[0].split(","))
    x2, y2 = map(int, bounds[1].split(","))
    elem_w, elem_h = x2 - x1, y2 - y1
    if "resource-id" in elem.attrib and elem.attrib["resource-id"]:
        elem_id = elem.attrib["resource-id"].replace(":", ".").replace("/", "_")
    else:
        elem_id = f"{elem.attrib['class']}_{elem_w}_{elem_h}"
    if "content-desc" in elem.attrib and elem.attrib["content-desc"] and len(elem.attrib["content-desc"]) < 20:
        content_desc = elem.attrib["content-desc"].replace("/", "_").replace(" ", "").replace(":", "_")
        elem_id += f"_{content_desc}"
    return elem_id


def _traverse_tree(xml_data: bytes, attrib: str, elem_list: List[_RawElement], min_dist: int = MIN_DIST):
    """遍历UI树，提取具有指定属性的元素

    Args:
        xml_data: UI树XML的二进制数据
        attrib: 要匹配的属性名
        elem_list: 用于存储提取元素的列表
        min_dist: 元素最小间距
    """
    path = []
    for event, elem in ET.iterparse(io.BytesIO(xml_data), ["start", "end"]):
        if event == "start":
            path.append(elem)
            if attrib in elem.attrib and elem.attrib[attrib] == "true":
                parent_prefix = ""
                if len(path) > 1:
                    parent_prefix = _get_id_from_element(path[-2])
                bounds = elem.attrib["bounds"][1:-1].split("][")
                x1, y1 = map(int, bounds[0].split(","))
                x2, y2 = map(int, bounds[1].split(","))
                center = ((x1 + x2) // 2, (y1 + y2) // 2)
                elem_id = _get_id_from_element(elem)
                if parent_prefix:
                    elem_id = parent_prefix + "_" + elem_id

                # 检查是否与已有元素太近
                too_close = False
                for e in elem_list:
                    cx = (e.bbox[0][0] + e.bbox[1][0]) // 2
                    cy = (e.bbox[0][1] + e.bbox[1][1]) // 2
                    dist = ((center[0] - cx) ** 2 + (center[1] - cy) ** 2) ** 0.5
                    if dist <= min_dist:
                        too_close = True
                        break
                if not too_close:
                    elem_list.append(_RawElement(uid=elem_id, bbox=((x1, y1), (x2, y2)), attrib=attrib))
        if event == "end":
            path.pop()


def _draw_labels(img_data: bytes, elem_list: List[_RawElement], dark_mode: bool = False) -> bytes:
    """在图片上绘制数字标签

    Args:
        img_data: 图片二进制数据
        elem_list: 元素列表
        dark_mode: 深色模式

    Returns:
        处理后的图片二进制数据(PNG格式)
    """
    img_array = np.frombuffer(img_data, dtype=np.uint8)
    imgcv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    for i, elem in enumerate(elem_list):
        try:
            x1, y1 = elem.bbox[0]
            x2, y2 = elem.bbox[1]
            label = str(i + 1)
            text_color = (10, 10, 10) if dark_mode else (255, 250, 250)
            bg_color = (255, 250, 250) if dark_mode else (10, 10, 10)
            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 1
            thickness = 2
            tx = (x1 + x2) // 2 + 10
            ty = (y1 + y2) // 2 + 10
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            pad = 10
            overlay = imgcv.copy()
            cv2.rectangle(overlay, (tx - pad, ty - th - pad), (tx + tw + pad, ty + pad + baseline), bg_color[::-1], -1)
            cv2.addWeighted(overlay, 0.6, imgcv, 0.4, 0, imgcv)
            cv2.putText(imgcv, label, (tx, ty), font, font_scale, text_color[::-1], thickness, cv2.LINE_AA)
        except Exception as e:
            print(f"标注元素 {i + 1} 时出错: {e}")
    _, encoded = cv2.imencode('.png', imgcv)
    return encoded.tobytes()


def _save_elements_json(json_path: str, elem_list: List[_RawElement]) -> Dict:
    """保存元素坐标到JSON文件，格式: {"1": [x, y], "2": [x, y], ...}"""
    elements = {}
    for i, elem in enumerate(elem_list):
        x1, y1 = elem.bbox[0]
        x2, y2 = elem.bbox[1]
        elements[str(i + 1)] = [(x1 + x2) // 2, (y1 + y2) // 2]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(elements, f, ensure_ascii=False)
    return elements


def get_screenshot(
    save_path: Optional[str] = None,
    with_ui: bool = False,
    dark_mode: bool = False,
    min_dist: int = MIN_DIST,
) -> str:
    """
    获取设备屏幕截图

    参数:
        save_path: 截图保存路径，默认使用临时目录
        with_ui: 是否标记UI元素。如果为True，会在图片上标记数字，
                 并生成同名的.json文件记录每个数字对应的坐标
        dark_mode: UI标记的颜色模式（仅with_ui=True时有效）
        min_dist: UI元素最小间距（仅with_ui=True时有效）

    返回:
        截图保存路径
        如果with_ui=True，还会生成 {save_path}.json 文件
    """
    if save_path is None:
        save_path = os.path.join(tempfile.gettempdir(), "mobile_screenshot.png")

    save_dir = os.path.dirname(save_path) or "."
    os.makedirs(save_dir, exist_ok=True)

    # 截图
    img_data = _adb(["exec-out", "screencap", "-p"], is_binary=True)

    if not with_ui:
        with open(save_path, "wb") as f:
            f.write(img_data)
        return save_path

    # 获取UI树XML
    xml_data = _adb(["exec-out", "sh", "-c", "uiautomator dump /dev/tty 2>/dev/null >/dev/null"], is_binary=True)

    # 提取元素
    elem_list: List[_RawElement] = []
    _traverse_tree(xml_data, "clickable", elem_list, min_dist)
    _traverse_tree(xml_data, "focusable", elem_list, min_dist)

    # 标注图片
    labeled_img_data = _draw_labels(img_data, elem_list, dark_mode)

    # 保存标注后的图片
    with open(save_path, "wb") as f:
        f.write(labeled_img_data)

    # 保存元素坐标到JSON
    json_path = save_path + ".json"
    _save_elements_json(json_path, elem_list)

    return save_path
