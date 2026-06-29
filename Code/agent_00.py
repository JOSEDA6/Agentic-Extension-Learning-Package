#!/usr/bin/env python3
"""
agent_00.py —— 课程起点：Agent 骨架
对应课程: Ch.00 — How to use this course

这是你亲手搭建的第一个 Agent 地基。
整个课程所有的 Agent 都从这个地基生长出来。

如果你第一次接触 Agent——别慌。这个文件只有 60 行，读完你就知道 Agent
长什么样了。后面的 22 个文件会在这个骨架上一次次「长肌肉」。

[注意] 重要: 这个文件是独立的——它不依赖任何同目录下的其他 .py 文件。
你直接运行就能看到效果:
  python agent_00.py

如果你是从 agent_01.py 开始看的，请放心——agent_01.py 会完整复制
这里的代码，你不需要来回翻文件。
"""

from dataclasses import dataclass
from typing import Optional


# ── 地基: Agent 配置 ────────────────────────────────────
# 一个 Agent 需要知道: 用什么模型、最多跑几步、花多少钱。
# 这些就是「配置」。dataclass 是 Python 自带的"数据容器"，
# 比字典更规范，比类更轻量。

@dataclass
class AgentConfig:
    """整个课程中所有 Agent 共用的配置结构。"""
    model: str = "gpt-4o-mini"       # 大模型的名字
    max_steps: int = 10              # 最多循环多少轮
    token_budget: int = 8000         # token 预算上限
    api_key: str = "YOUR_API_KEY_HERE"  # API 密钥（后续替换）
    base_url: str = "https://api.openai.com/v1"


# ── 地基: 最小 Agent ────────────────────────────────────
# Agent = 配置 + 工具 + 记忆。
# 这是后面 22 章所有 Agent 的起点。

class BaseAgent:
    """
    所有后续 Agent 的基类。

    核心三件套:
      - config:  配置（上面定义的 AgentConfig）
      - tools:   工具注册表（后面章节会用到）
      - history: 对话历史（后面章节会用到）

    Ch.00 的目标就是让你理解这个最小结构。
    """

    def __init__(self, name: str = "Agent", config: Optional[AgentConfig] = None):
        self.name = name
        self.config = config or AgentConfig()
        self.tools: dict[str, callable] = {}   # 工具字典: {工具名: 处理函数}
        self.history: list[dict] = []          # 对话消息列表

    def register_tool(self, name: str, handler: callable):
        """注册一个最简单的工具（只有名字和处理函数）。"""
        self.tools[name] = handler

    def __repr__(self):
        """打印 Agent 时能看到它的名字、工具数和消息数。"""
        return (f"<{self.__class__.__name__}('{self.name}': "
                f"tools={list(self.tools.keys())}, "
                f"history={len(self.history)} msgs)>")


# ── 演示 ────────────────────────────────────────────────
# 这里就是 Ch.00 的"动手看看"环节。
# 运行这个文件，你会看到地基已经搭好了。

if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.00 — Agent 骨架 (地基)")
    print("=" * 50)

    # 创建一个叫 MyAgent 的 Agent，什么都不用配置
    agent = BaseAgent("MyAgent")

    # 注册一个最简单的工具: echo — 你说什么它回什么
    agent.register_tool("echo", lambda msg: msg)

    # 打印 Agent 的信息
    print(f"  {agent}")
    print(f"  配置: model={agent.config.model}, "
          f"max_steps={agent.config.max_steps}")
    print()
    print("  [地基已就绪。]")
    print("  下一章 (agent_01.py) 会在这个骨架上加入 LLM 调用。")
    print("  但 agent_01.py 会完整复制这份代码——你不需要来回翻文件。")
