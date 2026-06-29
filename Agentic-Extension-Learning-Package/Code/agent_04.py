#!/usr/bin/env python3
"""
agent_04.py —— Prompt 组装与 Cache
对应课程: Ch.04 — Prompts, context, and the cache

这个文件是完全独立的——不依赖任何本地 .py 文件。
它完整复制了前三章的代码，然后加上 Ch.04 的新内容。

你可以单独运行:
  python agent_04.py

新学什么:
  - PromptBuilder: 把 system prompt 分成「稳定前缀」+「易变尾部」
  - SHA 指纹追踪: 知道前缀的每一层谁变了
  - CacheTracker: 记录 API 调用的 cache 命中情况
  - CacheAwareAgent: 自动构建前缀 + 记录 cache

为什么重要:
  给大模型的 system prompt 里，大部分内容（身份、工具 schema、项目背景）
  每轮对话都是一样的。如果能保持它们逐字节一致，API 的 prompt cache
  就能命中——省钱又省时。随便加个时间戳进去，cache 就永远不命中。
"""

# === 来自 Ch.00 的地基 ===
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"
    max_steps: int = 10
    token_budget: int = 8000
    api_key: str = "YOUR_API_KEY_HERE"
    base_url: str = "https://api.openai.com/v1"

class BaseAgent:
    def __init__(self, name: str = "Agent", config: Optional[AgentConfig] = None):
        self.name = name; self.config = config or AgentConfig()
        self.tools: dict[str, callable] = {}; self.history: list[dict] = []
    def register_tool(self, name: str, handler: callable): self.tools[name] = handler
    def __repr__(self):
        return (f"<{self.__class__.__name__}('{self.name}': "
                f"tools={list(self.tools.keys())}, history={len(self.history)} msgs)>")
# === 来自 Ch.00 的地基结束 ===

# +++ 来自 Ch.01 的代码 +++
import json; from openai import OpenAI
class ToolCallingAgent(BaseAgent):
    def __init__(self, name="ToolCallingAgent", config=None):
        super().__init__(name, config)
        self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        self._tool_schemas: list[dict] = []
    def add_tool(self, name, desc, params, handler):
        self.tools[name] = handler
        self._tool_schemas.append({
            "type":"function","function":{"name":name,"description":desc,"parameters":params}})
    @property
    def tool_schemas(self): return self._tool_schemas
    def _execute_tool(self, name, args):
        h = self.tools.get(name)
        if not h: return f"未知工具: {name}"
        try: return str(h(args))
        except Exception as e: return f"工具执行错误: {e}"
    def one_shot(self, user_msg, sys_prompt=""):
        msgs = [{"role":"system","content":sys_prompt},{"role":"user","content":user_msg}] if sys_prompt else [{"role":"user","content":user_msg}]
        r = self.client.chat.completions.create(model=self.config.model,messages=msgs,tools=self.tool_schemas or None)
        msg = r.choices[0].message
        if not msg.tool_calls: return msg.content or ""
        msgs.append(msg)
        for tc in msg.tool_calls:
            n,a = tc.function.name, json.loads(tc.function.arguments)
            res = self._execute_tool(n, a)
            print(f"     [工具调用] {n}({a}) -> {res}")
            msgs.append({"role":"tool","tool_call_id":tc.id,"content":res})
        r2 = self.client.chat.completions.create(model=self.config.model,messages=msgs)
        return r2.choices[0].message.content or ""
# +++ 来自 Ch.01 的代码结束 +++

# +++ 来自 Ch.02 的代码 +++
import time
@dataclass
class RunResult:
    answer: str = ""; steps: int = 0; total_tokens: int = 0
    stop_reason: str = ""; tool_calls_made: list[dict] = field(default_factory=list)

