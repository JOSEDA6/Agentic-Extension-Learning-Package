#!/usr/bin/env python3
"""
agent_06.py —— 长期记忆检索 (Long-term Recall)
对应课程: Ch.06 — Long-term Recall

完全独立，不依赖本地 .py 文件。
python agent_06.py
"""

# ============================================================
# 地基代码（来自 Ch.00 ~ Ch.05，完整复制以确保独立运行）
# ============================================================
import json, os, time, hashlib, math
from dataclasses import dataclass, field
from typing import Optional
from openai import OpenAI

@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"; max_steps: int = 10; token_budget: int = 8000
    api_key: str = "YOUR_API_KEY_HERE"; base_url: str = "https://api.openai.com/v1"

class BaseAgent:
    def __init__(self, name="Agent", config=None):
        self.name = name; self.config = config or AgentConfig()
        self.tools: dict[str, callable] = {}; self.history: list[dict] = []
    def register_tool(self, name, handler): self.tools[name] = handler
    def __repr__(self):
        return f"<{self.__class__.__name__}('{self.name}': tools={list(self.tools.keys())}, history={len(self.history)} msgs)>"

class ToolCallingAgent(BaseAgent):
    def __init__(self, name="ToolCallingAgent", config=None):
        super().__init__(name, config)
        self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        self._tool_schemas: list[dict] = []
    def add_tool(self, name, desc, params, handler):
        self.tools[name] = handler
        self._tool_schemas.append({"type":"function","function":{"name":name,"description":desc,"parameters":params}})
    @property
    def tool_schemas(self): return self._tool_schemas
    def _execute_tool(self, name, args):
        h = self.tools.get(name)
        if not h: return f"未知工具: {name}"
        try: return str(h(args))
        except Exception as e: return f"工具执行错误: {e}"
    def one_shot(self, um, sp=""):
        m=[{"role":"system","content":sp},{"role":"user","content":um}] if sp else [{"role":"user","content":um}]
        r=self.client.chat.completions.create(model=self.config.model,messages=m,tools=self.tool_schemas or None)
        msg=r.choices[0].message
        if not msg.tool_calls: return msg.content or ""
        m.append(msg)
        for tc in msg.tool_calls:
            n,a=tc.function.name,json.loads(tc.function.arguments); res=self._execute_tool(n,a)
            print(f"     [工具调用] {n}({a}) -> {res}"); m.append({"role":"tool","tool_call_id":tc.id,"content":res})
        r2=self.client.chat.completions.create(model=self.config.model,messages=m); return r2.choices[0].message.content or ""

@dataclass
class RunResult:
    answer: str = ""; steps: int = 0; total_tokens: int = 0
    stop_reason: str = ""; tool_calls_made: list[dict] = field(default_factory=list)

class LoopAgent(ToolCallingAgent):
    def __init__(self, name="LoopAgent", config=None):
        super().__init__(name, config); self._recent_calls=[]; self._doom_threshold=3
    def _check_doom_loop(self, name, args):
        key=json.dumps(args,sort_keys=True); self._recent_calls.append((name,key))
        if len(self._recent_calls)>self._doom_threshold: self._recent_calls.pop(0)
        if len(self._recent_calls)>=self._doom_threshold:
            if all(n==name and a==key for n,a in self._recent_calls): return True
        return False
    def run(self, um, sp=""):
        result=RunResult()
        m=[{"role":"system","content":sp},{"role":"user","content":um}] if sp else [{"role":"user","content":um}]
        for step in range(1,self.config.max_steps+1):
            resp=self.client.chat.completions.create(model=self.config.model,messages=m,tools=self.tool_schemas or None)
            msg=resp.choices[0].message; result.total_tokens+=(resp.usage.total_tokens if resp.usage else 0); result.steps=step
            if not msg.tool_calls: result.answer=msg.content or ""; result.stop_reason=f"model_driven({resp.choices[0].finish_reason})"; return result
            m.append(msg)
            for tc in msg.tool_calls:
                n,a=tc.function.name,json.loads(tc.function.arguments)
                tr=(f"[死循环] '{n}'连续{self._doom_threshold}次相同参数" if self._check_doom_loop(n,a) else self._execute_tool(n,a))
                print(f"     [Step{step}] {n}({a}) -> {str(tr)[:60]}")
                result.tool_calls_made.append({"step":step,"tool":n,"args":a,"result":str(tr)[:200]})
                if n=="final_answer": result.answer=str(tr); result.stop_reason="final_answer_tool"; return result
                m.append({"role":"tool","tool_call_id":tc.id,"content":str(tr)})
            if result.total_tokens>=self.config.token_budget:
                print("     [警告] Token预算耗尽，发grace call")
                m.append({"role":"user","content":"token预算已耗尽。请立即用final_answer提交最终答案。"})
        result.answer="[达到步数上限]"; result.stop_reason="step_cap"; return result

