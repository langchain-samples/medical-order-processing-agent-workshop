"""Retry + canned-fallback helper for Tavily web search.

The shape: call `resilient_tavily_search(query)` from inside your own `@tool`
function. The helper retries on Tavily failures with linear backoff, and if
every retry fails it returns a Tavily-shaped canned response matched against
topic keywords — chosen so the agent's downstream synthesis still produces a
useful answer during a workshop with a flaky network.

Usage (from a notebook or module):

    from langchain_core.tools import tool
    from utils.search import resilient_tavily_search

    @tool(parse_docstring=True)
    def tavily_search(query: str) -> str:
        \"\"\"Search the web for information on a given query.

        Args:
            query: Search query to execute.
        \"\"\"
        return resilient_tavily_search(query, max_retries=2)

The `@tool` decorator stays at the call site so the tool's name, docstring,
and signature remain visible to the reader. Only the resilience plumbing is
hidden behind the util.
"""

from __future__ import annotations

import time
from typing import Optional

from tavily import TavilyClient


# --------------------------------------------------------------------------- #
# Canned fallbacks — based on patterns we observed in real traces.
# Each entry is a list of (title, url, content) tuples shaped like Tavily's
# `results[]` payload. Keys are lowercase phrases matched as substrings.
# Order matters: longer/more-specific keys are checked first.
# --------------------------------------------------------------------------- #

_FALLBACK_RESULTS: list[tuple[tuple[str, ...], list[tuple[str, str, str]]]] = [
    (("difference between hcpcs and cpt", "hcpcs and cpt", "hcpcs vs cpt"), [
        (
            "HCPCS vs CPT codes — what each is used for",
            "https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system",
            "CPT codes describe procedures and professional services and are maintained by the "
            "AMA. HCPCS Level II codes describe items, supplies, and non-physician services — "
            "durable medical equipment, prosthetics, orthotics, and supplies — and are "
            "maintained by CMS. A device order is typically identified by an HCPCS Level II "
            "code, while the procedure to place or manage it is billed with a CPT code.",
        ),
    ]),
    (("certificate of medical necessity", "cmn"), [
        (
            "Certificate of Medical Necessity (CMN) — purpose and contents",
            "https://www.cms.gov/medicare/cms-forms/cms-forms",
            "A Certificate of Medical Necessity documents that a prescribed item meets the "
            "payer's medical-necessity criteria. It is completed by the treating clinician and "
            "typically captures the diagnosis, the specific item and HCPCS code, the expected "
            "length of need, and the clinician's signature and date. Payers may also require "
            "supporting chart notes; a CMN alone is rarely sufficient.",
        ),
    ]),
    (("prior authorization denial", "prior-authorization denial", "authorization denials"), [
        (
            "Common causes of prior authorization denials",
            "https://www.cms.gov/priorauth",
            "Denials commonly stem from incomplete documentation, a mismatch between the "
            "submitted code and the documented diagnosis, missing evidence that the payer's "
            "step-therapy or medical-necessity criteria were met, submission to the wrong "
            "benefit channel, or a request filed after the service date. Many denials are "
            "administrative rather than clinical and are overturned on appeal once the "
            "supporting record is supplied.",
        ),
    ]),
    (("prior authorization", "prior-authorization", "preauthorization"), [
        (
            "Prior authorization — what it is and when it applies",
            "https://www.cms.gov/priorauth",
            "Prior authorization is a payer requirement to approve an item or service before "
            "it is furnished. Requirements are plan-, product-, code-, and benefit-specific: "
            "the same device can require authorization under one plan and not another, and "
            "can route through a DME, pharmacy, or home-infusion benefit. Verify the payer's "
            "current policy and the confirmed HCPCS code before assuming a requirement.",
        ),
    ]),
    (("durable medical equipment", "dme"), [
        (
            "Durable Medical Equipment (DME) in medical billing",
            "https://www.cms.gov/medicare/coverage/durable-medical-equipment-coverage",
            "DME refers to equipment that is reusable, primarily serves a medical purpose, and "
            "is appropriate for use in the home — pumps, wheelchairs, hospital beds, and "
            "similar items. Coverage is governed by Local Coverage Determinations and "
            "documentation requirements administered by the DME MACs. Items are identified by "
            "HCPCS Level II codes, often with rental or purchase modifiers.",
        ),
    ]),
    (("infusion pump", "ambulatory infusion"), [
        (
            "External infusion pumps — coverage and documentation",
            "https://www.cms.gov/medicare-coverage-database",
            "External ambulatory infusion pumps are covered when the applicable Local Coverage "
            "Determination criteria are met for the specific drug and indication. "
            "Documentation generally includes a signed prescriber order, the diagnosis and "
            "indication, the drug with route, dose and duration, the pump and supply HCPCS "
            "codes, and supporting clinical records. Requirements differ between reusable "
            "external pumps and disposable delivery systems.",
        ),
    ]),
    (("hcpcs",), [
        (
            "HCPCS Level II codes",
            "https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system",
            "HCPCS Level II is a standardized code set for products, supplies, and services "
            "not covered by CPT — most notably durable medical equipment, prosthetics, "
            "orthotics, and supplies. Codes are alphanumeric (a letter followed by four "
            "digits) and are frequently paired with modifiers indicating rental, purchase, or "
            "replacement. CMS updates the set quarterly.",
        ),
    ]),
]