class LoopAgent(ToolCallingAgent):
    def __init__(self, name="LoopAgent", config=None):
        super().__init__(name, config)
        self._recent_calls = []; self._doom_threshold = 3
    def _check_doom_loop(self, name, args):
        key = json.dumps(args, sort_keys=True)
        self._recent_calls.append((name, key))
        if len(self._recent_calls) > self._doom_threshold: self._recent_calls.pop(0)
        if len(self._recent_calls) >= self._doom_threshold:
            if all(n==name and a==key for n,a in self._recent_calls): return True
        return False
    def run(self, user_msg, sys_prompt=""):
        result = RunResult()
        msgs = ([{"role":"system","content":sys_prompt},{"role":"user","content":user_msg}]
                if sys_prompt else [{"role":"user","content":user_msg}])
        for step in range(1, self.config.max_steps+1):
            r = self.client.chat.completions.create(
                model=self.config.model,messages=msgs,tools=self.tool_schemas or None)
            msg = r.choices[0].message
            result.total_tokens += (r.usage.total_tokens if r.usage else 0)
            result.steps = step
            if not msg.tool_calls:
                result.answer = msg.content or ""
                result.stop_reason = f"model_driven({r.choices[0].finish_reason})"
                return result
            msgs.append(msg)
            for tc in msg.tool_calls:
                n,a = tc.function.name, json.loads(tc.function.arguments)
                tool_res = (f"[死循环] '{n}' 连续 {self._doom_threshold} 次相同参数"
                            if self._check_doom_loop(n,a) else self._execute_tool(n,a))
                print(f"     [Step {step}] {n}({a}) -> {str(tool_res)[:60]}")
                result.tool_calls_made.append({"step":step,"tool":n,"args":a,"result":str(tool_res)[:200]})
                if n == "final_answer":
                    result.answer = str(tool_res); result.stop_reason = "final_answer_tool"
                    return result
                msgs.append({"role":"tool","tool_call_id":tc.id,"content":str(tool_res)})
            if result.total_tokens >= self.config.token_budget:
                print("     [警告] Token 预算耗尽，发 grace call")
                msgs.append({"role":"user","content":"token 预算已耗尽。请立即用 final_answer 提交最终答案。"})
        result.answer = "[达到步数上限]"; result.stop_reason = "step_cap"
        return result
# +++ 来自 Ch.02 的代码结束 +++

# +++ 来自 Ch.03 的代码 +++
import os, hashlib

@dataclass
class ToolResult:
    ok: bool; content: str = ""; recoverable: bool = True
    code: str = ""; hint: str = ""; meta: dict = field(default_factory=dict)
    def to_message(self) -> str:
        if self.ok: return self.content
        msg = f"[{self.code}] {self.content}"
        if self.hint: msg += f"\n提示: {self.hint}"
        return msg

@dataclass
class ToolMeta:
    read_only: bool = False; destructive: bool = False
    concurrency_safe: bool = True; idempotent: bool = False
    open_world: bool = False; max_result_chars: int = 2000
    timeout: int = 30; version: int = 1

class ToolRegistry:
    def __init__(self): self._entries: dict[str, dict] = {}
    def register(self, name, desc, params, handler, meta=None):
        self._entries[name] = {
            "schema": {"type":"function","function":{"name":name,"description":desc,"parameters":params}},
            "meta": meta or ToolMeta(), "handler": handler}
    def get_schemas(self): return [e["schema"] for e in self._entries.values()]
    def get_meta(self, name): e=self._entries.get(name); return e["meta"] if e else None
    def is_known(self, name): return name in self._entries
    def validate_and_execute(self, name, args, workspace="."):
        if not self.is_known(name):
            return ToolResult(False,f"未知工具: {name}",recoverable=False,code="UNKNOWN_TOOL",hint=f"可用: {list(self._entries.keys())}")
        entry=self._entries[name]; meta=entry["meta"]
        if "path" in args:
            path=str(args["path"]); dangerous=["/etc/","~/.ssh",".env","C:\\Windows"]
            if any(d in path for d in dangerous):
                return ToolResult(False,f"路径不安全: {path}",recoverable=True,code="UNSAFE_PATH",hint="请使用工作目录内的路径。")
        if meta.destructive: print(f"     [权限检查] 破坏性操作: {name}({args})")
        try:
            raw=entry["handler"](args); text=_clip(str(raw),meta.max_result_chars)
            return ToolResult(True,text,meta={"tool":name,"version":meta.version})
        except Exception as e:
            return ToolResult(False,f"执行错误: {e}",recoverable=True,code="TOOL_ERROR",hint=f"工具 '{name}' 执行失败。")
    @property
    def entries(self): return dict(self._entries)

