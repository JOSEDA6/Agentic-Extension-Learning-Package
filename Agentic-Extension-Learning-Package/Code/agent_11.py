#!/usr/bin/env python3
"""agent_11.py —— Agent 运行时 (Agent Harness)。Ch.11。完全独立。"""
from dataclasses import dataclass, field; from typing import Optional, Callable; from enum import Enum; import json, time, threading, signal

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.11 新增: Agent Harness（生命周期管理 + 钩子）+++
class HarnessState(str, Enum): BOOTING="booting"; READY="ready"; DRAINING="draining"; SHUTDOWN="shutdown"

class HookRunner:
    """管理 6 个生命周期钩子点。fail-open 观察 vs fail-closed 门控。"""
    def __init__(s): s._hooks:dict[str,list[Callable]]={"pre_session":[],"pre_llm_call":[],"post_llm_call":[],"pre_tool_call":[],"post_tool_call":[],"post_session":[]}
    def register(s,point:str,hook:Callable):
        if point in s._hooks: s._hooks[point].append(hook)
    def run(s,point:str,context:dict=None):
        results=[]; ctx=context or {}
        for hook in s._hooks.get(point,[]):
            try: r=hook(ctx); results.append(r)
            except Exception as e: results.append({"error":str(e)})
        return results

class AgentHarness(BaseAgent):
    """完整的 Agent 运行时：boot → tick → shutdown + 钩子 + 健康检查。"""
    def __init__(s,n="AgentHarness",c=None):
        super().__init__(n,c); s.state=HarnessState.BOOTING; s.hooks=HookRunner(); s._health={"uptime":0,"ticks":0,"last_tick":0.0}
    def bootstrap(s):
        s.state=HarnessState.READY; s._health["uptime"]=time.time(); s.hooks.run("pre_session"); return True
    def tick(s,user_msg:str) -> RunResult:
        if s.state!=HarnessState.READY: return RunResult(answer="[未就绪]")
        s.hooks.run("pre_llm_call",{"msg":user_msg})
        result=RunResult(answer=f"[模拟 tick] {user_msg[:40]}...",steps=1,stop_reason="completed")
        s._health["ticks"]+=1; s._health["last_tick"]=time.time()
        s.hooks.run("post_llm_call",{"result":result})
        return result
    def shutdown(s):
        s.state=HarnessState.DRAINING; s.hooks.run("post_session"); s.state=HarnessState.SHUTDOWN
    def health(s)->dict: s._health["uptime"]=time.time()-s._health.get("uptime",time.time()); return dict(s._health)

if __name__=="__main__":
    print("="*50); print("  Ch.11 - Agent Harness"); print("="*50)
    h=AgentHarness("Ch11Harness")
    h.hooks.register("pre_llm_call",lambda ctx: print(f"     [钩子] 即将处理: {ctx.get('msg','')[:30]}"))
    h.hooks.register("post_llm_call",lambda ctx: print(f"     [钩子] 处理完成"))
    h.bootstrap()
    print(f"  状态: {h.state.value}")
    r=h.tick("计算 15 * 23 + 100")
    print(f"  tick 结果: {r.answer}")
    print(f"  健康检查: ticks={h.health()['ticks']}")
    h.shutdown()
    print(f"  关闭后状态: {h.state.value}")
