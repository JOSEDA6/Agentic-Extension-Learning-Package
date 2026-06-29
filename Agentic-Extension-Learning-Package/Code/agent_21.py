#!/usr/bin/env python3
"""agent_21.py —— 自我演化型 Agent (Self-evolving Agents)。Ch.21。"""
from dataclasses import dataclass, field; from typing import Optional; from enum import Enum; import hashlib, threading, time

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.21 新增: 自我演化 +++
class UpdateKind(str, Enum): MEMORY="memory"; SKILL="skill"; PROMPT_SECTION="prompt_section"; LORA_WEIGHT="lora_weight"
class UpdateStatus(str, Enum): PROPOSED="proposed"; EVALUATING="evaluating"; APPROVED="approved"; REJECTED="rejected"; APPLIED="applied"; ROLLED_BACK="rolled_back"

@dataclass
class ProposedUpdate:
    id:str; kind:UpdateKind; patch:str; rationale:str=""; risk:str="low"; status:UpdateStatus=UpdateStatus.PROPOSED

class EvolutionEngine:
    """Agent 提议 → 引擎裁决。Agent 永不直接修改自己。"""
    def __init__(s): s._lock=threading.Lock(); s._history:list[ProposedUpdate]=[]
    def propose(s,kind:UpdateKind,patch:str,rationale:str="")->ProposedUpdate:
        upd=ProposedUpdate(id=f"upd_{len(s._history)}_{int(time.time())}",kind=kind,patch=patch,rationale=rationale)
        with s._lock: s._history.append(upd)
        return upd
    def evaluate(s,upd:ProposedUpdate,baseline:float=0.8)->bool:
        if upd.risk=="high" and baseline<0.9: upd.status=UpdateStatus.REJECTED; return False
        upd.status=UpdateStatus.APPROVED; return True

class DriftDetector:
    def __init__(s,threshold=0.05): s.baseline=None; s.threshold=threshold; s.current=None
    def capture(s,value:float): s.baseline=value
    def check(s,value:float)->tuple[bool,float]:
        if s.baseline is None: return False,0.0
        drift=abs(value-s.baseline)
        return drift>s.threshold,drift

if __name__=="__main__":
    print("="*50); print("  Ch.21 - 自我演化型 Agent"); print("="*50)
    engine=EvolutionEngine()
    for kind,patch,risk in [("skill","优化 calculator 描述","low"),("memory","用户偏好: Python","low"),("prompt_section","添加安全提醒","high")]:
        upd=engine.propose(UpdateKind(kind),patch,f"优化{kind}")
        ok=engine.evaluate(upd,0.85)
        print(f"  提案 [{kind}] {patch[:30]}... -> {'通过' if ok else '拒绝'}")
    dd=DriftDetector(0.05); dd.capture(0.88)
    drifted,drift=dd.check(0.82)
    print(f"  漂移检测: baseline=0.88, current=0.82, drift={drift:.3f}, {'漂移!' if drifted else '正常'}")
