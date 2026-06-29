#!/usr/bin/env python3
"""agent_20.py —— 主动型 Agent (Proactive Agents)。Ch.20。"""
from dataclasses import dataclass, field; from typing import Optional; from enum import Enum; import hashlib, threading, time

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.20 新增: 主动行为 +++
class TriggerType(str, Enum): CRON="cron"; EVENT="event"; WATCHDOG="watchdog"

@dataclass
class CronJob:
    id:str; agent:str; schedule:str; missed_fire:str="skip"; payload:dict=field(default_factory=dict)
    def run_key(s)->str: return hashlib.sha256(f"{s.id}:{s.schedule}".encode()).hexdigest()[:12]

@dataclass
class ProactivePermission:
    enabled:bool=False; frequency_cap:int=10; quiet_start:str=""; quiet_end:str=""; snooze_until:float=0.0

class ProactiveGate:
    def __init__(s): s.permissions:dict[str,dict[str,ProactivePermission]]={}
    def set(s,user,category,perm): s.permissions.setdefault(user,{})[category]=perm
    def can_notify(s,user,category)->tuple[bool,str]:
        cat_perms=s.permissions.get(user,{})
        perm=cat_perms.get(category)
        if not perm or not perm.enabled: return False,"未启用"
        if perm.snooze_until>time.time(): return False,f"已静音到 {perm.snooze_until}"
        if perm.quiet_start and perm.quiet_end:
            now=time.localtime(); cur=f"{now.tm_hour:02d}:{now.tm_min:02d}"
            if perm.quiet_start<=cur<perm.quiet_end: return False,f"静音时段 ({perm.quiet_start}-{perm.quiet_end})"
        return True,""

if __name__=="__main__":
    print("="*50); print("  Ch.20 - 主动型 Agent"); print("="*50)
    job=CronJob("daily-brief","BriefAgent","0 9 * * 1-5")
    print(f"  CronJob: {job.id} @ {job.schedule}, key={job.run_key()}")
    gate=ProactiveGate()
    gate.set("alice","deploy_alerts",ProactivePermission(enabled=True,quiet_start="22:00",quiet_end="06:00"))
    gate.set("alice","weekly_summary",ProactivePermission(enabled=False))
    cat=("deploy_alerts","weekly_summary")
    for c in cat:
        ok,reason=gate.can_notify("alice",c)
        print(f"  alice/{c}: {'通过' if ok else f'拒绝 ({reason})'}")
