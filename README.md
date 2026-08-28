# Order Processing Agent Workshop

Hands-on tutorials for building, deploying, and evaluating an **order operations agent** with Deep Agents and LangSmith.

The agent researches payer, coding, and authorization requirements for medical device orders and drafts exception notes the order desk can act on. All order, account, and payer data in these modules is synthetic.

Derived from the [Modular Workshops](https://github.com/langchain-ai/modular-workshops) series — this fork keeps the three modules that take an agent from prototype to production. Intended to be run in a session with a LangChain engineer. For more depth on your own, see [LangChain Academy](https://academy.langchain.com/courses/intro-to-langgraph), which has pre-recorded videos from our engineers.

## Modules

| # | Module | Covers | Time |
|---|--------|--------|------|
| 1 | [`01_deep_agents.ipynb`](modules/01_deep_agents.ipynb) | Build the order operations agent on the Deep Agents harness — custom tools, subagents, backends & memory, middleware, HITL, `AGENTS.md` + skills | ~60 min |
| 2 | [`02_deploy.ipynb`](modules/02_deploy.ipynb) | Ship that same agent to LangSmith Deployments with the `langgraph` CLI | ~15 min |
| 3 | [`03_langsmith.ipynb`](modules/03_langsmith.ipynb) | Prompt engineering (Playground + Prompt Hub), tracing, offline & online evals, annotation queues | ~30 min |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment variables
cp .env.example .env
# Edit .env and fill in your keys
```

| Key | Required for | Get one |
|-----|--------------|---------|
| `WORKSHOP_USER` | All modules — your unique attendee slug | pick one, e.g. `jane-doe` |
| `OPENAI_API_KEY` | Modules 1-3 (default model) | <https://platform.openai.com> |
| `LANGSMITH_API_KEY` | Modules 2 & 3 (recommended for all) | <https://smith.langchain.com> |
| `TAVILY_API_KEY` | Modules 1 & 3 (web search tool) | <https://tavily.com> |
| `LANGSMITH_API_KEY_GATEWAY` | Optional — only if you switch `utils/models.py` to the LLM Gateway block | same key as `LANGSMITH_API_KEY` |

```bash
# 3. Start Jupyter
uv run jupyter notebook
```

Open whichever module(s) your recipe calls for.

## Running with Multiple Attendees

Everyone in a session shares one LangSmith workspace, and LangSmith resources are addressed by **name** — so two attendees running the same cell would otherwise overwrite each other's tracing project, hub prompt, eval dataset, deployment, run rules, and annotation queue.

`WORKSHOP_USER` in your `.env` is the per-attendee slug that keeps them apart. Every shared name is wrapped in `scoped()` from [`utils/workshop.py`](utils/workshop.py), which suffixes it with your slug:

```python
from utils.workshop import scoped
scoped("order-agent-evals")   # -> "order-agent-evals-jane-doe"
```

The modules fail loudly at their setup cell if `WORKSHOP_USER` is unset or still `<first-last>`, rather than silently colliding.

**Use lowercase letters, digits, and hyphens only.** `.env` interpolates the raw value into `LANGSMITH_PROJECT`, while `scoped()` slugifies it — so `"Jane Doe"` would name your tracing project `...-Jane Doe` but your dataset `...-jane-doe`. You'll get a warning if the two diverge.

## Switching Models

All modules import `model` from `utils/models.py`. Change one line there to swap providers — no notebook edits required.

```python
# utils/models.py

# OpenAI
# model = init_chat_model("openai:gpt-5.6-terra", use_responses_api=True)

# Anthropic
# model = init_chat_model("anthropic:claude-sonnet-5")

# Azure OpenAI
# from langchain_openai import AzureChatOpenAI
# model = AzureChatOpenAI(azure_deployment="gpt-5.6-terra", streaming=True)

# AWS Bedrock (default)
from langchain_aws import ChatBedrockConverse
model = ChatBedrockConverse(provider="anthropic", model_id="anthropic.claude-sonnet-5")
```

### Routing through the LangSmith LLM Gateway

The simplest route needs **no code change** — set these in `.env` and the OpenAI SDK picks them up:

```bash
OPENAI_API_KEY="<gateway-key>"
OPENAI_BASE_URL="https://gateway.smith.langchain.com/openai/v1"
```

The Anthropic equivalent is `ANTHROPIC_BASE_URL="https://gateway.smith.langchain.com/anthropic"`. Both notebooks *and* the deployed agent then route through the gateway, subject to workspace policies.

`utils/models.py` also ships a commented-out gateway block that hardcodes the `base_url` and reads `LANGSMITH_API_KEY_GATEWAY` (the same key under a non-reserved name, since `langgraph deploy` strips `LANGSMITH_API_KEY` during upload). The env-var route above is usually simpler.

The gateway must be enabled for your LangSmith organization, and the key needs the `gateway:invoke` permission — otherwise calls fail with `missing permission gateway:invoke`.

## Deploy (Module 2)

Module 2 deploys the agent at `agents/deep_agent/` to LangSmith via the `langgraph` CLI (installed by `uv sync`). The deploy config is `langgraph.json` at the workshop root.

Because `agents/deep_agent/agent.py` imports `model` from `utils.models`, whichever block is active in `utils/models.py` at deploy time is what ships — no extra flags.

Your `LANGSMITH_API_KEY` must have deployment permissions (use a `lsv2_sk_...` service key).

## Project Structure

```
order-processing-agent-workshop/
├── README.md                       (this file — recipes + setup)
├── pyproject.toml                  (shared dependencies)
├── .env.example
├── langgraph.json                  (registers agents/deep_agent for langgraph dev)
├── utils/
├── agents/
│   ├── order_agent.py              (shared agent factory — Module 1 builds it, Module 3 imports for eval)
│   └── deep_agent/                 (deployable agent for Module 2)
│       ├── agent.py
│       ├── AGENTS.md
│       └── skills/
│           ├── exception-note/SKILL.md
│           └── status-update/SKILL.md
├── images/                         (diagrams used by the notebooks)
└── modules/
    ├── 01_deep_agents.ipynb        (Module 1 — Deep Agents)
    ├── 02_deploy.ipynb             (Module 2 — Deploy)
    └── 03_langsmith.ipynb          (Module 3 — LangSmith)
```

## Common Issues

**`langgraph deploy` fails with 403 / permission denied**
Your API key is a personal token. Generate a service key (`lsv2_sk_...`) in LangSmith settings.

**Notebook can't find `utils` / `agents`**
Each module's setup cell prepends `project_root` (the workshop root) to `sys.path`. If you moved a notebook, update the `Path().resolve().parent` line to point at the workshop root.

## For LangChain Internal Users
Please refer to this linked [Notion document](https://app.notion.com/p/Modular-Workshops-37d808527b1780318063fd210446aa03?source=copy_link) for instructions on setup and usage.
