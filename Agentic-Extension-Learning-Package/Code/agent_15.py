#!/usr/bin/env python3
"""agent_15.py —— 后端基础设施 (Backend Infrastructure)。Ch.15。"""
from dataclasses import dataclass, field; from typing import Optional; import hashlib, threading, time, json

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.15 新增: JobQueue + WorkerPool + Outbox + Tenant +++
@dataclass
class OutboxRow:
    id:str; run_id:str; action:str; idempotency_key:str; payload:str=""; status:str="pending"; attempt_count:int=0

@dataclass
class TenantContext:
    tenant_id:str; monthly_limit:int=10000; spend:int=0
    def can_afford(s,cost:int=1)->bool: return s.spend+cost <= s.monthly_limit

class JobQueue:
    def __init__(s): s._queue=[]; s._lock=threading.Lock()
    def submit(s,job:dict)->int: 
        with s._lock: s._queue.append(job); return len(s._queue)
    def claim(s)->Optional[dict]:
        with s._lock: return s._queue.pop(0) if s._queue else None
    @property
    def depth(s): return len(s._queue)

class OutboxDispatcher:
    def __init__(s): s._outbox=[]; s._processed=set()
    def enqueue(s,action,payload,run_id=""):
        key=hashlib.sha256(f"{action}:{json.dumps(payload,sort_keys=True)}".encode()).hexdigest()[:16]
        if key in s._processed: return False
        s._outbox.append(OutboxRow(id=f"out_{len(s._outbox)}",run_id=run_id,action=action,payload=json.dumps(payload),idempotency_key=key)); return True
    @property
    def count(s): return len(s._outbox)

class BackendAgent(BaseAgent):
    def __init__(s,n="BackendAgent",c=None):
        super().__init__(n,c); s.job_queue=JobQueue(); s.outbox=OutboxDispatcher(); s.tenants:dict[str,TenantContext]={}
    def add_tenant(s,t): s.tenants[t.tenant_id]=t

if __name__=="__main__":
    print("="*50); print("  Ch.15 - 后端基础设施"); print("="*50)
    agent=BackendAgent("Ch15Agent")
    agent.add_tenant(TenantContext("team-A"))
    agent.add_tenant(TenantContext("team-B"))
    agent.job_queue.submit({"task":"calc","expr":"1+1"})
    print(f"  队列深度: {agent.job_queue.depth}")
    job=agent.job_queue.claim()
    print(f"  认领任务: {job}")
    agent.outbox.enqueue("calculator",{"expr":"1+1"},"run-001")
    print(f"  Outbox 条目: {agent.outbox.count}")
    print(f"  重复提交: {not agent.outbox.enqueue('calculator',{'expr':'1+1'},'run-001')}")