@dataclass
class ToolResult:
    ok:bool; content:str=""; recoverable:bool=True; code:str=""; hint:str=""; meta:dict=field(default_factory=dict)
    def to_message(self):
        if self.ok: return self.content
        msg=f"[{self.code}] {self.content}"
        if self.hint: msg+=f"\n提示: {self.hint}"
        return msg

@dataclass
class ToolMeta:
    read_only:bool=False; destructive:bool=False; concurrency_safe:bool=True; idempotent:bool=False
    open_world:bool=False; max_result_chars:int=2000; timeout:int=30; version:int=1

def _clip_result(t,m):
    if len(t)<=m: return t
    h=m//2; o=len(t)-m; return t[:h]+f"\n...[{o}字符被裁剪]...\n"+t[-h:]

class ToolRegistry:
    def __init__(self): self._entries:dict[str,dict]={}
    def register(self,n,d,p,h,meta=None): self._entries[n]={"schema":{"type":"function","function":{"name":n,"description":d,"parameters":p}},"meta":meta or ToolMeta(),"handler":h}
    def get_schemas(self): return [e["schema"] for e in self._entries.values()]
    def get_meta(self,n): e=self._entries.get(n); return e["meta"] if e else None
    def is_known(self,n): return n in self._entries
    def validate_and_execute(self,n,a,ws="."):
        if not self.is_known(n): return ToolResult(False,f"未知工具: {n}",recoverable=False,code="UNKNOWN_TOOL",hint=f"可用: {list(self._entries.keys())}")
        e=self._entries[n]; m=e["meta"]
        if "path" in a:
            p=str(a["path"]); d=["/etc/","~/.ssh",".env","C:\\Windows"]
            if any(x in p for x in d): return ToolResult(False,f"路径不安全: {p}",recoverable=True,code="UNSAFE_PATH",hint="请使用工作目录内的路径。")
        if m.destructive: print(f"     [权限检查] 破坏性操作: {n}({a})")
        try: raw=e["handler"](a); text=_clip_result(str(raw),m.max_result_chars); return ToolResult(True,text,meta={"tool":n,"version":m.version})
        except Exception as ex: return ToolResult(False,f"执行错误: {ex}",recoverable=True,code="TOOL_ERROR",hint=f"工具'{n}'执行失败。")
    @property
    def entries(self): return dict(self._entries)

class ValidatedAgent(LoopAgent):
    def __init__(self,n="ValidatedAgent",c=None): super().__init__(n,c); self.registry=ToolRegistry(); self.workspace=os.getcwd()
    def add_tool(self,n,d,p,h,**mk):
        meta=ToolMeta(**{k:v for k,v in mk.items() if k in ToolMeta.__dataclass_fields__}); self.registry.register(n,d,p,h,meta); self.tools[n]=h
    @property
    def tool_schemas(self): return self.registry.get_schemas()
    def _execute_tool(self,n,a): return self.registry.validate_and_execute(n,a,self.workspace).to_message()

def _sha(text): return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

