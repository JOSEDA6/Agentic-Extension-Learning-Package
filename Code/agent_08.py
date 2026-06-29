#!/usr/bin/env python3
"""
agent_08.py —— 持久化状态与检查点 (State & Persistence)
对应课程: Ch.08 — State and persistence

完全独立，不依赖本地 .py 文件。
python agent_08.py
"""

# ============================================================
# 地基代码（精简版）
# ============================================================
import json, os, time, hashlib, math, sqlite3, threading
from enum import Enum; from dataclasses import dataclass, field; from typing import Optional
from openai import OpenAI

@dataclass
class AgentConfig:
    model:str="gpt-4o-mini"; max_steps:int=10; token_budget:int=8000; api_key:str="YOUR_API_KEY_HERE"; base_url:str="https://api.openai.com/v1"

class BaseAgent:
    def __init__(self,n="Agent",c=None): self.name=n; self.config=c or AgentConfig(); self.tools:dict[str,callable]={}; self.history:list[dict]=[]
    def __repr__(s): return f"<{s.__class__.__name__}('{s.name}': tools={list(s.tools.keys())}, history={len(s.history)} msgs)>"

@dataclass
class RunResult: answer:str=""; steps:int=0; total_tokens:int=0; stop_reason:str=""; tool_calls_made:list[dict]=field(default_factory=list)
# ============================================================
# 地基代码结束
# ============================================================


# +++ Ch.08 新增: 持久化状态管理 +++
#
# 前几章的 Agent 都是「一次性的」——用完就丢，状态全在内存里。
# Ch.08 引入:
#   - RunStatus: 状态机（queued → running → completed/failed）
#   - RunStore: 基于 SQLite 的持久化存储（CAS 认领 + 检查点 + 心跳）

class RunStatus(str, Enum):
    """运行状态机: 终态不可回转。"""
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def TERMINAL(cls) -> set:
        return {cls.COMPLETED, cls.FAILED, cls.CANCELLED}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _future(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + seconds))


