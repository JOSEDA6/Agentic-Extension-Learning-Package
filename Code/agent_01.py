#!/usr/bin/env python3
"""
agent_01.py —— 一次工具调用 (Function Calling)
对应课程: Ch.01 — One tool call

这个文件是完全独立的——不依赖任何本地 .py 文件。
它完整复制了 Ch.00 的地基代码（下方已标注），然后加上 Ch.01 的新内容。

你可以单独运行:
  python agent_01.py

如果你是从 Ch.00 一路看过来的——下面的「来自 Ch.00 的地基」你应该很眼熟。
它就是 agent_00.py 的全部内容，复制过来是为了让你不用来回翻文件。
"""

# === 来自 Ch.00 的地基（完整复制，未修改）===
from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentConfig:
    """整个课程中所有 Agent 共用的配置结构。"""
    model: str = "gpt-4o-mini"
    max_steps: int = 10
    token_budget: int = 8000
    api_key: str = "YOUR_API_KEY_HERE"
    base_url: str = "https://api.openai.com/v1"

class BaseAgent:
    """所有后续 Agent 的基类。核心三件套: config + tools + history。"""
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


# +++ Ch.01 新增: 让 Agent 能调用大模型 +++
#
# Ch.00 的 BaseAgent 有了骨架（名字、配置、工具列表），但它还不会"思考"。
# Ch.01 要做的事: 
#   1. 连上大模型（OpenAI 客户端）
#   2. 给模型发一份「工具说明书」（tool schema），告诉它有什么工具可用
#   3. 实现 one_shot(): 一次完整的"问→答→调工具→再答"往返

import json
from openai import OpenAI


class ToolCallingAgent(BaseAgent):
    """
    在 BaseAgent 基础上加入 LLM 调用能力。

    新增三个核心能力:
      - add_tool(): 同时注册 handler（Python 用）+ schema（模型看的说明书）
      - _execute_tool(): 按名字找到工具并执行
      - one_shot(): 一次完整的 LLM 往返（含可能的工具调用）
    """

    def __init__(self, name: str = "ToolCallingAgent", config: AgentConfig = None):
        super().__init__(name, config)

        # Ch.01 新增: 连接 OpenAI 服务器
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

        # Ch.01 新增: 工具说明书列表（发往模型的 JSON）
        self._tool_schemas: list[dict] = []

    # ── 核心方法 1: 注册工具（双通道）──
    def add_tool(self, name: str, description: str, parameters: dict, handler: callable):
        """
        同时注册:
          - handler:  Python 调用的函数（存在 self.tools 里）
          - schema:   发给模型的 JSON 说明书（存在 _tool_schemas 里）

        这两者必须一起改——说明书和实现不一致 = 模型乱调用工具。
        """
        self.tools[name] = handler
        self._tool_schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        })

    @property
    def tool_schemas(self) -> list[dict]:
        """工具说明书列表。子类可以覆盖这个方法。"""
        return self._tool_schemas

    # ── 核心方法 2: 执行工具 ──
    def _execute_tool(self, name: str, args: dict) -> str:
        """
        根据名字找到对应的工具函数，传参并执行。

        这是 Ch.01 的最简版本——没有校验、没有错误信封。
        Ch.03 会加上这些。
        """
        handler = self.tools.get(name)
        if not handler:
            return f"未知工具: {name}"
        try:
            return str(handler(args))
        except Exception as e:
            return f"工具执行错误: {e}"

    # ── 核心方法 3: 单次 LLM 往返 ──
    def one_shot(self, user_message: str, system_prompt: str = "") -> str:
        """
        Ch.01 的全部内容——一次「问→答→调工具→再答」的完整流程。

        步骤:
          1. 准备消息（system prompt + 用户问题）
          2. 发给大模型，附上工具说明书
          3. 模型判断: 直接回答？还是要用工具？
             - 直接回答 → 返回答案
             - 要调用工具 → 执行工具，把结果塞回对话
          4. 把工具结果发给模型，模型给出最终答案

        这就是 Agent 最原子的单元：一次询问 + 可能的一次工具调用。
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        # 第 1 步: 调用大模型
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            tools=self.tool_schemas or None,
        )
        msg = response.choices[0].message

        # 第 2 步: 模型直接回答了（不需要工具）
        if not msg.tool_calls:
            return msg.content or ""

        # 第 3 步: 模型要求调用工具
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            result = self._execute_tool(name, args)
            print(f"     [工具调用] {name}({args}) -> {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # 第 4 步: 把工具结果发给模型，让它给出最终答案
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.01 - 一次工具调用 (继承自 BaseAgent)")
    print("=" * 50)

    # 创建一个 Agent
    agent = ToolCallingAgent("Ch01Agent")

    # 注册一个计算器工具
    # 参数 structure 就是模型看到的"说明书"——模型根据它决定怎么调用
    agent.add_tool(
        name="calculator",
        description="计算数学表达式。用于精确数值计算。不要用于闲聊。",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '15*23+100'"
                }
            },
            "required": ["expression"],
        },
        handler=lambda args: str(eval(args["expression"])),
    )

    print(f"  继承自 BaseAgent: tools={list(agent.tools.keys())}")
    print(f"  Ch.01 新增: client={type(agent.client).__name__}, "
          f"schemas={len(agent.tool_schemas)}")
    print()

    # 注意: 下面的调用需要真实 API Key 才能运行。
    # 如果你没有 API Key，注释掉 one_shot 调用，直接看静态输出。
    # 如果设置了 api_key，取消注释下面两行:
    # result = agent.one_shot("15 * 23 + 100 等于多少？",
    #     "你是助手。遇到计算必须用 calculator。")
    # print(f"  [回答] {result}")

    print("  [提示] 上面的 one_shot() 需要真实 API Key 才能运行。")
    print("  请修改 AgentConfig 的 api_key 后取消注释。")
    print()
    print("  --- Ch.01 新增内容概览 ---")
    print("  1. add_tool(): 同时注册 handler + schema")
    print("  2. _execute_tool(): 按名字执行工具")
    print("  3. one_shot(): 问->答->调工具->再答 的完整往返")