@dataclass
class PromptBuilder:
    identity:str=""; project_context:str=""; frozen_memory:str=""; _tool_schemas_str:str=""; _prefix_fingerprint:Optional[str]=None; _layer_fingerprints:dict[str,str]=field(default_factory=dict)
    def set_tool_schemas(self,sc): self._tool_schemas_str=json.dumps(sorted(sc,key=lambda s:s["function"]["name"]),ensure_ascii=False,sort_keys=True)
    def build_stable_prefix(self):
        parts=[f"<!-- IDENTITY -->\n{self.identity}",f"<!-- TOOLS -->\n{self._tool_schemas_str}",f"<!-- PROJECT -->\n{self.project_context}",f"<!-- MEMORY -->\n{self.frozen_memory}"]
        prefix="\n\n".join(p for p in parts if p.split("\n")[-1].strip())
        self._prefix_fingerprint=_sha(prefix); self._layer_fingerprints={"identity":_sha(self.identity),"tools":_sha(self._tool_schemas_str),"project":_sha(self.project_context),"memory":_sha(self.frozen_memory)}
        return prefix
    @property
    def fingerprint(self): return self._prefix_fingerprint
    @property
    def layer_fps(self): return dict(self._layer_fingerprints)

class CacheTracker:
    def __init__(self): self._records=[]
    def record(self,fp,usage):
        d=getattr(usage,"prompt_tokens_details",None); c=d.cached_tokens if d else 0
        self._records.append({"fp":fp[:8],"total_input":usage.prompt_tokens or 0,"cache_hit":c,"hit":c>0})
    def hit_rate(self): return sum(1 for r in self._records if r["hit"])/len(self._records) if self._records else 0.0
    def report(self): return f"请求次数: {len(self._records)}, Cache命中率: {self.hit_rate():.0%}"

class CacheAwareAgent(ValidatedAgent):
    def __init__(self,n="CacheAwareAgent",c=None): super().__init__(n,c); self.prompt_builder=PromptBuilder(); self.cache_tracker=CacheTracker()
    def run(self,um,sp=""):
        self.prompt_builder.identity=sp or "你是助手。"; self.prompt_builder.set_tool_schemas(self.registry.get_schemas()); prefix=self.prompt_builder.build_stable_prefix()
        print(f"     [前缀指纹] {self.prompt_builder.fingerprint}"); print(f"     [分层指纹] {self.prompt_builder.layer_fps}")
        return super().run(um,prefix)

@dataclass
class TranscriptMessage:
    role:str; content:str; tool_name:str=""; tool_input:str=""; timestamp:float=0.0

@dataclass
class WorkingMemory:
    goal:str=""; plan:str=""; files_read:list[str]=field(default_factory=list); notes:list[str]=field(default_factory=list)

class ShortTermMemory:
    def __init__(self):
        self.audit_log=[]; self.operating_transcript=[]; self.working_memory=WorkingMemory()
        self._disposal_policy={}; self._stats={"added":0,"clipped":0,"deduped":0,"compacted":0}
    def set_disposal(self,n,p): self._disposal_policy[n]=p
    def add(self,role,content,tool_name="",tool_input=""):
        self.audit_log.append(TranscriptMessage(role=role,content=content,tool_name=tool_name,tool_input=tool_input,timestamp=time.time()))
        self._stats["added"]+=1; policy=self._disposal_policy.get(tool_name,"")
        if policy=="clip": cp=content[:500]; self._stats["clipped"]+=1
        elif policy=="dedupe": self.operating_transcript=_dedupe_latest(self.operating_transcript,tool_name,tool_input); cp=content; self._stats["deduped"]+=1
        elif policy=="compact": cp=_asym_compact(content,200,100); self._stats["compacted"]+=1
        else: cp=content
        self.operating_transcript.append({"role":role,"content":cp})
    def build_for_model(self): return list(self.operating_transcript)
    @property
    def stats(self): return dict(self._stats)

def _dedupe_latest(t,n,i):
    for x in range(len(t)-1,-1,-1):
        if n in t[x].get("content","") and i[:20] in t[x].get("content",""): t.pop(x); break
    return t