class RunStore:
    """
    持久化运行存储——基于 SQLite + WAL 模式。
    核心功能:
      - CAS 原子认领: 防止多个 worker 抢占同一任务
      - Checkpoint: 步骤边界的持久化快照
      - Heartbeat + Reaper: 检测死掉的 worker
    """

    def __init__(self, db_path: str = "runs.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        """每个线程一个连接（thread-local）。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'queued',
                agent_name TEXT,
                created_at TEXT,
                claimed_by TEXT,
                heartbeat_at TEXT,
                checkpoint_data TEXT,
                error TEXT
            )
        """)
        conn.commit()

    def create_run(self, run_id: str, agent_name: str = "") -> bool:
        """创建一个新运行。"""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO runs (run_id, status, agent_name, created_at) VALUES (?, ?, ?, ?)",
                (run_id, RunStatus.QUEUED.value, agent_name, _now()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def claim(self, run_id: str, worker_id: str) -> bool:
        """
        CAS 原子认领: 仅当状态为 queued 时才能认领。
        防止两个 worker 同时跑同一个任务。
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE runs SET status=?, claimed_by=?, heartbeat_at=? "
            "WHERE run_id=? AND status=?",
            (RunStatus.RUNNING.value, worker_id, _now(), run_id, RunStatus.QUEUED.value))
        conn.commit()
        return cursor.rowcount > 0

    def checkpoint(self, run_id: str, step: int, messages_count: int, tokens: int):
        """保存一个检查点。"""
        conn = self._get_conn()
        data = json.dumps({"step": step, "msgs": messages_count, "tokens": tokens,
                          "time": _now()})
        conn.execute(
            "UPDATE runs SET checkpoint_data=?, heartbeat_at=? WHERE run_id=?",
            (data, _now(), run_id))
        conn.commit()

    def transition(self, run_id: str, new_status: RunStatus, error: str = "") -> bool:
        """
        状态迁移。终态不可回转——如果已经是 completed/failed/cancelled，
        禁止再改成其他状态。
        """
        conn = self._get_conn()
        row = conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return False
        if row["status"] in RunStatus.TERMINAL():
            return False  # 终态不可回转
        conn.execute(
            "UPDATE runs SET status=?, error=?, heartbeat_at=? WHERE run_id=?",
            (new_status.value, error, _now(), run_id))
        conn.commit()
        return True

    def heartbeat(self, run_id: str) -> bool:
        """更新心跳时间。"""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE runs SET heartbeat_at=? WHERE run_id=? AND status=?",
            (_now(), run_id, RunStatus.RUNNING.value))
        conn.commit()
        return cursor.rowcount > 0

    def reap(self, timeout_seconds: int = 300) -> list[str]:
        """
        Reaper: 回收心跳超时的孤儿运行。
        返回被回收的 run_id 列表。
        """
        conn = self._get_conn()
        deadline = time.strftime("%Y-%m-%dT%H:%M:%S",
                                 time.gmtime(time.time() - timeout_seconds))
        cursor = conn.execute(
            "UPDATE runs SET status=? WHERE status=? AND heartbeat_at < ?",
            (RunStatus.FAILED.value, RunStatus.RUNNING.value, deadline))
        conn.commit()
        if cursor.rowcount > 0:
            rows = conn.execute(
                "SELECT run_id FROM runs WHERE status=? AND heartbeat_at < ?",
                (RunStatus.FAILED.value, deadline)).fetchall()
            return [r["run_id"] for r in rows]
        return []

    def get(self, run_id: str) -> Optional[dict]:
        """查询一个运行的状态。"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row:
            return dict(row)
        return None


class DurableAgent(BaseAgent):
    """
    在 BaseAgent 基础上加入持久化运行存储。
    """

    def __init__(self, name: str = "DurableAgent", config: AgentConfig = None,
                 db_path: str = "runs.db"):
        super().__init__(name, config)
        self.run_store = RunStore(db_path=db_path)

    def run(self, user_message: str, system_prompt: str = "",
            run_id: str = "") -> RunResult:
        """持久化版本的 run()——在运行前后写入状态。"""
        if not run_id:
            run_id = f"run_{int(time.time())}"
        self.run_store.create_run(run_id, self.name)
        self.run_store.claim(run_id, f"worker_{self.name}")

        result = RunResult()
        result.answer = f"[模拟运行] run_id={run_id}"
        result.stop_reason = "completed"

        self.run_store.checkpoint(run_id, 1, 2, 100)
        self.run_store.transition(run_id, RunStatus.COMPLETED)
        return result


# ── 演示 ────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile, os
    tmp_db = os.path.join(tempfile.mkdtemp(), "test.db")

    print("=" * 50)
    print("  Ch.08 - 持久化状态 (继承自 BaseAgent)")
    print("=" * 50)

    store = RunStore(db_path=tmp_db)

    # 演示 CAS 认领
    store.create_run("run-001", "Agent-A")
    claimed_a = store.claim("run-001", "worker-A")
    claimed_b = store.claim("run-001", "worker-B")  # 应该失败
    print(f"  CAS 认领:")
    print(f"    worker-A 认领: {'成功' if claimed_a else '失败'}")
    print(f"    worker-B 认领: {'成功' if claimed_b else '失败'} (期望失败)")

    # 检查点
    store.checkpoint("run-001", step=1, messages_count=5, tokens=500)
    print(f"\n  检查点已保存: step=1, tokens=500")

    # 状态迁移 + 终态不可回转
    ok = store.transition("run-001", RunStatus.COMPLETED)
    ok2 = store.transition("run-001", RunStatus.RUNNING)
    print(f"\n  状态迁移:")
    print(f"    -> COMPLETED: {'成功' if ok else '失败'}")
    print(f"    -> RUNNING (终态后): {'成功' if ok2 else '失败'} (期望失败)")

    print(f"\n  [演示完成] SQLite 持久化层: CAS + 检查点 + 终态不可回转")
    # 清理（注意: 需要先关闭 SQLite 连接）
    if os.path.exists(tmp_db):
        try: os.remove(tmp_db)
        except PermissionError: pass
