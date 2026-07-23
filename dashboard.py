"""
Lead Intelligence Dashboard — local, zero-cost email discovery + website
issue reporting.

Run with:
    streamlit run dashboard.py

Upload a CSV of companies (columns like `company_name`/`website` or
`name`/`domain`), click Start, and get real, verified emails plus a short
deterministic summary of each website's problems — useful for building
custom outreach. No email is ever fabricated: a company only appears in
the Leads table if a real email was actually found on its site.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.config import get_settings
from app.logging import configure_logging
from app.services.orchestrator import CompanyProgress, LocalBatchRunner

st.set_page_config(page_title="Lead Intelligence Dashboard", layout="wide")

configure_logging()
settings = get_settings()

st.title("Lead Intelligence Dashboard")
st.caption(
    "Upload a CSV of companies. The crawler only reports an email if it actually "
    "found one on the site — nothing here is guessed."
)

# -------------------------------------------------------------------------
# Sidebar settings
# -------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    concurrency = st.slider(
        "Concurrent crawling agents",
        min_value=5,
        max_value=7,
        value=max(5, min(settings.concurrent_crawlers, 7)),
        help="How many companies are crawled in parallel.",
    )
    batch_size = st.number_input(
        "Batch size",
        min_value=1,
        max_value=500,
        value=settings.batch_size,
        help="Companies processed per batch (a batch completes before the next starts).",
    )
    smtp_check = st.checkbox(
        "Enable SMTP validation (slower, more accurate)",
        value=settings.smtp_validation_enabled,
    )
    openai_available = bool(settings.openai_enabled and settings.openai_api_key)
    use_ai_summary = st.checkbox(
        "Polish issue summaries with OpenAI (optional, last resort)",
        value=False,
        disabled=not openai_available,
        help=(
            "Requires OPENAI_ENABLED=true and OPENAI_API_KEY set in .env. "
            "Deterministic summaries are always generated for free; this just "
            "rewrites them in more natural language."
            if not openai_available
            else "Uses OpenAI to rewrite the free deterministic summary in natural language."
        ),
    )
    show_no_email = st.checkbox("Show companies with no email found", value=True)

settings.concurrent_crawlers = concurrency
settings.batch_size = int(batch_size)
settings.smtp_validation_enabled = smtp_check

# -------------------------------------------------------------------------
# CSV upload
# -------------------------------------------------------------------------
uploaded = st.file_uploader("Upload CSV (company_name, website columns)", type=["csv"])

if uploaded is not None:
    csv_bytes = uploaded.getvalue()
    preview_df = pd.read_csv(uploaded)
    st.write(f"**{len(preview_df)} rows** detected in `{uploaded.name}`")
    st.dataframe(preview_df.head(10), use_container_width=True)

    start_clicked = st.button("Start Crawl", type="primary")

    if start_clicked:
        progress_bar = st.progress(0.0, text="Starting...")
        live_table = st.empty()
        live_rows: list[dict] = []
        completed_count = {"n": 0}
        total = len(preview_df)

        def _on_progress(progress: CompanyProgress) -> None:
            if progress.status == "crawling":
                return
            completed_count["n"] += 1
            fraction = min(1.0, completed_count["n"] / max(total, 1))

            result = progress.result or {}
            live_rows.append(
                {
                    "Company": result.get("name") or progress.name or progress.domain,
                    "Domain": progress.domain,
                    "State": result.get("state") or "",
                    "Status": progress.status,
                    "Emails": ", ".join(result.get("emails", [])),
                    "Business summary": result.get("business_summary", ""),
                    "Engines used": ", ".join(result.get("engines_used", [])),
                    "Issue summary": result.get("issue_summary", progress.error or ""),
                }
            )
            progress_bar.progress(
                fraction, text=f"Processed {completed_count['n']} / {total} companies"
            )
            live_table.dataframe(pd.DataFrame(live_rows), use_container_width=True)

        runner = LocalBatchRunner(use_ai_summary=use_ai_summary)
        results = asyncio.run(
            runner.run(csv_bytes, source_file=uploaded.name, progress_cb=_on_progress)
        )
        progress_bar.progress(1.0, text="Done")

        st.session_state["last_results"] = results
        st.session_state["last_run_at"] = datetime.now(timezone.utc).isoformat()

# -------------------------------------------------------------------------
# Results
# -------------------------------------------------------------------------
results = st.session_state.get("last_results")
if results:
    st.divider()
    st.header("Results")

    leads: list[dict] = []
    no_email: list[dict] = []
    all_engines: set[str] = set()

    for progress in results:
        if progress.status != "done" or not progress.result:
            continue
        result = progress.result
        all_engines.update(result.get("engines_used", []))
        emails = result.get("emails", [])
        row = {
            "Company": result.get("name") or progress.name or progress.domain,
            "Emails": ", ".join(emails),
            "Business summary": result.get("business_summary", ""),
            "State": result.get("state") or "",
            "Domain": progress.domain,
            "Engines used": ", ".join(result.get("engines_used", [])),
            "Issue summary": result.get("issue_summary", ""),
        }
        if emails:
            leads.append(row)
        else:
            no_email.append(row)

    st.subheader(f"Leads with a real email found ({len(leads)})")
    leads_df = pd.DataFrame(leads)
    st.dataframe(leads_df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download leads as CSV",
            data=leads_df.to_csv(index=False) if not leads_df.empty else "",
            file_name="leads.csv",
            mime="text/csv",
            disabled=leads_df.empty,
        )
    with col2:
        st.download_button(
            "Download leads as JSON",
            data=json.dumps(leads, indent=2, ensure_ascii=False),
            file_name="leads.json",
            mime="application/json",
            disabled=not leads,
        )

    if show_no_email and no_email:
        with st.expander(f"No email found, but site issues detected ({len(no_email)})"):
            st.dataframe(pd.DataFrame(no_email), use_container_width=True)

    if all_engines:
        st.caption(
            "Crawler engines actually used this run (cheapest first, escalated only "
            f"when needed): {', '.join(sorted(all_engines))}"
        )
