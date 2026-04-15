# Mobile-UI-Skill

一个面向 Android 的 mobile use agent 项目。基于adb，让claude，codex等LLM直接操作手机。

## 使用方法

先安装 `mobile_use_src` 里的 Python 包：

```bash
cd ~/Mobile-UI-Skill/mobile_use_src
pip install -e .
```

然后把 `mobile_use_skill` 安装成一个 Codex skill。推荐做法是在 skills 目录里创建一个名为 `mobile_use` 的软链接：

```bash
ln -s ~/Mobile-UI-Skill/mobile_use_skill ~/.codex/skills/mobile_use
```

如果目标链接已经存在，可以先删除旧链接再重新创建：

```bash
rm -f ~/.codex/skills/mobile_use
ln -s ~/Mobile-UI-Skill/mobile_use_skill ~/.codex/skills/mobile_use
```

安装完成后，Codex 在需要控制 Android 手机、截图、点击、滑动、输入文本时，就可以触发这个 skill。

## 精确点击

**准确点击屏幕**：它接收一张手机截图和一条自然语言指令，例如“点击登录按钮”或“从列表底部向上拖动”，然后通过 `codex exec` 启动小模型 agent，把这条指令收敛成一个可执行的移动端操作。当前默认模型是 `gpt-5.4-mini`，也可以按需切换。

这里有一个很关键、也是桌面环境里不明显的问题：mobile 设备没有鼠标。桌面上点偏了，我们通常还能从 hover、焦点、指针位置、窗口反馈里判断发生了什么；但手机不是这样。一次点击不准确之后，大模型往往很难知道到底是：

- 这个点没有反应
- 实际点错了别的控件
- 点击触发了别的页面变化
- 当前界面需要的是拖动、长按或其他动作

所以移动端 grounding 的关键不只是“给一个坐标”，而是要尽量判断这个坐标在视觉上是否真的合理，并在失败时给出可修复的反馈。

- 不是单次猜坐标，而是双 agent 闭环。`operator agent` 先提出操作方案，`evaluator agent` 再独立审核是否真的对准了目标。
- 不是只看文本描述，而是先把操作画回截图再评估。点击会渲染半透明反色十字，长按会额外画出强调环，拖动会渲染起点、终点和箭头。
- 反色 overlay 的设计让标记在浅色和深色背景上都清晰可见，比单纯画红框更稳，也更适合让模型二次判断。
- 两个 agent 各自保留自己的历史上下文，但只看到对方的结构化输出，不共享完整上下文，能减少相互带偏。
- 评估失败时不会只说“不对”，而是输出具体问题和修复建议，再反馈给 `operator agent` 继续迭代。
- 最终结果不是抽象描述，而是可以直接落地执行的 Python 操作，例如 `tap(...)`、`long_press(...)`、`swipe(...)`。
- 每一轮都会保存运行产物，包括原始响应、规范化 JSON、overlay 图片、trace 和最终结果，方便调试和复盘。

## 它解决什么问题

移动端 UI grounding 最大的难点，不是“让模型看懂截图”，而是“让模型稳定地把动作落到正确位置”。单次输出坐标很容易出现这些问题：

- 点位偏了一点，但文本理由听起来仍然合理
- 模型自信很高，但实际上点在了目标旁边
- 拖动方向大致正确，但起点和终点并不适合真实操作
- 出错后没有明确的修复路径，只能重新猜一次

这个项目把问题拆成“提案、可视化、评估、修正”的闭环，让便宜的小模型也能逐步收敛，而不是一次性赌博。

## 工作流程

1. 输入一张手机截图和一条自然语言操作指令。
2. 启动 `operator agent`，让模型先输出一个初步操作。
3. 操作会先被规范化为结构化 JSON。坐标统一使用 `0-999` 的归一化空间，而不是直接输出像素坐标。
4. 根据这个操作生成可视化 overlay。
5. 启动 `evaluator agent`，让它只基于截图、overlay 和 operator 的结构化输出来判断动作是否正确。
6. 如果 evaluator 拒绝，它必须给出具体问题和 `repair_hint`，再把这些反馈给 operator 继续迭代。
7. 迭代直到 evaluator 接受，或者达到上限。当前默认上限是 6 轮。
8. 一旦接受，就返回最终操作；在 `interact_with_screen(...)` 这条高层 API 中，还会直接调用控制层执行该操作。

