#!/usr/bin/env python3
"""
agent_02.py —— Agent 循环 (The Agent Loop)
对应课程: Ch.02 — The agent loop

这个文件是完全独立的——不依赖任何本地 .py 文件。
它完整复制了 Ch.00 和 Ch.01 的代码，然后加上 Ch.02 的新内容。

你可以单独运行:
  python agent_02.py

新学什么:
  - RunResult: 记录 Agent 运行的结果（答案、步数、token 数）
  - LoopAgent: 在 one_shot 外面包了一个 while 循环
  - 四种停止条件: 模型说停 / final_answer 工具 / 步数上限 / token 预算
  - 死循环检测: 如果 Agent 连续 3 次调用同样的工具+参数，就打断它
"""

# === 来自 Ch.00 的地基 ===
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"
    max_steps: int = 10
    token_budget: int = 8000
    api_key: str = "YOUR_API_KEY_HERE"
    base_url: str = "https://api.openai.com/v1"

class BaseAgent:
    def __init__(self, name: str = "Agent", config: Optional[AgentConfig] = None):
        self.name = name
        self.config = config or AgentConfig()
        self.tools: dict[str, callable] = {}
        self.history: list[dict] = []
    def register_tool(self, name: str, handler: callable):
        self.tools[name] = handler
    def __repr__(self):
        return (f"<{self.__class__.__name__}('{self.name}': "
                f"tools={list(self.tools.keys())}, "
                f"history={len(self.history)} msgs)>")
# === 来自 Ch.00 的地基结束 ===


# +++ 来自 Ch.01 的代码（工具调用 + LLM 客户端）+++
import json
from openai import OpenAI

class ToolCallingAgent(BaseAgent):
    def __init__(self, name: str = "ToolCallingAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        self._tool_schemas: list[dict] = []

    def add_tool(self, name: str, description: str, parameters: dict, handler: callable):
        self.tools[name] = handler
        self._tool_schemas.append({
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        })

    @property
    def tool_schemas(self) -> list[dict]:
        return self._tool_schemas

    def _execute_tool(self, name: str, args: dict) -> str:
        handler = self.tools.get(name)
        if not handler:
            return f"未知工具: {name}"
        try:
            return str(handler(args))
        except Exception as e:
            return f"工具执行错误: {e}"

    def one_shot(self, user_message: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        response = self.client.chat.completions.create(
            model=self.config.model, messages=messages, tools=self.tool_schemas or None,
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = self._execute_tool(name, args)
            print(f"     [工具调用] {name}({args}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        response = self.client.chat.completions.create(
            model=self.config.model, messages=messages,
        )
        return response.choices[0].message.content or ""
# +++ 来自 Ch.01 的代码结束 +++


# +++ Ch.02 新增: Agent 循环 +++
#
# 上一章的 one_shot() 只能做一轮「问→答」。
# 但真实场景中，Agent 可能需要多轮工具调用才能回答一个复杂问题。
#
# 例: 用户问「北京和东京的时差是多少？」
#   第 1 轮: 查北京的时区 → 得到 UTC+8
#   第 2 轮: 查东京的时区 → 得到 UTC+9
#   第 3 轮: 计算时差 → 得到 1 小时
#
# Ch.02 就把 one_shot 包进一个 while 循环里，让 Agent 能一直
# 「思考→行动→观察→再思考」，直到任务完成或达到上限。

import time

@dataclass
class RunResult:
    """Agent 一次运行的完整记录。"""
    answer: str = ""
    steps: int = 0                # 跑了多少轮
    total_tokens: int = 0         # 花了多少 token
    stop_reason: str = ""         # 为什么停下来
    tool_calls_made: list[dict] = field(default_factory=list)


class LoopAgent(ToolCallingAgent):
    """
    在 ToolCallingAgent 基础上加入 while 循环。

    新能力:
      - run(): 持续调用 LLM，每轮检查要不要停下来
      - 四种停止条件（从软到硬）:
          1. 模型说完成了（finish_reason = "stop"）
          2. 调用了 final_answer 工具
          3. 达到步数上限
          4. Token 预算耗尽（会发一次 grace call 让模型紧急收尾）
      - doom_loop 检测: 连续 3 次同样的工具+参数 = 卡死了
    """

    def __init__(self, name: str = "LoopAgent", config: AgentConfig = None):
        super().__init__(name, config)
        # 死循环检测: 记录最近几次工具调用
        self._recent_calls: list[tuple[str, str]] = []
        self._doom_threshold = 3   # 连续 3 次相同就判定卡死

    def _check_doom_loop(self, tool_name: str, args: dict) -> bool:
        """
        检测死循环: 如果连续 N 次调用同一个工具+同样的参数，
        大概率是 Agent 卡住了，需要打断它。
        """
        key = json.dumps(args, sort_keys=True)
        self._recent_calls.append((tool_name, key))
        # 只保留最近 N 条记录
        if len(self._recent_calls) > self._doom_threshold:
            self._recent_calls.pop(0)
        # 检查最近 N 条是否完全一样
        if len(self._recent_calls) >= self._doom_threshold:
            if all(n == tool_name and a == key for n, a in self._recent_calls):
                return True
        return False

    # ── Ch.02 核心: Agent 循环 ──
    def run(self, user_message: str, system_prompt: str = "") -> RunResult:
        """
        Ch.02 的全部内容 —— Agent 循环。

        每一轮的流程:
          接收消息 -> 调 LLM -> 检查结果 -> 执行工具 -> 继续循环

        停止条件（从软到硬，依次检查）:
          1. 模型不再要求调用工具 -> 正常返回
          2. 模型调用了 final_answer 工具 -> 提取答案
          3. 步数达到 max_steps -> 强制停止
          4. Token 预算超过 token_budget -> 发 grace call 收尾
        """
        result = RunResult()
        messages = []

        # 准备消息
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        for step in range(1, self.config.max_steps + 1):
            # 调大模型
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                tools=self.tool_schemas or None,
            )
            msg = response.choices[0].message
            usage = response.usage
            turn_tokens = usage.total_tokens if usage else 0
            result.total_tokens += turn_tokens
            result.steps = step

            # 停止条件 1: 模型认为完成了，不再要工具
            if not msg.tool_calls:
                result.answer = msg.content or ""
                result.stop_reason = f"model_driven({response.choices[0].finish_reason})"
                print(f"     [停止] 模型认为完成, 原因: {result.stop_reason}")
                return result

            # 执行工具
            messages.append(msg)
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                # 死循环检测
                if self._check_doom_loop(name, args):
                    tool_result = (f"[死循环] '{name}' 连续调用了 "
                                   f"{self._doom_threshold} 次，参数相同。请换种方法。")
                    print(f"     [死循环检测] 打断! {name}({args})")
                else:
                    tool_result = self._execute_tool(name, args)

                print(f"     [Step {step}] {name}({args}) -> {str(tool_result)[:60]}")
                result.tool_calls_made.append({
                    "step": step, "tool": name, "args": args,
                    "result": str(tool_result)[:200]
                })

                # 停止条件 2: 调用了 final_answer 工具
                if name == "final_answer":
                    result.answer = str(tool_result)
                    result.stop_reason = "final_answer_tool"
                    print(f"     [停止] 调用了 final_answer 工具")
                    return result

                # 把工具结果加回消息列表
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": str(tool_result),
                })

            # 停止条件 4: Token 预算快用完了 -> 发 grace call
            if result.total_tokens >= self.config.token_budget:
                print(f"     [警告] Token 预算耗尽，发送 grace call 让模型紧急收尾")
                messages.append({
                    "role": "user",
                    "content": "你的 token 预算已耗尽。请立即用 final_answer 提交最终答案。",
                })
                # 继续循环，让模型在下一轮处理 grace call

        # 停止条件 3: 步数达到上限
        result.answer = "[达到步数上限]"
        result.stop_reason = "step_cap"
        print(f"     [停止] 达到步数上限 ({self.config.max_steps})")
        return result
