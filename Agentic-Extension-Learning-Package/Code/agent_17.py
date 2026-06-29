#!/usr/bin/env python3
"""agent_17.py —— 成本、延迟与模型策略 (Cost, Latency & Model Strategy)。Ch.17。"""
from dataclasses import dataclass, field; from typing import Optional; from enum import Enum

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.17 新增: 模型路由 + 成本控制 +++
class ProfileName(str, Enum): FAST="fast"; BALANCED="balanced"; DEEP="deep"

@dataclass
class ModelProfile:
    provider:str; model_id:str; input_price:float; output_price:float; context_window:int=128000
    def estimate_cost(s,input_tokens:int,output_tokens:int)->float:
        return (input_tokens/1e6*s.input_price)+(output_tokens/1e6*s.output_price)

class ModelRouter:
    def __init__(s): s.profiles:dict[str,ModelProfile]={}
    def register(s,name,p): s.profiles[name]=p
    def route(s,task_type:str)->ModelProfile:
        if task_type in ["planner","deep_review"]: return s.profiles.get("deep",s.profiles.get("balanced"))
        if task_type in ["builder","summarize"]: return s.profiles.get("balanced")
        return s.profiles.get("fast")

def estimate_cost(profile:ModelProfile,in_tok,out_tok)->float: return profile.estimate_cost(in_tok,out_tok)
def check_budget(profile:ModelProfile,in_tok,out_tok,budget:float)->tuple[bool,float]:
    cost=profile.estimate_cost(in_tok,out_tok); return cost<=budget,cost

if __name__=="__main__":
    print("="*50); print("  Ch.17 - 成本, 延迟与模型策略"); print("="*50)
    router=ModelRouter()
    router.register("fast",ModelProfile("openai","gpt-4o-mini",0.15,0.60))
    router.register("balanced",ModelProfile("openai","gpt-4o",2.50,10.00))
    router.register("deep",ModelProfile("openai","o3",10.00,40.00))
    for task in ["planner","builder","summarize","deep_review"]:
        p=router.route(task); cost=estimate_cost(p,500,200)
        print(f"  {task} -> {p.model_id} (${cost:.4f})")
    ok,cost=check_budget(router.profiles["fast"],1000,200,0.01)
    print(f"  Token 预算检查: ${cost:.4f} <= $0.01? {'通过' if ok else '不足'}")
