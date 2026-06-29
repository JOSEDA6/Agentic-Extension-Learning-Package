#!/usr/bin/env python3
"""
agent_10.py —— 多 Agent 委派 (Multi-agent Delegation)
对应课程: Ch.10 — Multi-agent delegation
完全独立。 python agent_10.py
"""
from dataclasses import dataclass, field; from typing import Optional; import json, time

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.10 新增: 多 Agent 委派 +++
@dataclass
class DelegationPacket:
    """父 Agent 发给子 Agent 的结构化任务包。"""
    role: str; objective: str; context: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    max_steps: int = 5; budget_tokens: int = 2000; remaining_depth: int = 3

@dataclass
class SubagentResult:
    """子 Agent 返回的结构化结果。"""
    answer: str = ""; success: bool = True; error: str = ""
    evidence: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    uncertainty: float = 0.0; cost_tokens: int = 0

@dataclass
class SubagentProfile:
    """一个 specialist 的完整定义。"""
    name: str; description: str; system_prompt: str = ""
    tool_allowlist: list[str] = field(default_factory=list)
    model: str = ""; max_steps: int = 5; recursion_depth: int = 3

class DelegationEngine:
    """管理 specialist profiles + 执行委派。"""
    def __init__(self): self.profiles: dict[str, SubagentProfile] = {}
    def register(self, p: SubagentProfile): self.profiles[p.name] = p
    def list_roles(self) -> list[str]: return list(self.profiles.keys())
    def can_spawn(self, depth: int) -> bool: return depth > 0
    def delegate(self, packet: DelegationPacket) -> SubagentResult:
        if packet.remaining_depth <= 0: return SubagentResult(answer="深度耗尽",success=False)
        profile = self.profiles.get(packet.role)
        if not profile: return SubagentResult(answer=f"未知角色: {packet.role}",success=False)
        return SubagentResult(answer=f"[{packet.role}] 已处理: {packet.objective[:50]}...",
                              tools_used=profile.tool_allowlist, cost_tokens=150)

class DelegatingAgent(BaseAgent):
    """可以 spawn subagent 的父 Agent。"""
    def __init__(s,n="DelegatingAgent",c=None): super().__init__(n,c); s.engine=DelegationEngine()
    def add_specialist(s,p): s.engine.register(p)
    def delegate(s,role,objective,context="",depth=3) -> SubagentResult:
        return s.engine.delegate(DelegationPacket(role,objective,context,remaining_depth=depth))

if __name__=="__main__":
    print("="*50); print("  Ch.10 - 多 Agent 委派"); print("="*50)
    agent=DelegatingAgent("Ch10Agent")
    agent.add_specialist(SubagentProfile("reviewer","审查代码","检查代码质量和安全性"))
    agent.add_specialist(SubagentProfile("implementer","实现功能","写代码实现需求"))
    print(f"  可用角色: {agent.engine.list_roles()}")
    r1=agent.delegate("reviewer","审查 src/auth.py")
    print(f"  委派结果: {r1.answer}")
    r2=agent.delegate("reviewer","审查另一个文件",depth=0)
    print(f"  深度耗尽: success={r2.success}, error={r2.error}")
