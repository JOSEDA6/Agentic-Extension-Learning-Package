#!/usr/bin/env python3
"""
agent_09.py —— 计划模式 (Planning Patterns)
对应课程: Ch.09 — Planning patterns

完全独立，不依赖本地 .py 文件。
python agent_09.py
"""

# ============================================================
# 地基代码（精简版）
# ============================================================
import json, os, time, hashlib, math, sqlite3, threading
from enum import Enum; from dataclasses import dataclass, field; from typing import Optional
from openai import OpenAI

@dataclass
class AgentConfig:
    model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"

class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"

@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)
# ============================================================
# 地基代码结束
# ============================================================


# +++ Ch.09 新增: 计划模式 +++
#
# 前八章的 Agent 都是"直接行动"模式——收到问题就立刻调用工具。
# Ch.09 让 Agent 先做计划再执行，实现 Checklist 模式 + DAG 依赖图。

class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class PlanStep:
    """检查清单中的一个步骤。"""
    id: str
    text: str
    status: StepStatus = StepStatus.PENDING
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """完整的检查清单计划。"""
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: float = 0.0
    replan_count: int = 0
    last_replan_reason: str = ""

    @property
    def completed(self) -> set[str]:
        return {s.id for s in self.steps if s.status == StepStatus.DONE}

    @property
    def progress(self) -> str:
        if not self.steps:
            return "0/0"
        done = len([s for s in self.steps if s.status == StepStatus.DONE])
        return f"{done}/{len(self.steps)}"


class ReplanTriggers:
    """
    重新计划的触发器。
    检测: 某一步连续失败 / 新信息与计划矛盾。
    """

    @staticmethod
    def step_failed_repeatedly(failures: list[str], threshold: int = 3) -> bool:
        """同一目标连续失败 threshold 次以上 → 触发重新计划。"""
        return len(failures) >= threshold

    @staticmethod
    def new_info_contradicts(plan: Plan, new_info: str) -> bool:
        """新信息与计划的前提条件矛盾。"""
        # 简化版: 检查是否包含"重新"、"改变"等关键词
        contradictory = ["重新", "改变", "cancel", "stop", "不做了"]
        return any(kw in new_info for kw in contradictory)


@dataclass
class PlanNode:
    """DAG 依赖图中的一个节点。"""
    id: str
    text: str
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING


def find_runnable(nodes: list[PlanNode]) -> list[PlanNode]:
    """
    在 DAG 中找到所有可运行的节点。
    条件: 所有依赖节点都已完成。
    """
    done_ids = {n.id for n in nodes if n.status == StepStatus.DONE}
    return [
        n for n in nodes
        if n.status == StepStatus.PENDING
        and all(dep in done_ids for dep in n.depends_on)
    ]


class PlanningAgent(BaseAgent):
    """
    在 BaseAgent 基础上加入计划管理能力。
    """

    def __init__(self, name: str = "PlanningAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.current_plan: Optional[Plan] = None

    def plan_checklist(self, goal: str, steps: list[PlanStep]):
        """构建一个检查清单计划。"""
        self.current_plan = Plan(
            goal=goal, steps=steps, created_at=time.time())

    def render_plan(self) -> str:
        """把当前计划渲染成文本（可以发给模型看）。"""
        if not self.current_plan:
            return "[无计划]"
        lines = [f"目标: {self.current_plan.goal}"]
        for s in self.current_plan.steps:
            deps = f" [依赖: {s.depends_on}]" if s.depends_on else ""
            lines.append(f"  [{s.status.value}] {s.id}: {s.text}{deps}")
        lines.append(f"进度: {self.current_plan.progress}")
        return "\n".join(lines)


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.09 - 计划模式 (继承自 BaseAgent)")
    print("=" * 50)

    agent = PlanningAgent("Ch09Agent")

    # 演示: 检查清单计划
    print("  [检查清单计划]")
    agent.plan_checklist("学习 Python Agent 开发", [
        PlanStep("step1", "安装 Python", StepStatus.DONE),
        PlanStep("step2", "学习基础语法", StepStatus.IN_PROGRESS),
        PlanStep("step3", "学习 Tool Calling", depends_on=["step1", "step2"]),
        PlanStep("step4", "实现第一个 Agent", depends_on=["step3"]),
    ])
    print(f"  {agent.render_plan()}")
    print(f"  进度: {agent.current_plan.progress}")

    # 演示: DAG 依赖图
    print("\n  [DAG 依赖图]")
    nodes = [
        PlanNode("fetch", "获取数据"),
        PlanNode("analyze", "分析数据", depends_on=["fetch"]),
        PlanNode("report", "生成报告", depends_on=["analyze"]),
    ]
    print(f"  初始可运行: {[n.id for n in find_runnable(nodes)]}")
    nodes[0].status = StepStatus.DONE  # fetch 完成
    print(f"  fetch 完成后可运行: {[n.id for n in find_runnable(nodes)]}")
    nodes[1].status = StepStatus.DONE  # analyze 完成
    print(f"  analyze 完成后可运行: {[n.id for n in find_runnable(nodes)]}")

    # 演示: 重新计划触发器
    print("\n  [重新计划触发器]")
    failures = ["fail1", "fail2", "fail3"]
    triggered = ReplanTriggers.step_failed_repeatedly(failures)
    print(f"  连续 {len(failures)} 次失败 -> 触发重新计划: {triggered}")