# +++ Ch.02 新增结束 +++


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.02 - Agent 循环 (继承自 ToolCallingAgent)")
    print("=" * 50)

    agent = LoopAgent("Ch02Agent")

    # 注册计算器工具
    agent.add_tool(
        "calculator",
        "计算数学表达式。用于精确数值计算。",
        {"type": "object", "properties": {"expression": {"type": "string"}},
         "required": ["expression"]},
        lambda args: str(eval(args["expression"])),
    )

    # 注册 final_answer 工具（让模型能主动说"做完了"）
    agent.add_tool(
        "final_answer",
        "当你确定任务完成时，必须调用此工具提交最终答案。",
        {"type": "object", "properties": {"text": {"type": "string"}},
         "required": ["text"]},
        lambda args: args.get("text", "完成"),
    )

    print(f"  继承自 ToolCallingAgent: client={type(agent.client).__name__}, "
          f"tools={list(agent.tools.keys())}")
    print(f"  Ch.02 新增: run_loop + 停止条件 + doom_loop 检测")
    print()

    # 注意: run() 需要真实 API Key。如果没有，看下面的静态输出。
    # result = agent.run("计算 (15 + 23) * 7 / 2",
    #     "你是助手。计算用 calculator，完成用 final_answer。")
    # print(f"\n  答案: {result.answer}")
    # print(f"  统计: steps={result.steps}, tokens={result.total_tokens}, "
    #       f"stop={result.stop_reason}")

    print("  [提示] 上面的 run() 需要真实 API Key 才能运行。")
    print("  请修改 AgentConfig 的 api_key 后取消注释。")
    print()
    print("  --- Ch.02 新增内容概览 ---")
    print("  1. RunResult: 记录运行结果")
    print("  2. run(): while 循环代替单次调用")
    print("  3. 四种停止条件: 模型驱动 / final_answer / 步数 / token")
    print("  4. doom_loop 检测: 连续 3 次相同调用 = 卡死")
