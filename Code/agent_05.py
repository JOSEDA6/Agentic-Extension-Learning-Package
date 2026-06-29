#!/usr/bin/env python3
"""
agent_05.py —— 短期记忆 (Short-term Memory)
对应课程: Ch.05 — Short-term Memory

这个文件是完全独立的——不依赖任何本地 .py 文件。
它完整复制了前四章的地基代码，然后加上 Ch.05 的新内容。

可以单独运行: python agent_05.py
"""

# ============================================================
# 地基代码（来自 Ch.00 ~ Ch.04，完整复制以确保独立运行）
# ============================================================
import json
import os
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from openai import OpenAI


@dataclass
class AgentConfig:
    """Agent 配置。"""
    model: str = "gpt-4o-mini"
    max_steps: int = 10
    token_budget: int = 8000
    api_key: str = "YOUR_API_KEY_HERE"
    base_url: str = "https://api.openai.com/v1"


class BaseAgent:
    """所有 Agent 的基类。"""
    def __init__(self, name: str = "Agent", config: Optional[AgentConfig] = None):
        self.name = name
        self.config = config or AgentConfig()
        self.tools: dict[str, callable] = {}
        self.history: list[dict] = []

    def register_tool(self, name: str, handler: callable):
        self.tools[name] = handler

    def __repr__(self):
        return (f"<{self.__class__.__name__}('{self.name}': "
                f"tools={list(self.tools.keys())}, history={len(self.history)} msgs)>")