## 支持的动作

- `tap`
- `long_press`
- `swipe`

其中：

- `tap` 和 `long_press` 使用单点坐标
- `swipe` 使用起点和终点坐标
- `long_press` 和 `swipe` 的 `duration_ms` 在运行时固定为 `1000ms`，不让模型额外承担这部分输出负担

## 为什么要先渲染 overlay 再评估

如果只把坐标数字发给评估模型，模型很难真正判断“这个点是不是落在正确的 UI 元素上”。而把动作画回截图之后，评估模型看到的是一个接近人类视觉检查的结果：

- 点击是否真的落在按钮中心
- 长按是否压在目标本体上
- 拖动箭头的方向和路径是否合理
- 标记是否离危险控件太近

这个步骤把“坐标对不对”转换成了“视觉上像不像真的会这么操作”，大幅提升了可审查性。

## 上下文隔离设计

`operator agent` 和 `evaluator agent` 在多轮迭代中各自保留自己的历史，但不会直接共享彼此的完整上下文。它们之间只传递结构化输出。

这样设计的好处是：

- operator 更专注于提出动作，而不是迎合 evaluator 的措辞
- evaluator 更像独立审稿人，而不是顺着 operator 的思路走
- 失败反馈更结构化，更适合下一轮修正

## 运行产物

默认情况下，运行产物会写到：

```text
runs/grounding/<timestamp>-<short_id>/
```

目录里通常会包含：

- `input.png`
- `input.meta.json`
- `operator.raw.turn_N.txt`
- `operator.turn_N.json`
- `evaluator.raw.turn_N.txt`
- `evaluator.turn_N.json`
- `overlay.turn_N.png`
- `overlay.turn_N.json`
- `trace.jsonl`
- `final.json`

这些文件很适合用来排查“为什么没点准”或者“为什么 evaluator 反复 reject”。

## Python 用法

```python
from mobile_use import get_screenshot, interact_with_screen

get_screenshot("/tmp/screen.png")
result = interact_with_screen(
    "/tmp/screen.png",
    "点击底部中间的登录按钮",
    reasoning_effort="low",
    max_rounds=3,
    out="/tmp/mobile-runs/demo",
    workdir="~/Mobile-UI-Skill",
)

print(result)
```

## CLI 用法

```bash
PYTHONPATH=~/Mobile-UI-Skill/mobile_use_src \
python -m mobile_use.grounding \
  --image /tmp/screen.png \
  --instruction "点击底部中间的登录按钮" \
  --reasoning-effort low \
  --max-rounds 6 \
  --workdir ~/Mobile-UI-Skill
```

## 返回结果

典型返回结果包含这些信息：

- `status`: `accepted` 或 `unresolved`
- `rounds_used`: 实际使用了多少轮
- `action`: 最终接受的动作
- `overlay_path`: 最后一轮 overlay 图片路径
- `visual_description`: 对该动作的形象化描述
- `evaluator_summary`: 最后一轮评估摘要
- `run_dir`: 这次运行的产物目录

如果通过 `interact_with_screen(...)` 调用，还会额外包含：

- `execution.performed`: 是否真的调用了控制层
- `execution.controller_result`: ADB 控制层返回结果

## 仓库结构

- `mobile_use_src/`: Python 包和 grounding 实现
- `mobile_use_src/mobile_use/grounding/`: operator/evaluator/orchestrator/overlay/run-store 等核心逻辑
- `mobile_use_skill/`: 给 Codex 使用的 skill 文档
- `runs/`: grounding 运行产物目录

## 适用场景

- 根据截图点击某个按钮、图标或菜单项
- 根据截图执行拖动、滑动、长按
- 在没有稳定原生 UI tree 的游戏界面里做视觉 grounding
- 对移动端 agent 的决策过程做可解释、可复盘的调试

## 当前设计取舍

- 优先保证动作可解释、可审查，而不是单轮最快返回
- 优先使用结构化 JSON 和 overlay，可牺牲一点延迟
- 优先让 evaluator 严格拒绝“差不多对”的提案，避免误触
- 优先把动作表达成少数几类基础操作，保持控制层简单稳定
