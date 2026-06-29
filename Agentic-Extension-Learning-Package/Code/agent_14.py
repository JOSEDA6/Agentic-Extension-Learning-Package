#!/usr/bin/env python3
"""agent_14.py —— 技能、MCP与子Agent (Skills, MCP & Subagents)。Ch.14。完全独立。"""
from dataclasses import dataclass, field; from typing import Optional

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.14 新增: 技能存储 + 决策准则 +++
@dataclass
class Skill:
    name: str; description: str; body: str = ""; version: int = 1

class SkillStore:
    """完整的 Skill 生命周期管理。"""
    def __init__(s): s._skills:dict[str,Skill]={}
    def register(s,skill:Skill): s._skills[skill.name]=skill
    def list(s) -> list[str]: return list(s._skills.keys())
    def get(s,name:str) -> Optional[Skill]: return s._skills.get(name)
    def get_prefix(s) -> str: return "\n".join(f"  - {sk.name}: {sk.description}" for sk in s._skills.values())

def decide_shape(is_procedural:bool, needs_external:bool, needs_reasoning:bool) -> str:
    """
    Ch.14 核心决策准则: 判断选哪种能力形态。
    优先级: Skill > MCP Server > Subagent > Built-in Tool
    """
    if is_procedural and not needs_external: return "skill"
    if needs_external and not needs_reasoning: return "mcp_server"
    if needs_reasoning: return "subagent"
    return "builtin_tool"

class ShapedAgent(BaseAgent):
    """带 SkillStore 和决策准则的 Agent。"""
    def __init__(s,n="ShapedAgent",c=None):
        super().__init__(n,c); s.skill_store=SkillStore()
    def register_skill(s,skill:Skill): s.skill_store.register(skill)
    def decide_capability(s,is_procedural=False,needs_external=False,needs_reasoning=False) -> str:
        return decide_shape(is_procedural,needs_external,needs_reasoning)

if __name__=="__main__":
    print("="*50); print("  Ch.14 - 技能, MCP & 子Agent"); print("="*50)
    agent=ShapedAgent("Ch14Agent")
    agent.register_skill(Skill("review_ts","审查 TypeScript 代码","检查类型安全..."))
    agent.register_skill(Skill("deploy_check","部署前置检查","检查构建和测试..."))
    print(f"  注册的技能: {agent.skill_store.list()}")
    print(f"  技能索引前缀:\n    {agent.skill_store.get_prefix()[:80]}...")
    for desc,proc,ext,reason in [("审查PR",True,False,False),("PDF解析",False,True,False),("跨文档研究",False,True,True),("grep搜索",False,False,False)]:
        shape=agent.decide_capability(proc,ext,reason)
        print(f"  {desc} -> {shape}")
