#!/usr/bin/env python3
"""agent_12.py —— 人在回路 (Human-in-the-loop)。Ch.12。完全独立。"""
from dataclasses import dataclass, field; from typing import Optional; from enum import Enum; import json, hashlib, time

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.12 新增: Human-in-the-loop +++
class PermissionAction(str, Enum): ALLOW="allow"; ASK="ask"; DENY="deny"
class RiskTier(str, Enum): READ="read"; REVERSIBLE="reversible"; EXTERNAL="external"; HIGH_IMPACT="high_impact"

@dataclass
class PermissionRule:
    """一条权限规则: 工具名模式 + 动作 + 风险等级。"""
    tool_pattern: str; action: PermissionAction; risk: RiskTier = RiskTier.READ
    reason: str = ""

@dataclass
class SuspendedCall:
    """挂起的工具调用（等待审批）。"""
    tool_name: str; args: dict; rule: PermissionRule; timestamp: float = 0.0

class PermissionEngine:
    """权限引擎: 规则集评估（最后匹配者胜）。"""
    def __init__(s): s.rules:list[PermissionRule]=[]
    def add_rule(s,r): s.rules.append(r)
    def evaluate(s,tool_name:str,args:dict) -> tuple[PermissionAction,Optional[PermissionRule]]:
        if not s.rules: return PermissionAction.ALLOW,None
        matched = None
        for r in s.rules:
            if r.tool_pattern in tool_name: matched = r
        if not matched: return PermissionAction.ALLOW,None
        return matched.action,matched

def detect_dangerous(tool_name:str,args:dict) -> list[str]:
    warnings=[]
    if "path" in args:
        p=str(args.get("path",""))
        dangerous=["/etc","~/.ssh",".env","C:\\Windows",";","|","&&"]
        if any(d in p for d in dangerous): warnings.append("危险路径")
    if tool_name in ["delete_file","rm","drop_table","shutdown"]: warnings.append("破坏性操作")
    return warnings

if __name__=="__main__":
    print("="*50); print("  Ch.12 - Human-in-the-loop"); print("="*50)
    engine=PermissionEngine()
    engine.add_rule(PermissionRule("read_file",PermissionAction.ALLOW,RiskTier.READ,"读取文件"))
    engine.add_rule(PermissionRule("delete_file",PermissionAction.DENY,RiskTier.HIGH_IMPACT,"不能删文件"))
    engine.add_rule(PermissionRule("execute",PermissionAction.ASK,RiskTier.HIGH_IMPACT,"执行命令需确认"))
    for test in [("read_file",{"path":"/tmp/test.txt"}),("delete_file",{"path":"/etc/passwd"}),("unknown_tool",{})]:
        action,rule=engine.evaluate(*test)
        danger=detect_dangerous(*test)
        print(f"  {test[0]}({str(test[1])[:30]}...) -> {action.value}, 风险: {danger if danger else '无'}")
