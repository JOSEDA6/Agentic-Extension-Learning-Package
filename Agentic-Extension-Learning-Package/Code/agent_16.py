#!/usr/bin/env python3
"""agent_16.py —— 可观测性 (Observability)。Ch.16。"""
from dataclasses import dataclass, field; from typing import Optional; from contextlib import contextmanager; import threading, time

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.16 新增: Tracer + Metrics + EvalJudge +++
@dataclass
class Span:
    name:str; span_id:str; parent_id:Optional[str]=None; start:float=0.0; end:float=0.0; attributes:dict=field(default_factory=dict); status:str="ok"

class Tracer:
    def __init__(s): s.spans=[]; s._stack=[]
    @contextmanager
    def span(s,name,attrs=None):
        span_id=f"sp_{len(s.spans)}"; parent=s._stack[-1] if s._stack else None
        sp=Span(name=name,span_id=span_id,parent_id=parent.span_id if parent else None,start=time.time(),attributes=attrs or {})
        s._stack.append(sp)
        try: yield sp
        finally: sp.end=time.time(); s._stack.pop(); s.spans.append(sp)
    def stats(s): return {"total":len(s.spans),"open":len(s._stack)}

class MetricsRegistry:
    def __init__(s): s._counters={}; s._gauges={}; s._histograms={}; s._lock=threading.Lock()
    def inc(s,name,val=1):
        with s._lock: s._counters[name]=s._counters.get(name,0)+val
    def gauge(s,name,val):
        with s._lock: s._gauges[name]=val
    def record(s,name,val):
        with s._lock:
            if name not in s._histograms: s._histograms[name]=[]
            s._histograms[name].append(val)
    def snapshot(s): return {"counters":dict(s._counters),"gauges":dict(s._gauges),"histograms":{k:sum(v)/len(v) for k,v in s._histograms.items()}}

class ObservableAgent(BaseAgent):
    def __init__(s,n="ObservableAgent",c=None):
        super().__init__(n,c); s.tracer=Tracer(); s.metrics=MetricsRegistry()

if __name__=="__main__":
    print("="*50); print("  Ch.16 - 可观测性"); print("="*50)
    agent=ObservableAgent("Ch16Agent")
    with agent.tracer.span("tool.call",{"tool":"calculator"}): time.sleep(0.01)
    agent.metrics.inc("model.calls"); agent.metrics.inc("tool.calls"); agent.metrics.gauge("queue.depth",3)
    print(f"  Tracer: {agent.tracer.stats()}")
    print(f"  Metrics: {agent.metrics.snapshot()}")
