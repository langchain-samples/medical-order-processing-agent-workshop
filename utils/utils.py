"""Shared notebook helpers (graph rendering, env hygiene, Chinook demo DB).

Currently unused by Modules 1-3 — retained as scaffolding for custom modules.
"""

import os
import sqlite3
import requests
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


def trust_system_certs():
    """Merge the OS certificate store into a local CA bundle so requests/boto3 can
    verify certs from an internal proxy CA (e.g. corporate LangSmith/Bedrock endpoints).

    `truststore.inject_into_ssl()` does the same job but monkeypatches
    `ssl.SSLContext` globally, which causes a RecursionError on Windows/macOS
    (open bug: https://github.com/sethmlarson/truststore/issues/214). This builds
    a static PEM bundle instead and points the standard CA-bundle env vars at it,
    so no SSL internals are patched. Safe to call every run; regenerates the
    bundle file (gitignored via *.pem) from each user's own machine.
    """
    if os.name != "nt":
        return  # Windows-only workaround; other OSes' OpenSSL already trusts the system store.

    import ssl
    import certifi
    from pathlib import Path

    bundle_path = Path(__file__).resolve().parent.parent / "system-ca-bundle.pem"

    pem_certs = [Path(certifi.where()).read_text()]
    for store in ("CA", "ROOT"):
        for cert_der, encoding, _trust in ssl.enum_certificates(store):
            if encoding == "x509_asn":
                pem_certs.append(ssl.DER_cert_to_PEM_cert(cert_der))
    bundle_path.write_text("\n".join(pem_certs))

    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "AWS_CA_BUNDLE"):
        os.environ[var] = str(bundle_path)


def clear_local_env_vars():
    """Drop company-gateway env vars that would override our service key for this local demo invocation."""
    for _var in (
        "ANTHROPIC_CUSTOM_HEADERS",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        os.environ.pop(_var, None)


def show_graph(graph, xray=False):
    """Display a LangGraph mermaid diagram with ASCII fallback."""
    from IPython.display import Image
    try:
        return Image(graph.get_graph(xray=xray).draw_mermaid_png())
    except Exception as e:
        print(f"Image rendering failed: {e}")
        print("\nFalling back to ASCII:\n")
        print(graph.get_graph(xray=xray).draw_ascii())
        return None


def get_engine_for_chinook_db():
    """Download the Chinook SQL script and load it into an in-memory SQLite DB."""
    url = "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql"
    response = requests.get(url)
    sql_script = response.text

    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.executescript(sql_script)
    return create_engine(
        "sqlite://",
        creator=lambda: connection,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