def _asym_compact(t,h=200,tl=100):
    if len(t)<=h+tl+50: return t
    o=len(t)-h-tl; return t[:h]+f"\n...[{o}字符压缩]...\n"+t[-tl:]

class MemoryAgent(CacheAwareAgent):
    def __init__(self,n="MemoryAgent",c=None): super().__init__(n,c); self.stm=ShortTermMemory()
    def run(self,um,sp=""):
        self.stm.add("user",um); result=super().run(um,sp); self.stm.add("assistant",result.answer); return result
# ============================================================
# 地基代码结束
# ============================================================


# +++ Ch.06 新增: 长期检索 +++
#
# Ch.05 的短期记忆只处理当前任务的记忆。
# 但 Agent 还需要从更早的对话或知识库中检索信息。
#
# Ch.06 引入:
#   - FullTextRetriever: 精确词匹配（适合 ID/代码/文件名）
#   - VectorRetriever:   简化的语义检索（TF-IDF + 余弦相似度）
#   - RRF: Reciprocal Rank Fusion（融合多个排序结果）
#   - Skill + SkillIndex: 渐进式披露的技能索引

@dataclass
class RetrievalResult:
    """检索结果的一条记录。"""
    id: str
    text: str
    score: float


class FullTextRetriever:
    """
    精确词匹配检索器。
    适合: ID、代码、文件名、版本号——需要精确匹配的场景。
    """

    def __init__(self):
        self.docs: dict[str, str] = {}

    def index(self, doc_id: str, text: str):
        self.docs[doc_id] = text

    def search(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        """精确子串匹配，返回前 top_k 个结果。"""
        results = []
        query_lower = query.lower()
        for doc_id, text in self.docs.items():
            if query_lower in text.lower():
                # 匹配度: 匹配位置越靠前得分越高
                pos = text.lower().index(query_lower)
                score = 1.0 / (1.0 + pos / len(text))
                results.append(RetrievalResult(doc_id, text[:200], score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


class VectorRetriever:
    """
    语义相似检索器。
    使用简化 TF-IDF + 余弦相似度。
    适合: 概念搜索、改写匹配、泛化查询。
    注意: 这不是真正的嵌入模型——是简化的词袋版本。
    """

    def __init__(self):
        self.docs: dict[str, str] = {}
        self._idf: dict[str, float] = {}
        self._vectors: dict[str, dict[str, float]] = {}

    def index(self, doc_id: str, text: str):
        self.docs[doc_id] = text

    def _tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    def _build_index(self):
        """构建 TF-IDF 向量索引。"""
        doc_count = len(self.docs)
        if doc_count == 0:
            return

        # 计算 DF（文档频率）
        df: dict[str, int] = {}
        all_tokens = []
        for text in self.docs.values():
            tokens = set(self._tokenize(text))
            for t in tokens:
                df[t] = df.get(t, 0) + 1
            all_tokens.extend(self._tokenize(text))

        # 计算 IDF
        self._idf = {t: math.log((doc_count + 1) / (freq + 1)) + 1
                     for t, freq in df.items()}

        # 计算 TF-IDF 向量
        for doc_id, text in self.docs.items():
            tf: dict[str, float] = {}
            tokens = self._tokenize(text)
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            max_tf = max(tf.values()) if tf else 1
            vec = {}
            for t, freq in tf.items():
                vec[t] = (freq / max_tf) * self._idf.get(t, 1)
            self._vectors[doc_id] = vec

    def _cosine_sim(self, v1: dict[str, float], v2: dict[str, float]) -> float:
        all_keys = set(v1.keys()) | set(v2.keys())
        dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in all_keys)
        n1 = math.sqrt(sum(v**2 for v in v1.values()))
        n2 = math.sqrt(sum(v**2 for v in v2.values()))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def search(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        """语义检索。"""
        self._build_index()
        if not self._vectors:
            return []

        query_tokens = self._tokenize(query)
        max_tf = max(query_tokens.count(t) for t in set(query_tokens)) if query_tokens else 1
        q_vec = {t: (query_tokens.count(t) / max_tf) * self._idf.get(t, 1)
                 for t in set(query_tokens)}

        results = []
        for doc_id, doc_vec in self._vectors.items():
            score = self._cosine_sim(q_vec, doc_vec)
            if score > 0:
                results.append(RetrievalResult(doc_id, self.docs[doc_id][:200], score))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


def reciprocal_rank_fusion(lists: list[list[RetrievalResult]], k: int = 60) -> list[RetrievalResult]:
    """
    RRF（Reciprocal Rank Fusion）：合并多个排序列表。
    在多个列表中都靠前的条目获得更高得分。
    """
    scores: dict[str, float] = {}
    texts: dict[str, str] = {}

    for ranked_list in lists:
        for rank, item in enumerate(ranked_list):
            id_ = item.id
            scores[id_] = scores.get(id_, 0) + 1.0 / (k + rank + 1)
            if id_ not in texts:
                texts[id_] = item.text

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [RetrievalResult(id_, texts[id_], score) for id_, score in merged]


@dataclass
class Skill:
    """技能描述: 名字 + 一句话描述 + 完整内容 + 版本。"""
    name: str
    description: str
    body: str = ""
    version: int = 1


class SkillIndex:
    """
    渐进式披露的技能索引。
    prefix 只暴露名称和描述（节省 token）。
    body 按需加载（用 get_skill()）。
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        self._skills[skill.name] = skill

    def get_prefix(self) -> str:
        """只返回名称和描述。"""
        lines = ["可用技能:"]
        for s in self._skills.values():
            lines.append(f"  - {s.name}: {s.description}")
        return "\n".join(lines)

    def get_skill(self, name: str) -> Optional[Skill]:
        """按需获取完整技能内容。"""
        return self._skills.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._skills.keys())


class RecallAgent(MemoryAgent):
    """
    在 MemoryAgent 基础上加入长期检索能力。
    在 prompt_builder 的 frozen_memory 中注入检索结果和技能索引。
    """

    def __init__(self, name: str = "RecallAgent", config: AgentConfig = None):
        super().__init__(name, config)
        self.fulltext = FullTextRetriever()
        self.semantic = VectorRetriever()
        self.skill_index = SkillIndex()

    def recall(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        """
        混合检索: 全文检索 + 语义检索 → RRF 融合。
        """
        ft_results = self.fulltext.search(query, top_k)
        sem_results = self.semantic.search(query, top_k)
        return reciprocal_rank_fusion([ft_results, sem_results], k=top_k * 3)


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Ch.06 - 长期记忆检索 (继承自 MemoryAgent)")
    print("=" * 50)

    agent = RecallAgent("Ch06Agent")
    agent.add_tool("calculator", "计算数学表达式。",
        {"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]},
        lambda a: str(eval(a["expression"])), read_only=True, idempotent=True)
    agent.add_tool("final_answer", "提交最终答案。",
        {"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},
        lambda a: a["text"])

    # 添加文档
    agent.fulltext.index("doc001", "TypeScript 是 JavaScript 的超集，添加了静态类型。")
    agent.fulltext.index("doc002", "Python 是动态类型语言，适合快速原型开发。")
    agent.semantic.index("doc001", "TypeScript 是 JavaScript 的超集，添加了静态类型。")
    agent.semantic.index("doc002", "Python 是动态类型语言，适合快速原型开发。")

    # 注册技能
    agent.skill_index.register(Skill("review_ts", "审查 TypeScript 代码质量", "检查类型安全、lint、测试覆盖"))
    agent.skill_index.register(Skill("deploy_check", "部署前置检查清单", "验证构建、测试、配置"))

    # 测试检索
    results = agent.recall("TypeScript 代码风格")
    print(f"  检索 'TypeScript 代码风格' 结果:")
    for r in results:
        print(f"    [{r.id}] score={r.score:.3f}: {r.text[:60]}")

    print(f"\n  技能索引前缀:")
    print(f"    {agent.skill_index.get_prefix()[:100]}...")
