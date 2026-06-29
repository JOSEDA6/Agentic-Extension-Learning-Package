# Agentic Extension Learning Package - Learn Agentic Systems with Your AI Partner

> English · [中文](README_zh.md)

**This project is adapted and extended from [bryanyzhu/agentic-ai-system-course](https://github.com/bryanyzhu/agentic-ai-system-course). Special thanks to the original author!**

---

This course is designed for beginners. The original author **[bryanyzhu/agentic-ai-system-course](https://github.com/bryanyzhu/agentic-ai-system-course)** provided a 22-chapter skeleton (pure Markdown) covering the design of production-grade AI agents. I wrote companion code files (`Code/agent_NN.py`) on top of that skeleton, one per chapter.

---

## What's inside

This package includes hands-on demo code for each chapter (`Code/agent_NN.py`, 23 files total). Every file is fully self-contained — just run `python agent_NN.py`. Comments inside each file mark which code comes from previous chapters and which is new.

There is also a beginner-friendly guide for absolute starters: `course/写在所有的开头.html`. It starts from "what is a terminal" and walks through building a working Agent, with plain-language explanations for every line.

---

## Course structure (22 chapters)

| Chapter | Topic | Demo code |
|---------|-------|-----------|
| **Ch.00** | How to use this course | `agent_00.py` — Agent skeleton |
| **Ch.01** | One tool call | `agent_01.py` — LLM call + tool registration |
| **Ch.02** | The agent loop | `agent_02.py` — while loop + stop conditions |
| **Ch.03** | Tools the agent can trust | `agent_03.py` — ToolRegistry + validation pipeline |
| **Ch.04** | Prompts, context & cache | `agent_04.py` — PromptBuilder + cache tracking |
| **Ch.05** | Short-term memory | `agent_05.py` — Three-view memory management |
| **Ch.06** | Long-term recall | `agent_06.py` — Full-text/semantic search + RRF |
| **Ch.07** | Memory writing & curation | `agent_07.py` — MemoryStore + safety filter |
| **Ch.08** | State and persistence | `agent_08.py` — SQLite + CAS claiming |
| **Ch.09** | Planning patterns | `agent_09.py` — Checklist + DAG dependency graph |
| **Ch.10** | Multi-agent delegation | `agent_10.py` — Subagent dispatch |
| **Ch.11** | The agent harness | `agent_11.py` — Lifecycle + hooks |
| **Ch.12** | Human in the loop | `agent_12.py` — Permission engine + HITL |
| **Ch.13** | Connectors, MCP, IPC | `agent_13.py` — Channel adapter + Webhook |
| **Ch.14** | Skills, MCP & subagents | `agent_14.py` — SkillStore + decision criteria |
| **Ch.15** | Backend infrastructure | `agent_15.py` — Queue + Outbox + tenant |
| **Ch.16** | Observability | `agent_16.py` — Tracer + Metrics |
| **Ch.17** | Cost, latency & model strategy | `agent_17.py` — Model routing + cost estimation |
| **Ch.18** | Safety & adversarial inputs | `agent_18.py` — Threat scan + defense pipeline |
| **Ch.19** | Ops & forward-deployed | `agent_19.py` — Runbook + graceful shutdown |
| **Ch.20** | Proactive agents | `agent_20.py` — CronJob + notification gate |
| **Ch.21** | Self-evolving agents | `agent_21.py` — Evolution engine + drift detection |
| **Ch.22** | Designing your own agent | `agent_22.py` — Five archetypes + full inheritance chain |

Every `agent_NN.py` is independent. Run it directly after studying the corresponding chapter.

---

## Quick start

```bash
# 1. Clone this repo
git clone https://github.com/your-username/Agentic-Extension-Learning-Package
cd Agentic-Extension-Learning-Package

# 2. Install dependency
pip install openai

# 3. Start from Ch.00
python Code/agent_00.py

# 4. Move forward
python Code/agent_01.py
python Code/agent_02.py
# ...
python Code/agent_22.py
```

> Note: `agent_01.py` and later files require an API key to call the LLM.
> Replace `YOUR_API_KEY_HERE` in `AgentConfig` with your actual key.

---

## Recommended learning paths

- **Complete beginner** — Start with `course/写在所有的开头.html`, then go Ch.00 → Ch.01 → ...
- **Have Python basics** — Begin at Ch.00, read the code first, then the comments
- **Want to move fast** — Jump to Ch.22's design canvas, clarify your goal, then revisit needed chapters
- **Looking for a specific topic** — Open the corresponding `agent_NN.py` directly; it's self-contained

---

## Repository layout

```
Code/                  — 23 self-contained Python demo files
course/                — Course content
  ├── zh/              — Chinese chapter translations
  ├── en/              — English chapter files
  └── 写在所有的开头.html  — Beginner-friendly guide (Chinese)
CLAUDE.md              — AI partner behavior guide
AGENTS.md              — Same content as CLAUDE.md
README.md              — This file
README_zh.md           — Chinese README
```

---

## Acknowledgments

Course content comes from **[bryanyzhu/agentic-ai-system-course](https://github.com/bryanyzhu/agentic-ai-system-course)**, a 22-chapter AI Agent skeleton course. I will continue to improve and expand this package over time.

If you find it useful, please star both this repo and the original project!

---

## License

The course content follows the original project's license and is open for educational use.
