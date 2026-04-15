# Mobile Operation Grounding 双 Agent 设计

## 目标

这个脚本负责把一张手机截图和一条操作意图，转换成一个可执行的移动端动作。

输入：

- 一张手机屏幕截图
- 一条自然语言操作意图，例如：
  - `点击右上角的发送按钮`
  - `从底部向上拖动打开控制中心`
  - `长按第二个标签`

输出：

- 一个结构化动作
- 一个对应的 Python 调用语句
- 一张带可视化标记的辅助图
- 一份双 agent 迭代轨迹

本设计默认通过 `codex exec` / `codex exec resume` 在后台启动两个独立的 Codex CLI 会话，默认模型使用 `gpt-5.4-mini`。模型名应保持可配置，不要硬编码。

## 为什么采用双 Agent

单模型直接出坐标的问题是：

- 容易把“看起来像目标”的区域和“真正可点击目标”混淆
- 输出的坐标缺少独立校验
- 一旦首轮判断错，后续没有明确的纠错通道

双 agent 结构的目标是把“提出动作”和“审查动作”拆开：

- `operator agent` 负责提出动作
- `evaluator agent` 负责审查动作是否真的符合截图与意图
- 两者各自保留自己的上下文
- 两者不能读取对方历史，只能看到对方最新一次输出

这样可以让脚本形成一个小型对抗式收敛回路，而不是一次性拍脑袋出结果。

## 总体架构

建议拆成 5 个模块：

1. `orchestrator`
   负责主循环、轮次控制、上下文文件、最终收敛。
2. `codex_cli_adapter`
   负责启动和恢复 Codex CLI 会话，传递图片、schema、prompt，并提取最后一条消息。
3. `renderer`
   负责根据动作坐标生成可视化图，包括点击十字、长按圆环、拖动箭头。
4. `schemas`
   负责定义 operator/evaluator/final output 的 JSON Schema。
5. `run_store`
   负责保存每次 run 的所有工件，便于调试和复现。

建议文件结构：

```text
mobile_use_src/mobile_use/grounding/
  __init__.py
  cli.py
  orchestrator.py
  codex_cli_adapter.py
  renderer.py
  schemas.py
  prompts.py
  types.py
```

建议每次运行建立一个独立目录：

```text
runs/grounding/<timestamp>-<short_id>/
  input.png
  input.meta.json
  operator.schema.json
  evaluator.schema.json
  operator.last.json
  evaluator.last.json
  operator.history.jsonl
  evaluator.history.jsonl
  overlay.turn_1.png
  overlay.turn_2.png
  final.json
```

## 与 Codex CLI 的对接方式

本机 `codex` 已支持以下能力，足够落地这个设计：

- `codex exec`
- `codex exec resume`
- `--image`
- `--output-schema`
- `--output-last-message`
- `--json`

建议封装成一个稳定 adapter，而不是在业务代码里直接拼接命令。

### 启动首轮 operator

思路：

- 用 `codex exec` 启动新的会话
- prompt 里明确设定身份为 `operator agent`
- 用 `--image <screenshot>` 附带截图
- 用 `--output-schema` 约束输出必须为 JSON
- 用 `--output-last-message` 落盘结果
- 用 `--json` 捕获 `thread.started` 事件，拿到 thread id

### 后续轮次恢复 operator

思路：

- 用 `codex exec resume <thread_id>`
- 只把 evaluator 的最新输出作为反馈传给 operator
- 不把 evaluator 的历史 transcript 传进去

### evaluator 的启动与恢复

完全对称：

- evaluator 有独立 thread id
- evaluator 的系统角色与 operator 不同
- evaluator 只能看到：
  - 原始截图
  - 当前 overlay 图
  - 用户指令
  - operator 最新 JSON 输出

## 上下文隔离原则

这是整个设计最关键的约束。

### operator 可以看到

- 原始用户指令
- 当前截图
- 自己前几轮的历史
- evaluator 最新一轮的输出

### operator 不可以看到

- evaluator 的系统 prompt
- evaluator 的历史推理过程
- evaluator 过去多轮完整 transcript

### evaluator 可以看到

- 原始用户指令
- 当前截图
- 当前 overlay 图
- 自己前几轮的历史
- operator 最新一轮的输出

### evaluator 不可以看到

- operator 的历史推理过程
- operator 过去多轮完整 transcript

### 工程实现建议

如果 `codex exec resume` 稳定可用，就直接给 operator 与 evaluator 各维持一个 thread id。

如果未来 CLI 行为变化，无法可靠恢复线程，也可以退化为“脚本自己维护每个 agent 的 transcript 回放”：

- `operator.history.jsonl`
- `evaluator.history.jsonl`

每次调用 CLI 时只回放该 agent 自己的历史，再拼上对方最新输出。

## 动作协议

建议不要让模型输出自由文本动作，而是输出严格的结构化 JSON。

### operator 输出