_GENERIC_FALLBACK = [
    (
        "Search temporarily unavailable",
        "https://fallback.example/no-results",
        "The web search service didn't return results for this query. Use what you already "
        "know to answer; if information is missing, say so plainly rather than guessing.",
    ),
]


def _format_results(results: list[tuple[str, str, str]]) -> str:
    """Match TavilyClient output formatting used everywhere else in the workshops."""
    return "\n\n".join(f"**{t}**\n{u}\n{c}" for t, u, c in results)


def _pick_fallback(query: str) -> str:
    q = query.lower()
    for keys, results in _FALLBACK_RESULTS:
        if any(k in q for k in keys):
            return _format_results(results)
    return _format_results(_GENERIC_FALLBACK)


# --------------------------------------------------------------------------- #
# Public helper
# --------------------------------------------------------------------------- #

# Lazy singleton — instantiated once on first call, then reused.
_default_client: Optional[TavilyClient] = None


def resilient_tavily_search(
    query: str,
    *,
    max_retries: int = 2,
    max_results: int = 3,
    base_backoff_seconds: float = 1.0,
    client: Optional[TavilyClient] = None,
) -> str:
    """Run a Tavily search with retries; fall back to canned content on failure.

    Returns a Tavily-shaped string (each result formatted as
    `**title**\\nurl\\ncontent`, joined by blank lines) so the caller can return
    it from a `@tool` function as-is.

    Args:
        query: search query to run.
        max_retries: additional attempts after the first call. `max_retries=2`
            means up to 3 total attempts before falling back.
        max_results: passed through to `TavilyClient.search`.
        base_backoff_seconds: first retry sleeps this long; subsequent retries
            sleep `base * attempt` (linear backoff).
        client: optional TavilyClient to use. If `None`, a lazily-initialized
            module-level client is used.
    """
    global _default_client
    if client is None:
        if _default_client is None:
            _default_client = TavilyClient()
        client = _default_client

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            results = client.search(query, max_results=max_results)
            hits = results.get("results", [])
            if hits:
                return "\n\n".join(
                    f"**{r['title']}**\n{r['url']}\n{r['content']}"
                    for r in hits
                )
            last_error = RuntimeError("Tavily returned 0 results")
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(base_backoff_seconds * (attempt + 1))

    notice = (
        f"[fallback content; live search unavailable -- "
        f"{type(last_error).__name__}: {str(last_error)[:120]}]\n\n"
    )
    return notice + _pick_fallback(query)