class ToolCallingAgent(BaseAgent):
    """带工具调用能力的 Agent。"""
    def __init__(self, name: str = "ToolCallingAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        self._tool_schemas: list[dict] = []

    def add_tool(self, name: str, description: str, parameters: dict, handler: callable):
        self.tools[name] = handler
        self._tool_schemas.append({
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        })

    @property
    def tool_schemas(self) -> list[dict]:
        return self._tool_schemas

    def _execute_tool(self, name: str, args: dict) -> str:
        handler = self.tools.get(name)
        if not handler:
            return f"未知工具: {name}"
        try:
            return str(handler(args))
        except Exception as e:
            return f"工具执行错误: {e}"

    def one_shot(self, user_message: str, system_prompt: str = "") -> str:
        messages = ([{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_message}]
                    if system_prompt else [{"role": "user", "content": user_message}])
        response = self.client.chat.completions.create(
            model=self.config.model, messages=messages, tools=self.tool_schemas or None)
        msg = response.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""
        messages.append(msg)
        for tc in msg.tool_calls:
            name, args = tc.function.name, json.loads(tc.function.arguments)
            result = self._execute_tool(name, args)
            print(f"     [工具调用] {name}({args}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        r2 = self.client.chat.completions.create(model=self.config.model, messages=messages)
        return r2.choices[0].message.content or ""


@dataclass
class RunResult:
    """Agent 运行结果。"""
    answer: str = ""
    steps: int = 0
    total_tokens: int = 0
    stop_reason: str = ""
    tool_calls_made: list[dict] = field(default_factory=list)


class LoopAgent(ToolCallingAgent):
    """带循环的 Agent。"""
    def __init__(self, name: str = "LoopAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self._recent_calls: list[tuple[str, str]] = []
        self._doom_threshold = 3

    def _check_doom_loop(self, tool_name: str, args: dict) -> bool:
        key = json.dumps(args, sort_keys=True)
        self._recent_calls.append((tool_name, key))
        if len(self._recent_calls) > self._doom_threshold:
            self._recent_calls.pop(0)
        if len(self._recent_calls) >= self._doom_threshold:
            if all(n == tool_name and a == key for n, a in self._recent_calls):
                return True
        return False

    def run(self, user_message: str, system_prompt: str = "") -> RunResult:
        result = RunResult()
        messages = ([{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_message}]
                    if system_prompt else [{"role": "user", "content": user_message}])
        for step in range(1, self.config.max_steps + 1):
            response = self.client.chat.completions.create(
                model=self.config.model, messages=messages, tools=self.tool_schemas or None)
            msg = response.choices[0].message
            result.total_tokens += (response.usage.total_tokens if response.usage else 0)
            result.steps = step
            if not msg.tool_calls:
                result.answer = msg.content or ""
                result.stop_reason = f"model_driven({response.choices[0].finish_reason})"
                return result
            messages.append(msg)
            for tc in msg.tool_calls:
                name, args = tc.function.name, json.loads(tc.function.arguments)
                tool_result = (f"[死循环] '{name}' 连续 {self._doom_threshold} 次相同参数"
                               if self._check_doom_loop(name, args)
                               else self._execute_tool(name, args))
                print(f"     [Step {step}] {name}({args}) -> {str(tool_result)[:60]}")
                result.tool_calls_made.append({
                    "step": step, "tool": name, "args": args,
                    "result": str(tool_result)[:200],
                })
                if name == "final_answer":
                    result.answer = str(tool_result)
                    result.stop_reason = "final_answer_tool"
                    return result
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(tool_result)})
            if result.total_tokens >= self.config.token_budget:
                print("     [警告] Token 预算耗尽，发 grace call")
                messages.append({"role": "user",
                    "content": "token 预算已耗尽。请立即用 final_answer 提交最终答案。"})
        result.answer = "[达到步数上限]"
        result.stop_reason = "step_cap"
        return result


@dataclass
class ToolResult:
    """工具返回的错误信封。"""
    ok: bool
    content: str = ""
    recoverable: bool = True
    code: str = ""
    hint: str = ""
    meta: dict = field(default_factory=dict)

    def to_message(self) -> str:
        if self.ok:
            return self.content
        msg = f"[{self.code}] {self.content}"
        if self.hint:
            msg += f"\n提示: {self.hint}"
        return msg


@dataclass
class ToolMeta:
    """工具元数据（模型看不到）。"""
    read_only: bool = False
    destructive: bool = False
    concurrency_safe: bool = True
    idempotent: bool = False
    open_world: bool = False
    max_result_chars: int = 2000
    timeout: int = 30
    version: int = 1


def _clip_result(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - max_chars
    return text[:half] + f"\n...[{omitted} 字符被裁剪]...\n" + text[-half:]


class ToolRegistry:
    """工具注册表，含五阶段校验流水线。"""
    def __init__(self):
        self._entries: dict[str, dict] = {}

    def register(self, name: str, description: str, parameters: dict,
                 handler: callable, meta: ToolMeta = None):
        self._entries[name] = {
            "schema": {
                "type": "function",
                "function": {"name": name, "description": description, "parameters": parameters},
            },
            "meta": meta or ToolMeta(),
            "handler": handler,
        }

    def get_schemas(self) -> list[dict]:
        return [e["schema"] for e in self._entries.values()]

    def get_meta(self, name: str) -> Optional[ToolMeta]:
        entry = self._entries.get(name)
        return entry["meta"] if entry else None

    def is_known(self, name: str) -> bool:
        return name in self._entries

    def validate_and_execute(self, name: str, args: dict, workspace: str = ".") -> ToolResult:
        if not self.is_known(name):
            return ToolResult(False, f"未知工具: {name}", recoverable=False,
                              code="UNKNOWN_TOOL", hint=f"可用: {list(self._entries.keys())}")
        entry = self._entries[name]
        meta = entry["meta"]
        if "path" in args:
            path = str(args["path"])
            dangerous = ["/etc/", "~/.ssh", ".env", "C:\\Windows"]
            if any(d in path for d in dangerous):
                return ToolResult(False, f"路径不安全: {path}", recoverable=True,
                                  code="UNSAFE_PATH", hint="请使用工作目录内的路径。")
        if meta.destructive:
            print(f"     [权限检查] 破坏性操作: {name}({args})")
        try:
            raw = entry["handler"](args)
            text = _clip_result(str(raw), meta.max_result_chars)
            return ToolResult(True, text, meta={"tool": name, "version": meta.version})
        except Exception as e:
            return ToolResult(False, f"执行错误: {e}", recoverable=True,
                              code="TOOL_ERROR", hint=f"工具 '{name}' 执行失败。")

    @property
    def entries(self) -> dict:
        return dict(self._entries)


class ValidatedAgent(LoopAgent):
    """使用 ToolRegistry 的 Agent。"""
    def __init__(self, name: str = "ValidatedAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.registry = ToolRegistry()
        self.workspace = os.getcwd()

    def add_tool(self, name: str, description: str, parameters: dict,
                 handler: callable, **meta_kwargs):
        meta = ToolMeta(**{k: v for k, v in meta_kwargs.items()
                           if k in ToolMeta.__dataclass_fields__})
        self.registry.register(name, description, parameters, handler, meta)
        self.tools[name] = handler

    @property
    def tool_schemas(self):
        return self.registry.get_schemas()

    def _execute_tool(self, name: str, args: dict) -> str:
        return self.registry.validate_and_execute(name, args, self.workspace).to_message()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class PromptBuilder:
    """构建稳定的 system prompt 前缀。"""
    identity: str = ""
    project_context: str = ""
    frozen_memory: str = ""
    _tool_schemas_str: str = ""
    _prefix_fingerprint: Optional[str] = None
    _layer_fingerprints: dict[str, str] = field(default_factory=dict)

    def set_tool_schemas(self, schemas: list[dict]):
        self._tool_schemas_str = json.dumps(
            sorted(schemas, key=lambda s: s["function"]["name"]),
            ensure_ascii=False, sort_keys=True)

    def build_stable_prefix(self) -> str:
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


class CacheTracker:
    """记录 API 调用的 cache 命中情况。"""
    def __init__(self):
        self._records: list[dict] = []

    def record(self, fingerprint: str, usage) -> None:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = details.cached_tokens if details else 0
        self._records.append({
            "fp": fingerprint[:8],
            "total_input": usage.prompt_tokens or 0,
            "cache_hit": cached,
            "hit": cached > 0,
        })

    def hit_rate(self) -> float:
        if not self._records:
            return 0.0
        return sum(1 for r in self._records if r["hit"]) / len(self._records)

    def report(self) -> str:
        return f"请求次数: {len(self._records)}, Cache 命中率: {self.hit_rate():.0%}"


class CacheAwareAgent(ValidatedAgent):
    """带 cache 意识的 Agent。"""
    def __init__(self, name: str = "CacheAwareAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.prompt_builder = PromptBuilder()
        self.cache_tracker = CacheTracker()

    def run(self, user_message: str, system_prompt: str = "") -> RunResult:
        self.prompt_builder.identity = system_prompt or "你是助手。"
        self.prompt_builder.set_tool_schemas(self.registry.get_schemas())
        prefix = self.prompt_builder.build_stable_prefix()
        print(f"     [前缀指纹] {self.prompt_builder.fingerprint}")
        print(f"     [分层指纹] {self.prompt_builder.layer_fps}")
        return super().run(user_message, prefix)
# ============================================================
# 地基代码结束
# ============================================================


# +++ Ch.05 新增: 短期记忆 +++
#
# 前四章的 history 列表只有一个「全部显示」模式——对话一长就浪费 token。
# Ch.05 把记忆分成三个视图:
#   - audit_log: 审计日志（完整保留，永不可删）
#   - operating_transcript: 给模型看的精简版（裁剪/去重/压缩）
#   - working_memory: 当前任务草稿区

@dataclass
class TranscriptMessage:
    """审计日志中的一条消息。"""
    role: str
    content: str
    tool_name: str = ""
    tool_input: str = ""
    timestamp: float = 0.0


@dataclass
class WorkingMemory:
    """当前任务的草稿区。结束后重置。"""
    goal: str = ""
    plan: str = ""
    files_read: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ShortTermMemory:
    """
    三视图记忆管理:
      audit_log           — 完整日志（审计用）
      operating_transcript — 精简后发给模型
      working_memory       — 草稿区
    """

    def __init__(self):
        self.audit_log: list[TranscriptMessage] = []
        self.operating_transcript: list[dict] = []
        self.working_memory = WorkingMemory()
        self._disposal_policy: dict[str, str] = {}
        self._stats = {"added": 0, "clipped": 0, "deduped": 0, "compacted": 0}

    def set_disposal(self, tool_name: str, policy: str):
        """设置工具输出处理策略: clip / dedupe / compact。"""
        self._disposal_policy[tool_name] = policy

    def add(self, role: str, content: str, tool_name: str = "", tool_input: str = ""):
        """添加消息到所有视图。"""
        self.audit_log.append(TranscriptMessage(
            role=role, content=content, tool_name=tool_name,
            tool_input=tool_input, timestamp=time.time()))
        self._stats["added"] += 1

        policy = self._disposal_policy.get(tool_name, "")
        if policy == "clip":
            content_processed = content[:500]
            self._stats["clipped"] += 1
        elif policy == "dedupe":
            self.operating_transcript = _dedupe_latest(
                self.operating_transcript, tool_name, tool_input)
            content_processed = content
            self._stats["deduped"] += 1
        elif policy == "compact":
            content_processed = _asym_compact(content, head=200, tail=100)
            self._stats["compacted"] += 1
        else:
            content_processed = content

        self.operating_transcript.append({"role": role, "content": content_processed})

    def build_for_model(self) -> list[dict]:
        return list(self.operating_transcript)

    @property
    def stats(self) -> dict:
        return dict(self._stats)


def _dedupe_latest(transcript: list[dict], tool_name: str, tool_input: str) -> list[dict]:
    """同名同参只保留最后一条。"""
    for i in range(len(transcript) - 1, -1, -1):
        content = transcript[i].get("content", "")
        if tool_name in content and tool_input[:20] in content:
            transcript.pop(i)
            break
    return transcript


def _asym_compact(text: str, head: int = 200, tail: int = 100) -> str:
    """非对称压缩: 保头尾，压中间。"""
    if len(text) <= head + tail + 50:
        return text
    omitted = len(text) - head - tail
    return text[:head] + f"\n...[{omitted} 字符压缩]...\n" + text[-tail:]


class MemoryAgent(CacheAwareAgent):
    """带三视图短期记忆的 Agent。"""
    def __init__(self, name: str = "MemoryAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.stm = ShortTermMemory()

    def run(self, user_message: str, system_prompt: str = "") -> RunResult:
        self.stm.add("user", user_message)
        result = super().run(user_message, system_prompt)
        self.stm.add("assistant", result.answer)
        return result


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.05 - 短期记忆 (继承自 CacheAwareAgent)")
    print("=" * 50)

    agent = MemoryAgent("Ch05Agent")
    agent.add_tool("calculator", "计算数学表达式。",
        {"type": "object", "properties": {"expression": {"type": "string"}},
         "required": ["expression"]},
        lambda a: str(eval(a["expression"])), read_only=True, idempotent=True)
    agent.add_tool("final_answer", "提交最终答案。",
        {"type": "object", "properties": {"text": {"type": "string"}},
         "required": ["text"]},
        lambda a: a["text"])

    # 演示三视图
    agent.stm.add("user", "15 * 23 等于多少？")
    agent.stm.add("assistant", "让我计算一下。")
    agent.stm.add("tool", "345", tool_name="calculator", tool_input='{"expression":"15*23"}')

    print(f"  审计日志: {len(agent.stm.audit_log)} 条")
    print(f"  运行副本: {len(agent.stm.operating_transcript)} 条")
    print(f"  工作记忆: goal='{agent.stm.working_memory.goal}'")
    print(f"  处理统计: {agent.stm.stats}")
    print()
    print("  [提示] run() 需要 API Key。上面演示了 ShortTermMemory 三视图。")