```json
{
  "action_type": "tap",
  "target_desc": "右上角的发送按钮",
  "screen_size": [1080, 2400],
  "point_px": [1002, 142],
  "point_999": [927, 59],
  "bbox_999": [900, 32, 955, 86],
  "duration_ms": null,
  "confidence": 0.82,
  "reason": "发送图标位于标题栏右上角，和搜索入口、返回键明显分离。",
  "python_call": "tap(1002, 142)"
}
```

对于拖动动作：

```json
{
  "action_type": "swipe",
  "target_desc": "从底部中间向上拖动打开控制中心",
  "screen_size": [1080, 2400],
  "start_px": [540, 2200],
  "end_px": [540, 900],
  "start_999": [500, 916],
  "end_999": [500, 375],
  "duration_ms": 450,
  "confidence": 0.77,
  "reason": "这是一个系统级上滑手势，起点应接近底部边缘，终点在中上区域。",
  "python_call": "swipe(540, 2200, 540, 900, duration=450)"
}
```

### 推荐 action_type 集合

- `tap`
- `long_press`
- `swipe`
- `text`
- `back`
- `home`
- `enter`
- `keyevent`

对于本设计的第一期，建议先重点支持：

- `tap`
- `long_press`
- `swipe`

因为这三类最依赖 grounding。

### evaluator 输出

```json
{
  "verdict": "reject",
  "score": 0.41,
  "reason": "当前点击点更接近搜索图标左侧空白区域，没有落在发送图标主体内。",
  "issues": [
    "point_x 偏左",
    "bbox_999 覆盖到了标题栏空白区域"
  ],
  "repair_hint": "将点击点右移约 20 到 35 像素，并让 bbox 更贴近发送图标本体。",
  "expected_action_type": "tap"
}
```

或者在接受时：

```json
{
  "verdict": "accept",
  "score": 0.91,
  "reason": "点击点位于发送图标中心区域，动作类型与用户意图一致。",
  "issues": [],
  "repair_hint": "",
  "expected_action_type": "tap"
}
```

## 可视化层设计

这里建议采用“模型出结构化动作，脚本做确定性渲染”的方式。

不要让模型自己生成图像描述或自己假设画法。渲染规则应该是固定的，这样 evaluator 看到的视觉证据稳定，调试也容易。

### 点击动作

渲染一个半透明反色十字架：

- 十字中心对准 `point_px`
- 横竖各一条线
- 线条主体采用“半透明反色”
- 推荐计算方式：
  - `new_pixel = 0.35 * old_pixel + 0.65 * (255 - old_pixel)`
- 在十字中心再加一个小圆点
- 圆点外围加 1 到 2 像素的细边，提高在高频背景上的可见性

这样做比纯红点更稳，因为反色在浅色和深色背景上都可见。

### 长按动作

渲染规则：

- 使用同样的反色十字架
- 外加一个半透明圆环
- 可在旁边标注 `long press 1000ms`

### 拖动动作

渲染规则：

- 起点画十字
- 终点画十字
- 两点之间画箭头
- 箭头主体仍使用半透明反色
- 起点可加小实心圆
- 终点可加空心箭头头部

### 文本描述

可视化图之外，再生成一条给人看的短描述，但建议由脚本半确定性生成：

- 先根据坐标生成粗位置描述，例如：
  - `屏幕右上角`
  - `屏幕下半部偏中间`
  - `从屏幕底部中间向上拖动到中部`
- 再拼上 operator 的 `target_desc`

例如：

- `点击屏幕右上角的发送按钮`
- `从屏幕底部中间向上拖动到中部以打开控制中心`

这条描述可以出现在最终返回结构里，也可以绘制在 overlay 图的顶部边缘。

## 迭代状态机

建议最大轮次 `max_rounds = 6`。

主循环如下：

1. operator 产出首轮动作
2. renderer 根据动作生成 overlay 图和视觉描述
3. evaluator 判断动作是否正确
4. 如果 `accept`，结束并返回动作
5. 如果 `reject` 且未超出轮次，把 evaluator 输出反馈给 operator
6. operator 基于自己的历史和 evaluator 最新反馈继续修正
7. 重复直到收敛或达到上限

### 伪代码

```python
def solve(image_path: str, instruction: str, max_rounds: int = 6) -> dict:
    run = create_run(image_path, instruction)

    operator = start_agent(
        name="operator agent",
        role="operator",
        image_path=image_path,
        instruction=instruction,
    )
    evaluator = start_agent(
        name="evaluator agent",
        role="evaluator",
        image_path=image_path,
        instruction=instruction,
    )

    latest_feedback = None

    for turn in range(1, max_rounds + 1):
        op_result = operator.propose(feedback=latest_feedback)
        overlay = render_overlay(image_path, op_result, turn=turn)
        ev_result = evaluator.judge(
            operator_output=op_result,
            overlay_path=overlay.path,
            overlay_desc=overlay.description,
        )

        persist_turn(run, turn, op_result, overlay, ev_result)

        if ev_result["verdict"] == "accept":
            return build_final_success(run, op_result, ev_result, overlay)

        latest_feedback = ev_result

    return build_final_failure(run)
```

## Prompt 设计

### operator system prompt 要点

