"""Shared order operations agent used by Module 1 (Deep Agents) and Module 3 (LangSmith).

This is the minimal useful Deep Agent: a research subagent + Tavily search + a
checkpointer. It deliberately omits HITL and FilesystemBackend so that
evaluation runs in Module 3 don't pause or leak files to disk.

Module 1 builds up to this agent step-by-step in the notebook. This file
packages the same pattern so Module 3 can import it directly:

    from agents.order_agent import build_order_agent
    agent = build_order_agent()
"""

from datetime import datetime

from deepagents import create_deep_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from utils.models import model
from utils.search import resilient_tavily_search


@tool(parse_docstring=True)
def tavily_search(query: str) -> str:
    """Search the web for information on a given query.

    Args:
        query: Search query to execute.
    """
    # `resilient_tavily_search` retries on Tavily failure with linear backoff,
    # then falls back to a topic-matched canned response so a flaky network
    # doesn't break the workshop. See utils/search.py for details.
    return resilient_tavily_search(query, max_retries=2)


def build_order_agent():
    """Return a fresh order operations deep agent.

    Each call returns a new agent with a fresh checkpointer — useful so eval
    runs don't share state with each other.
    """
    research_subagent = {
        "name": "research-agent",
        "description": (
            "Delegate order and payer research tasks. Give one order or payer "
            "question at a time."
        ),
        "system_prompt": (
            f"You are an order operations research analyst. Today is "
            f"{datetime.now().strftime('%Y-%m-%d')}.\n"
            "Use tools to gather payer policy, coding, and authorization "
            "requirements. Limit to 3 search calls."
        ),
        "tools": [tavily_search],
    }

    return create_deep_agent(
        model=model,
        tools=[tavily_search],
        system_prompt=(
            "You are a helpful order operations analyst. "
            "Delegate payer and coding research to the research-agent. "
            "State requirements as general guidance, not reimbursement advice."
        ),
        subagents=[research_subagent],
        checkpointer=MemorySaver(),
    )
