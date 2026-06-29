#!/usr/bin/env python3
"""agent_13.py —— 连接器、MCP、IPC。Ch.13。完全独立。"""
from dataclasses import dataclass, field; from typing import Optional; import hashlib, hmac, json, time, threading

@dataclass
class AgentConfig: model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"
class BaseAgent:
    def __init__(s,n="Agent",c=None): s.name=n; s.config=c or AgentConfig(); s.tools:dict[str,callable]={}; s.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"
@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)

# +++ Ch.13 新增: 连接器、MCP、IPC +++
@dataclass
class ChannelEvent:
    """标准化的入站事件。"""
    channel: str; event_id: str; actor_id: str=""; thread_id: str=""; text: str=""; attachments: list=field(default_factory=list); raw: dict=field(default_factory=dict)

class ChannelAdapter:
    def normalize(self,raw:dict)->ChannelEvent: raise NotImplementedError
    def send(self,event:ChannelEvent,text:str): print(f"[{event.channel}] 发送: {text[:50]}...")

class TelegramAdapter(ChannelAdapter):
    def normalize(self,raw:dict)->ChannelEvent:
        return ChannelEvent(channel="telegram",event_id=str(raw.get("update_id",0)),
                           actor_id=str(raw.get("message",{}).get("from",{}).get("id","")),
                           text=raw.get("message",{}).get("text",""))

class MCPClient:
    """外部 MCP 服务器连接器（模拟）。"""
    def __init__(s,name=""): s.name=name; s.tools:dict[str,callable]={}
    def discover_tools(s): return list(s.tools.keys())
    def call_tool(s,name,args): return f"[MCP:{s.name}] {name}({args})"

class WebhookReceiver:
    """HMAC 签名的 Webhook 处理器。"""
    def __init__(s,secret="default-secret"): s.secret=secret; s._seen=set()
    def verify(s,payload:bytes,signature:str)->bool:
        expected=hmac.new(s.secret.encode(),payload,hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected,signature)
    def accept(s,event_id:str)->bool:
        if event_id in s._seen: return False
        s._seen.add(event_id); return True

if __name__=="__main__":
    print("="*50); print("  Ch.13 - 连接器, MCP, IPC"); print("="*50)
    # Telegram
    tg=TelegramAdapter()
    event=tg.normalize({"update_id":1,"message":{"from":{"id":"user1"},"text":"你好"}})
    print(f"  Telegram: channel={event.channel}, text={event.text}")
    # MCP
    mcp=MCPClient("github")
    mcp.tools["list_repos"]=lambda a: f"repos for {a.get('user','')}"
    print(f"  MCP 工具: {mcp.discover_tools()}")
    # Webhook
    wh=WebhookReceiver("secret123")
    sig=hmac.new(b"secret123",b'{"event":"push"}',hashlib.sha256).hexdigest()
    ok=wh.verify(b'{"event":"push"}',sig)
    print(f"  Webhook 验证: {'通过' if ok else '失败'}")
    print(f"  去重: 第一次={wh.accept('evt1')}, 重复={wh.accept('evt1')}")