- 你是 `operator agent`
- 任务是根据截图与指令提出一个具体、可执行、单一的移动端动作
- 只允许输出 JSON
- 坐标必须同时给出像素坐标与 `0..999` 归一化坐标
- 不要输出多候选
- 如果 evaluator 拒绝，必须优先修正 evaluator 指出的具体问题
- 不要解释过长，不要输出 markdown

### evaluator system prompt 要点

- 你是 `evaluator agent`
- 任务是严格审查 operator 的动作是否真的与截图和用户意图一致
- 只允许输出 JSON
- 不能因为“差不多”就接受
- 如果拒绝，必须指出可操作的、具体的错误原因
- 只能根据当前截图、overlay 和 operator 最新输出进行判断
- 不要猜测 operator 的历史思路

### 推荐的 schema 约束

第一期尽量强约束：

- 必填字段固定
- 禁止额外字段
- `action_type` 用 enum
- `verdict` 只允许 `accept` 或 `reject`
- `confidence` / `score` 限制到 `0.0 ~ 1.0`

这样脚本更容易自动化，不容易被模型输出漂移拖垮。

## 失败策略

这里我建议做一个比原始设想更安全的扩展。

### 达到最大轮次时不要强行返回点击

更安全的做法是：

- 如果 6 轮内达成一致，则返回动作
- 如果 6 轮后仍未达成一致，则返回 `status = "unresolved"`
- 附带最后一轮 operator 方案与 evaluator 拒绝理由

这样可以避免在高风险界面上点错。

最终结构可为：

```json
{
  "status": "unresolved",
  "rounds_used": 6,
  "best_candidate": {
    "action_type": "tap",
    "python_call": "tap(1002, 142)"
  },
  "last_evaluator_feedback": {
    "verdict": "reject",
    "reason": "点击点仍然偏左，未进入发送图标主体。"
  }
}
```

如果业务上一定要“总是给一个动作”，也建议至少增加一个字段：

- `safe_to_execute: true | false`

## 可选增强

### 1. 引入自动裁剪

当 evaluator 多次拒绝，或者 operator 自己给出较低置信度时，可以进入局部放大模式：

- operator 同时输出 `focus_bbox_999`
- 脚本自动裁剪该区域
- 下一轮给两个 agent 都传：
  - 原图
  - 局部 crop
  - 当前 overlay

这个能力和仓库现有 `box_tool.py` 能很好衔接。

### 2. operator 输出候选框而不是单点

对点击类动作，推荐 operator 同时输出：

- `bbox_999`
- `point_px`

这样 evaluator 不只看一个点，也能看 operator 对目标区域边界的理解是否正确。

### 3. 为 evaluator 增加“拒绝标签”

把拒绝理由标准化，有利于后续分析：

- `wrong_target`
- `wrong_action_type`
- `unsafe_nearby_controls`
- `gesture_path_wrong`
- `too_uncertain`

### 4. 轨迹可回放

每轮保存：

- 原图
- overlay
- operator JSON
- evaluator JSON

后面可以直接做一个 HTML trace viewer，用来人工检查每轮为什么被拒。

## 建议的脚本入口

建议提供一个简洁 CLI：

```bash
python -m mobile_use.grounding.cli \
  --image /tmp/screen.png \
  --instruction "点击右上角的发送按钮" \
  --model gpt-5.4-mini \
  --max-rounds 6 \
  --out /tmp/grounding-result
```

输出：

- `/tmp/grounding-result/final.json`
- `/tmp/grounding-result/overlay.turn_*.png`
- `/tmp/grounding-result/trace.jsonl`

## 最终返回结构

成功时建议返回：

```json
{
  "status": "accepted",
  "rounds_used": 3,
  "instruction": "点击右上角的发送按钮",
  "action": {
    "action_type": "tap",
    "target_desc": "右上角的发送按钮",
    "point_px": [1002, 142],
    "point_999": [927, 59],
    "python_call": "tap(1002, 142)"
  },
  "overlay_path": "/tmp/grounding-result/overlay.turn_3.png",
  "visual_description": "点击屏幕右上角的发送按钮",
  "evaluator_summary": {
    "score": 0.91,
    "reason": "点击点位于发送图标中心区域，动作类型与用户意图一致。"
  }
}
```

## 一个重要取舍

如果只从“最省 token”出发，可以让 evaluator 只看 operator 的 JSON，不看 overlay。

但从可解释性和 debug 能力来看，我更建议 evaluator 同时看：

- 原图
- overlay 图
- operator JSON

原因是 evaluator 不只是在审查坐标数值，还在审查“这个点在图上到底落在哪儿”。overlay 会显著降低误判。

## 落地建议

如果下一步开始实现，我建议按下面顺序推进：

1. 先实现 `schemas.py` 和 `renderer.py`
2. 再实现 `codex_cli_adapter.py`
3. 然后接 `orchestrator.py` 的 6 轮循环
4. 最后补 `cli.py` 和 trace 落盘

这样可以先把“结构化输出 + 可视化 + 双线程恢复”三件最关键的事情做稳。
