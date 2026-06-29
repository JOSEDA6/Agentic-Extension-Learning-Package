#!/usr/bin/env python3
"""
agent_22.py —— 设计你自己的 Agent (Design Canvas)
对应课程: Ch.22 — Designing your own agent

完全独立。这是整个课程的终点——一张设计画布，帮你把 22 章的知识
组合成一个完整的 Agent 设计方案。
python agent_22.py
"""
from dataclasses import dataclass, field; from typing import Optional; from enum import Enum

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.22 新增: 设计画布 +++
class Archetype(str, Enum):
    PERSONAL_ASSISTANT="personal_assistant"; CODING_AGENT="coding_agent"
    WORKFLOW_CONTROL="workflow_control"; KNOWLEDGE_RESEARCH="knowledge_research"; FORWARD_DEPLOYED="forward_deployed"

ARCHETYPE_INFO = {
    Archetype.PERSONAL_ASSISTANT: {"desc":"个人助手","refs":"Hermes Agent","chapters":"01-07,13,20-21"},
    Archetype.CODING_AGENT: {"desc":"编程 Agent","refs":"OpenCode","chapters":"01-08,12,16-18"},
    Archetype.WORKFLOW_CONTROL: {"desc":"工作流控制","refs":"Paperclip","chapters":"08,11-12,15,19"},
    Archetype.KNOWLEDGE_RESEARCH: {"desc":"研究 Agent","refs":"多种","chapters":"04-07,16,21"},
    Archetype.FORWARD_DEPLOYED: {"desc":"现场部署","refs":"OpenClaw","chapters":"13,19,20"},
}

@dataclass
class DesignCanvas:
    """设计画布: 意图 + 架构决策。"""
    # 意图层
    use_case: str = ""; goal: str = ""; scope_in: list = field(default_factory=list)
    scope_out: list = field(default_factory=list); budget: str = ""
    users: str = ""; success_criteria: str = ""; worst_case: str = ""
    # 架构层
    archetype: Optional[Archetype] = None; loop_shape: str = "sequential"
    planning_mode: str = "none"; tools_needed: list = field(default_factory=list)
    memory_layers: list = field(default_factory=list); persistence: str = "none"
    connectors: list = field(default_factory=list); deployment: str = "cli"
    safety_controls: list = field(default_factory=list)
    proactive: bool = False; evolution_loops: int = 0
    load_bearing: list = field(default_factory=list)

SYSTEM_MAP = {
    "Ch.01": "一次 Tool Call", "Ch.02": "Agent 循环", "Ch.03": "工具契约",
    "Ch.04": "Prompt 与 Cache", "Ch.05": "短期记忆", "Ch.06": "长期检索",
    "Ch.07": "记忆策展", "Ch.08": "持久化状态", "Ch.09": "计划模式",
    "Ch.10": "多 Agent", "Ch.11": "Harness", "Ch.12": "HITL",
    "Ch.13": "连接器/MCP", "Ch.14": "技能/子Agent", "Ch.15": "后端",
    "Ch.16": "可观测性", "Ch.17": "模型路由", "Ch.18": "安全",
    "Ch.19": "运维", "Ch.20": "主动型", "Ch.21": "自我演化",
    "Ch.22": "设计画布 (你在这里)",
}

if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.22 - 设计你自己的 Agent")
    print("=" * 50)

    # 演示: 完整继承链
    chain = ["BaseAgent(Ch.00)", "ToolCallingAgent(Ch.01)", "LoopAgent(Ch.02)",
             "ValidatedAgent(Ch.03)", "CacheAwareAgent(Ch.04)", "MemoryAgent(Ch.05)",
             "RecallAgent(Ch.06)", "CuratorAgent(Ch.07)", "DurableAgent(Ch.08)",
             "PlanningAgent(Ch.09)", "DelegatingAgent(Ch.10)", "AgentHarness(Ch.11)",
             "HITLAgent(Ch.12)", "ConnectedAgent(Ch.13)", "ShapedAgent(Ch.14)",
             "BackendAgent(Ch.15)", "ObservableAgent(Ch.16)", "RoutingAgent(Ch.17)",
             "SecureAgent(Ch.18)", "OpsAgent(Ch.19)", "ProactiveAgent(Ch.20)",
             "EvolvingAgent(Ch.21)", "FullAgent(Ch.22)"]
    print(f"  完整继承链 ({len(chain)} 层):")
    for i, c in enumerate(chain):
        if i % 4 == 3 or i == len(chain)-1:
            print(f"    {' -> '.join(chain[max(0,i-3):i+1])}")

    # 演示: 五种原型
    print("\n  五种 Agent 原型:")
    for arch, info in ARCHETYPE_INFO.items():
        print(f"    {arch.value}: {info['desc']} (参考: {info['refs']})")

    # 演示: 系统全景图
    print("\n  系统全景图 (22 章):")
    for ch, desc in SYSTEM_MAP.items():
        marker = " <--" if "你在这里" in desc else ""
        print(f"    {ch}: {desc}{marker}")

    # 演示: 设计画布
    canvas = DesignCanvas(
        use_case="工单分类与回复", goal="自动分类技术工单并生成回复",
        scope_in=["GitHub Issues", "Slack 消息"], scope_out=["邮件", "电话"],
        budget="50 美元/月", users="3 人技术团队",
        success_criteria="95% 分类准确率，5 分钟内回复",
        archetype=Archetype.CODING_AGENT,
        loop_shape="sequential", planning_mode="checklist",
        tools_needed=["search_issues", "classify", "generate_reply"],
        memory_layers=["short_term", "long_term"], persistence="SQLite",
        connectors=["GitHub API", "Slack API"], safety_controls=["HITL"],
        load_bearing=["Ch.01", "Ch.05", "Ch.12", "Ch.18"],
    )
    print(f"\n  示例画布: [{canvas.archetype.value}]")
    print(f"    场景: {canvas.use_case}")
    print(f"    目标: {canvas.goal}")
    print(f"    承重章节: {canvas.load_bearing}")