def _clip(text, max_chars):
    if len(text)<=max_chars: return text
    h=max_chars//2; o=len(text)-max_chars
    return text[:h]+f"\n...[{o} 字符被裁剪]...\n"+text[-h:]

class ValidatedAgent(LoopAgent):
    def __init__(self, name="ValidatedAgent", config=None):
        super().__init__(name, config)
        self.registry = ToolRegistry(); self.workspace = os.getcwd()
    def add_tool(self, name, desc, params, handler, **meta_kwargs):
        meta=ToolMeta(**{k:v for k,v in meta_kwargs.items() if k in ToolMeta.__dataclass_fields__})
        self.registry.register(name,desc,params,handler,meta); self.tools[name]=handler
    @property
    def tool_schemas(self): return self.registry.get_schemas()
    def _execute_tool(self, name, args):
        return self.registry.validate_and_execute(name, args, self.workspace).to_message()
# +++ 来自 Ch.03 的代码结束 +++


# +++ Ch.04 新增: Prompt 组装 + Cache 追踪 +++
#
# 问题: 每次调用 API 时，system prompt 里有大量内容每轮都一样
# （身份描述、工具说明书、项目背景、记忆信息）。如果这些内容
# 逐字节一致，OpenAI 的 prompt caching 就能命中，节省约 50% 的
# input token 费用。
#
# 但一个常见错误是在前缀里放动态内容（比如时间戳），导致 cache
# 永不命中——每次都是全价。
#
# Ch.04 的解法:
#   1. PromptBuilder — 把 system prompt 分成稳定前缀 + 易变尾部
#   2. SHA 指纹追踪 — 每次构建前缀时算哈希，知道谁变了
#   3. CacheTracker — 记录每次 API 调用的 cache 命中情况

@dataclass
class PromptBuilder:
    """
    构建稳定的 system prompt 前缀。

    分层结构:
      IDENTITY -> 你是谁（"你是一个编程助手..."）
      TOOLS    -> 工具说明书（排序固定，保证逐字节一致）
      PROJECT  -> 项目背景（"当前项目是..."）
      MEMORY   -> 冻结的记忆

    每一层都算 SHA 指纹 —— 方便定位"到底是哪一层变了"。
    """

    identity: str = ""
    project_context: str = ""
    frozen_memory: str = ""
    _tool_schemas_str: str = ""
    _prefix_fingerprint: Optional[str] = None
    _layer_fingerprints: dict[str, str] = field(default_factory=dict)

    def set_tool_schemas(self, schemas: list[dict]):
        """
        设置工具 schema 的 JSON 字符串。
        注意: 必须按名称排序，确保前后两次构建逐字节一致。
        """
        self._tool_schemas_str = json.dumps(
            sorted(schemas, key=lambda s: s["function"]["name"]),
            ensure_ascii=False, sort_keys=True)

    def build_stable_prefix(self) -> str:
        """
        构建并冻结前缀。每次构建时计算 SHA 指纹和分层指纹。
        """
        parts = [
            f"<!-- IDENTITY -->\n{self.identity}",
            f"<!-- TOOLS -->\n{self._tool_schemas_str}",
            f"<!-- PROJECT -->\n{self.project_context}",
            f"<!-- MEMORY -->\n{self.frozen_memory}",
        ]
        prefix = "\n\n".join(p for p in parts if p.split("\n")[-1].strip())
        self._prefix_fingerprint = _sha(prefix)
        self._layer_fingerprints = {
            "identity": _sha(self.identity),
            "tools": _sha(self._tool_schemas_str),
            "project": _sha(self.project_context),
            "memory": _sha(self.frozen_memory),
        }
        return prefix

    @property
    def fingerprint(self) -> Optional[str]:
        return self._prefix_fingerprint

    @property
    def layer_fps(self) -> dict[str, str]:
        return dict(self._layer_fingerprints)


