# Agentic Extension Learning Package - 用 AI 伙伴深入学习智能体系统

> 中文版 · [English](README.md)

**本项目基于 [bryanyzhu/agentic-ai-system-course](https://github.com/bryanyzhu/agentic-ai-system-course) 进行改编和扩展，特此致谢！**

---

这门课面向零基础的学习者。原课程作者 **[bryanyzhu/agentic-ai-system-course](https://github.com/bryanyzhu/agentic-ai-system-course)** 提供了一套 22 章的骨架（纯 Markdown 文件），讲的是生产级 AI Agent 的设计思路。我在这个骨架基础上写了配套的代码文件（`Code/agent_NN.py`），每章一个。

---

## 扩展包内容

扩展包内附带了针对每章课程的示范代码（`Code/agent_NN.py`，共 23 个文件）。每个文件都完整独立，直接 `python agent_NN.py` 就能跑。文件内部用注释标记了哪些代码是前置地基、哪些是本章新增内容。

另外还提供了一份面向零基础的入门指南「写在所有的开头.html」——从终端是什么开始教，到写出一个能用的 Agent 结束，每段代码都有白话解释。

---

## 课程结构（22 章）

| 章节 | 主题 | 核心代码 |
|------|------|---------|
| **Ch.00** | 如何使用这门课 | `agent_00.py` — Agent 骨架 |
| **Ch.01** | 一次 Tool Call | `agent_01.py` — LLM 调用 + 工具注册 |
| **Ch.02** | Agent 循环 | `agent_02.py` — while 循环 + 停止条件 |
| **Ch.03** | 工具契约与校验 | `agent_03.py` — ToolRegistry + 校验流水线 |
| **Ch.04** | Prompt 与 Cache | `agent_04.py` — PromptBuilder + 缓存追踪 |
| **Ch.05** | 短期记忆 | `agent_05.py` — 三视图记忆管理 |
| **Ch.06** | 长期检索 | `agent_06.py` — 全文/语义检索 + RRF |
| **Ch.07** | 记忆写入与策展 | `agent_07.py` — MemoryStore + 安全过滤 |
| **Ch.08** | 持久化状态 | `agent_08.py` — SQLite + CAS 认领 |
| **Ch.09** | 计划模式 | `agent_09.py` — Checklist + DAG 依赖图 |
| **Ch.10** | 多 Agent 委派 | `agent_10.py` — 子 Agent 调度 |
| **Ch.11** | Agent 运行时 | `agent_11.py` — 生命周期 + 钩子 |
| **Ch.12** | 人在回路 | `agent_12.py` — 权限引擎 + HITL |
| **Ch.13** | 连接器与 MCP | `agent_13.py` — 频道适配 + Webhook |
| **Ch.14** | 技能与子 Agent | `agent_14.py` — SkillStore + 决策准则 |
| **Ch.15** | 后端基础设施 | `agent_15.py` — 队列 + Outbox + 租户 |
| **Ch.16** | 可观测性 | `agent_16.py` — Tracer + Metrics |
| **Ch.17** | 模型策略 | `agent_17.py` — 模型路由 + 成本估算 |
| **Ch.18** | 安全防御 | `agent_18.py` — 威胁扫描 + 防御流水线 |
| **Ch.19** | 运维就绪 | `agent_19.py` — Runbook + 优雅关闭 |
| **Ch.20** | 主动型 Agent | `agent_20.py` — CronJob + 通知门控 |
| **Ch.21** | 自我演化 | `agent_21.py` — 提案引擎 + 漂移检测 |
| **Ch.22** | 设计画布 | `agent_22.py` — 五种原型 + 完整继承链 |

每一章的 `agent_NN.py` 都是**独立的**。你可以在学完某章后直接运行对应的文件，无需担心前面的代码没有读完。

---

## 快速开始

```bash
# 1. 克隆本仓库
git clone https://github.com/你的用户名/Agentic-Extension-Learning-Package
cd Agentic-Extension-Learning-Package

# 2. 安装依赖
pip install openai

# 3. 从 Ch.00 开始
python Code/agent_00.py

# 4. 一路向前
python Code/agent_01.py
python Code/agent_02.py
# ...
python Code/agent_22.py
```

> 注意：`agent_01.py` 及之后的文件需要配置 API Key 才能调用大模型。
> 请将 `AgentConfig` 中的 `YOUR_API_KEY_HERE` 替换为你的真实密钥。

---

## 推荐学习路径

- **纯新手** → 先看「写在所有的开头.html」，再按 Ch.00 → Ch.01 → ... 的顺序学
- **有 Python 基础** → 从 Ch.00 开始，每章先看代码，再看代码中的注释
- **想快速上手** → 跳到 Ch.22 的设计画布，明确目标后再回看需要的章节
- **找特定知识点** → 直接打开对应的 `agent_NN.py`，它是独立的

---

## 仓库布局

```
Code/                  — 23 个自包含的 Python 代码文件
course/                — 课程内容
  ├── zh/              — 中文课程章节
  ├── en/              — 英文课程章节
  └── 写在所有的开头.html  — 零基础入门指南
CLAUDE.md              — AI 伙伴行为指南
AGENTS.md              — 与 CLAUDE.md 内容相同
README.md              — 英文说明文件
README_zh.md           — 本文件（中文说明）
```

---

## 致谢

课程内容来自 **[bryanyzhu/agentic-ai-system-course](https://github.com/bryanyzhu/agentic-ai-system-course)**，一份 22 章的 AI Agent 骨架课程。后续我会持续完善和扩展这个课程包的内容。

如果对你有帮助，给本项目和原项目各点一个 star 吧！

---

## License

课程内容遵循原项目的许可证，开放用于教育用途。
