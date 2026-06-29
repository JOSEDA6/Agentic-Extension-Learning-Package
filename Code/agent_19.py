#!/usr/bin/env python3
"""agent_19.py —— 运维与 Forward-Deployed (Ops & Forward-Deployed)。Ch.19。"""
from dataclasses import dataclass, field; from typing import Optional; import json, os, signal, threading, time

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.19 新增: 运维就绪 +++
@dataclass
class AppConfig: env:str="dev"; log_level:str="INFO"; version:str="0.1.0"; max_concurrency:int=5

class ShutdownHandler:
    def __init__(s): s._handlers=[]; s._shutdown=False
    def register(s,fn): s._handlers.append(fn)
    def shutdown(s):
        if s._shutdown: return
        s._shutdown=True; print("     [关闭] 开始优雅关闭...")
        for fn in s._handlers:
            try: fn()
            except Exception as e: print(f"     [关闭] 错误: {e}")
        print("     [关闭] 完成")

@dataclass
class RunbookEntry:
    title:str; severity:str; steps:list[str]; owner:str=""

RUNBOOK_CATALOG:dict[str,RunbookEntry]={
    "token_exhausted":RunbookEntry("Token 耗尽","high",["检查用量","充值或降级模型","重试"]),
    "api_timeout":RunbookEntry("API 超时","medium",["检查服务状态","重试","升级模型"]),
    "loop_detected":RunbookEntry("检测到死循环","medium",["检查输入","增加最大步数","检查工具逻辑"]),
}

class OpsAgent(BaseAgent):
    def __init__(s,n="OpsAgent",c=None):
        super().__init__(n,c); s.config_=AppConfig(); s.shutdown=ShutdownHandler()
    def get_runbook(s,incident:str)->Optional[RunbookEntry]: return RUNBOOK_CATALOG.get(incident)
    def assess_maturity(s)->str: return "Stage 2: 可重复"

if __name__=="__main__":
    print("="*50); print("  Ch.19 - 运维与 Forward-Deployed"); print("="*50)
    agent=OpsAgent("Ch19Agent")
    print(f"  环境: {agent.config_.env}, 版本: {agent.config_.version}")
    for name in ["token_exhausted","api_timeout","loop_detected"]:
        rb=agent.get_runbook(name)
        print(f"  Runbook: {rb.title} ({rb.severity})")
    print(f"  成熟度: {agent.assess_maturity()}")