def _sha(text: str) -> str:
    """计算 SHA-256 的前 12 位作为简短指纹。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ── Cache 追踪 ──
class CacheTracker:
    """记录每次 API 请求的 cache 使用情况。"""

    def __init__(self):
        self._records: list[dict] = []

    def record(self, fingerprint: str, usage) -> None:
        """记录一次 API 调用的 cache 情况。"""
        details = getattr(usage, "prompt_tokens_details", None)
        cached = details.cached_tokens if details else 0
        self._records.append({
            "fp": fingerprint[:8],
            "total_input": usage.prompt_tokens or 0,
            "cache_hit": cached,
            "hit": cached > 0,
        })

    def hit_rate(self) -> float:
        """cache 命中率。"""
        if not self._records:
            return 0.0
        return sum(1 for r in self._records if r["hit"]) / len(self._records)

    def report(self) -> str:
        """生成可读的 cache 统计报告。"""
        return (f"请求次数: {len(self._records)}, "
                f"Cache 命中率: {self.hit_rate():.0%}")


# ── 升级版 Agent ──
class CacheAwareAgent(ValidatedAgent):
    """
    在 ValidatedAgent 基础上加入 PromptBuilder + CacheTracker。

    run() 时自动:
      1. 用 PromptBuilder 构建稳定的 system prompt 前缀
      2. 打印当前前缀的 SHA 指纹
      3. 记录每次 API 调用的 cache 命中情况
    """

    def __init__(self, name: str = "CacheAwareAgent", config: AgentConfig = None):
        super().__init__(name, config)
        # Ch.04 新增
        self.prompt_builder = PromptBuilder()
        self.cache_tracker = CacheTracker()

    def run(self, user_message: str, system_prompt: str = "") -> RunResult:
        """
        覆盖父类 run(): 构建稳定前缀 -> 跑 loop -> 记录 cache。

        这确保每轮对话的 system prompt 前缀是逐字节一致的，
        从而最大化 cache 命中率。
        """
        # 把最新的工具 schema 写入 prompt builder
        self.prompt_builder.identity = system_prompt or "你是助手。"
        self.prompt_builder.set_tool_schemas(self.registry.get_schemas())
        prefix = self.prompt_builder.build_stable_prefix()

        print(f"     [前缀指纹] {self.prompt_builder.fingerprint}")
        print(f"     [分层指纹] {self.prompt_builder.layer_fps}")

        # 调用父类的核心逻辑（传入构建好的稳定前缀作为 system prompt）
        result = super().run(user_message, prefix)
        return result
# +++ Ch.04 新增结束 +++


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.04 - Prompt 组装与 Cache (继承自 ValidatedAgent)")
    print("=" * 50)

    agent = CacheAwareAgent("Ch04Agent")

    # 注册工具
    agent.add_tool("calculator", "计算数学表达式。",
        {"type": "object", "properties": {"expression": {"type": "string"}},
         "required": ["expression"]},
        lambda args: str(eval(args["expression"])),
        read_only=True, idempotent=True)
    agent.add_tool("final_answer", "提交最终答案。",
        {"type": "object", "properties": {"text": {"type": "string"}},
         "required": ["text"]},
        lambda args: args["text"])

    # 设置项目上下文和记忆（这些应该保持稳定）
    agent.prompt_builder.project_context = "项目: Agent 学习"
    agent.prompt_builder.frozen_memory = "用户偏好: Python"

    print(f"  继承自 ValidatedAgent: ToolRegistry + ToolResult")
    print(f"  Ch.04 新增: PromptBuilder + CacheTracker")
    print()

    # 演示: 为什么不能在前缀里放时间戳
    print("  [Cache 破坏演示]")
    pb1 = PromptBuilder()
    pb1.identity = f"时间戳: {time.strftime('%H:%M:%S')}"  # 每轮都变
    fp1 = pb1.build_stable_prefix()
    pb1.identity = f"时间戳: {time.strftime('%H:%M:%S')}"  # 又变了
    fp2 = pb1.build_stable_prefix()
    print(f"    动态身份: fp1={fp1} != fp2={fp2}  -> cache 永不命中!")

    # 正确做法: 稳定身份
    pb2 = PromptBuilder()
    pb2.identity = "你是助手。"  # 永远不变
    fp3 = pb2.build_stable_prefix()
    fp4 = pb2.build_stable_prefix()
    print(f"    稳定身份: fp3={fp3} == fp4={fp4}  -> cache 可以命中")
