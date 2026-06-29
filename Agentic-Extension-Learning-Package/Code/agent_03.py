#!/usr/bin/env python3
"""
agent_03.py —— 工具契约与校验 (Tools the agent can trust)
对应课程: Ch.03 — Tools the agent can trust

这个文件是完全独立的——不依赖任何本地 .py 文件。
它完整复制了前三章的代码，然后加上 Ch.03 的新内容。

你可以单独运行:
  python agent_03.py

新学什么:
  - ToolResult: 工具返回的「错误信封」（ok / 错误码 / 提示）
  - ToolMeta: 工具的元数据（只读/破坏性/幂等...）
  - ToolRegistry: 带五阶段校验流水线的工具注册表
  - ValidatedAgent: 使用 ToolRegistry 代替原始 dict
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


# +++ Ch.03 新增: 工具契约与校验 +++
#
# 前两章的工具调用太"天真"了——没有任何校验。
# 如果模型说"删掉 /etc/passwd"，Agent 会真的去删。
# 如果工具返回 10MB 数据，Agent 会直接塞回对话。
# 如果工具报错了，模型也看不懂。
#
# Ch.03 引入三样东西来解决这些问题:
#   1. ToolResult (错误信封) — 工具返回给模型的是结构化的结果
#   2. ToolMeta (工具元数据) — 这个工具是只读的？破坏性的？幂等的？
#   3. ToolRegistry (注册表) — 五阶段校验流水线

import os
import hashlib


# ── 1. 错误信封 ──
@dataclass
class ToolResult:
    """
    每个工具返回一个「信封」，模型据此决定下一步。

    ok=True  → 工具执行成功，content 里有结果
    ok=False → 工具执行失败，code 说明原因，hint 告诉模型怎么补救
    """
    ok: bool                        # 成功还是失败？
    content: str = ""               # 结果内容
    recoverable: bool = True        # 模型能从错误中恢复吗？
    code: str = ""                  # 错误码（如 UNKNOWN_TOOL, UNSAFE_PATH）
    hint: str = ""                  # 给模型的下一步提示
    meta: dict = field(default_factory=dict)

    def to_message(self) -> str:
        """把信封转成发给模型的文本。"""
        if self.ok:
            return self.content
        msg = f"[{self.code}] {self.content}"
        if self.hint:
            msg += f"\n提示: {self.hint}"
        return msg


# ── 2. 工具元数据 ──
@dataclass
class ToolMeta:
    """
    工具的「身份证」。模型看不到这些——只有 Agent 代码读。
    loop 根据这些标志位决定怎么处理工具调用。
    """
    read_only: bool = False          # 只读工具（如搜索）？
    destructive: bool = False        # 破坏性工具（如删除文件）？
    concurrency_safe: bool = True    # 可并发执行？
    idempotent: bool = False         # 多次调用结果一样？
    open_world: bool = False         # 访问外部网络？
    max_result_chars: int = 2000     # 结果最大字符数
    timeout: int = 30                # 超时秒数
    version: int = 1                 # 工具版本


# ── 3. 工具注册表 ──
class ToolRegistry:
    """
    Ch.03 核心: 每个工具有三份信息。
      - schema:  模型看到的"说明书"（来自 Ch.01）
      - meta:    loop 读的标志位（Ch.03 新增）
      - handler: 真正干活的函数

    校验流水线五阶段:
      Known? -> Type check -> Semantic safety -> Permission -> Execute
    """

    def __init__(self):
        self._entries: dict[str, dict] = {}

    def register(self, name: str, description: str, parameters: dict,
                 handler: callable, meta: ToolMeta = None):
        """注册一个工具: 说明书 + 元数据 + 实现。"""
        self._entries[name] = {
            "schema": {
                "type": "function",
                "function": {"name": name, "description": description,
                             "parameters": parameters},
            },
            "meta": meta or ToolMeta(),
            "handler": handler,
        }

    def get_schemas(self) -> list[dict]:
        """返回所有工具的 schema（发给模型用的）。"""
        return [e["schema"] for e in self._entries.values()]

    def get_meta(self, name: str) -> Optional[ToolMeta]:
        """查询工具的元数据。"""
        entry = self._entries.get(name)
        return entry["meta"] if entry else None

    def is_known(self, name: str) -> bool:
        """这个工具注册过吗？"""
        return name in self._entries

    def validate_and_execute(self, name: str, args: dict,
                              workspace: str = ".") -> ToolResult:
        """
        Ch.03 五阶段校验流水线（便宜的检查先跑）:

        ① 检查工具是否存在 (Known?)
        ② [省略通用类型检查]
        ③ 语义安全检查（路径安全等）
        ④ 权限检查（破坏性操作打警告）
        ⑤ 执行工具
        """
        # 阶段 ①: 工具存在吗？
        if not self.is_known(name):
            return ToolResult(False, f"未知工具: {name}",
                              recoverable=False, code="UNKNOWN_TOOL",
                              hint=f"可用工具: {list(self._entries.keys())}")

        entry = self._entries[name]
        meta = entry["meta"]

        # 阶段 ③: 语义安全检查
        if "path" in args:
            path = str(args["path"])
            dangerous = ["/etc/", "~/.ssh", ".env", "C:\\Windows"]
            if any(d in path for d in dangerous):
                return ToolResult(False, f"路径不安全: {path}",
                                  recoverable=True, code="UNSAFE_PATH",
                                  hint="请使用工作目录内的路径。")

        # 阶段 ④: 权限检查
        if meta.destructive:
            print(f"     [权限检查] 破坏性操作: {name}({args})")

        # 阶段 ⑤: 执行
        try:
            raw = entry["handler"](args)
            result_text = _clip_result(str(raw), meta.max_result_chars)
            return ToolResult(True, result_text,
                              meta={"tool": name, "version": meta.version})
        except Exception as e:
            return ToolResult(False, f"执行错误: {e}",
                              recoverable=True, code="TOOL_ERROR",
                              hint=f"工具 '{name}' 执行失败，请检查参数或换方法。")

    @property
    def entries(self):
        """调试用: 查看所有注册的工具。"""
        return dict(self._entries)


def _clip_result(text: str, max_chars: int) -> str:
    """裁剪过长的工具输出，防止撑爆对话。"""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - max_chars
    return (text[:half] +
            f"\n...[{omitted} 字符被裁剪]...\n" +
            text[-half:])


# ── 4. 升级版 Agent ──
class ValidatedAgent(LoopAgent):
    """
    在 LoopAgent 基础上:
      - 用 ToolRegistry 替代原始的 self.tools / self._tool_schemas
      - _execute_tool() 走完整五阶段校验流水线
    """

    def __init__(self, name: str = "ValidatedAgent", config: AgentConfig = None):
        super().__init__(name, config)
        # Ch.03 新增: 使用 ToolRegistry
        self.registry = ToolRegistry()
        self.workspace = os.getcwd()

    def add_tool(self, name: str, description: str, parameters: dict,
                 handler: callable, **meta_kwargs):
        """
        Ch.03: 注册工具时同时传入元数据。

        例如: add_tool("delete_file", ..., destructive=True, concurrency_safe=False)
        """
        meta = ToolMeta(**{k: v for k, v in meta_kwargs.items()
                           if k in ToolMeta.__dataclass_fields__})
        self.registry.register(name, description, parameters, handler, meta)
        # 兼容父类（虽然父类的 tools 在 Ch.03 不再直接使用）
        self.tools[name] = handler

    @property
    def tool_schemas(self):
        """覆盖父类的 tool_schemas——现在从 registry 获取。"""
        return self.registry.get_schemas()

    def _execute_tool(self, name: str, args: dict) -> str:
        """Ch.03: 走完整校验流水线。"""
        result = self.registry.validate_and_execute(name, args, self.workspace)
        return result.to_message()
# +++ Ch.03 新增结束 +++


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.03 - 工具契约与校验 (继承自 LoopAgent)")
    print("=" * 50)

    agent = ValidatedAgent("Ch03Agent")

    # 注册计算器（只读、幂等）
    agent.add_tool("calculator",
        "计算数学表达式。用于精确数值计算。",
        {"type": "object", "properties": {"expression": {"type": "string"}},
         "required": ["expression"]},
        lambda args: str(eval(args["expression"])),
        read_only=True, concurrency_safe=True, idempotent=True)

    # 注册删除文件（破坏性、不可并发）
    agent.add_tool("delete_file",
        "删除指定文件。不可逆！",
        {"type": "object", "properties": {"path": {"type": "string"}},
         "required": ["path"]},
        lambda args: f"已删除 {args['path']}",
        read_only=False, destructive=True, concurrency_safe=False)

    # 注册 final_answer
    agent.add_tool("final_answer", "提交最终答案。",
        {"type": "object", "properties": {"text": {"type": "string"}},
         "required": ["text"]},
        lambda args: args["text"])

    # 展示工具元数据
    print(f"  继承自 LoopAgent: run_loop + 停止条件")
    print(f"  Ch.03 新增: ToolRegistry + ToolResult + ToolMeta")
    for name in sorted(agent.registry.entries):
        meta = agent.registry.get_meta(name)
        flags = [f for f in ["read_only","destructive","idempotent"]
                 if getattr(meta, f)]
        print(f"    {name}: {flags}")

    # 演示校验流水线
    print()
    print("  [校验演示]")
    r1 = agent.registry.validate_and_execute("delete_file", {"path": "/etc/passwd"})
    print(f"    危险路径 -> {r1.code}: {r1.content[:60]}")
    r2 = agent.registry.validate_and_execute("calculator", {"expression": "1+1"})
    print(f"    正常调用 -> ok={r2.ok}: {r2.content}")
    r3 = agent.registry.validate_and_execute("unknown_tool", {})
    print(f"    未知工具 -> {r3.code}: {r3.content}")
