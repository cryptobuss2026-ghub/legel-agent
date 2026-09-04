"""
app.py
Streamlit dashboard for the Legal Case Analysis & Court Speech Generation System.

Run the FastAPI backend first:
    uvicorn main:app --reload --port 8000

Then run this app:
    streamlit run app.py
"""
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Configurable API Base URL
DEFAULT_API_BASE_URL = os.environ.get("LEGAL_API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Legal Case Analysis & Court Speech Generator",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# --------------------------------------------------------------------------

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "file_id" not in st.session_state:
    st.session_state.file_id = None
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("OPENAI_API_KEY", "")


def _reset_state() -> None:
    """Clear session analysis context."""
    st.session_state.analysis_result = None
    st.session_state.file_id = None


def _get_headers() -> dict:
    """Construct request headers containing authentication data."""
    headers = {}
    if st.session_state.api_key:
        headers["X-API-Key"] = st.session_state.api_key
        headers["Authorization"] = f"Bearer {st.session_state.api_key}"
    return headers


def _call_analyze_endpoint(api_url: str, uploaded_file, client_role: str) -> dict:
    """Post document to backend pipeline."""
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    data = {"client_role": client_role}
    headers = _get_headers()

    response = requests.post(
        f"{api_url}/api/analyze",
        files=files,
        data=data,
        headers=headers,
        timeout=600,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(show_spinner=False, ttl=300)
def _fetch_download_bytes(api_url: str, endpoint: str, api_key: str) -> bytes:
    """Retrieve binary export content (DOCX/JSON) with caching."""
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.get(f"{api_url}{endpoint}", headers=headers, timeout=120)
    response.raise_for_status()
    return response.content


# --------------------------------------------------------------------------
# SIDEBAR: CONFIGURATION & KEYS
# --------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Settings & Credentials")

    api_base_url_input = st.text_input(
        "Backend API URL",
        value=DEFAULT_API_BASE_URL,
        help="Endpoint where your FastAPI backend is running.",
    )

    # API Key Input Box
    api_key_input = st.text_input(
        "API Key (LLM Provider / Backend)",
        value=st.session_state.api_key,
        type="password",
        help="Enter your API key if required by the model backend.",
    )
    st.session_state.api_key = api_key_input

    st.markdown("---")

    # Backend Connection Status Check
    try:
        health = requests.get(
            f"{api_base_url_input}/health",
            headers=_get_headers(),
            timeout=3,
        )
        if health.ok:
            st.success("🟢 Backend connected")
        else:
            st.warning("🟡 Backend reachable, but returned unhealthy status")
    except requests.exceptions.RequestException:
        st.error("🔴 Backend not reachable\n\nStart it with:\n`uvicorn main:app --reload`")

    st.markdown("---")
    if st.button("🔄 Start New Analysis", use_container_width=True):
        _reset_state()
        st.rerun()

# --------------------------------------------------------------------------
# HEADER
# --------------------------------------------------------------------------

st.title("⚖️ Legal Case Analysis & Court Speech Generator")
st.caption(
    "Upload a case document to extract parties, build a chronological timeline, "
    "flag inconsistencies, determine jurisdiction, match precedents, and draft a "
    "formal court speech powered by a LangGraph analysis pipeline."
)

st.divider()

# --------------------------------------------------------------------------
# UPLOAD & CONFIGURATION FORM
# --------------------------------------------------------------------------

col_upload, col_options = st.columns([2, 1], gap="medium")

with col_upload:
    uploaded_file = st.file_uploader(
        "Upload case document",
        type=["pdf", "docx", "txt"],
        help="Accepted formats: PDF, DOCX, TXT",
    )

with col_options:
    client_role = st.radio(
        "Client representation type",
        options=["Plaintiff / Victim", "Defendant / Respondent"],
        help="Which side of the dispute does your client represent?",
    )

run_clicked = st.button("🚀 Run Analysis", type="primary", disabled=uploaded_file is None, use_container_width=True)

if run_clicked and uploaded_file is not None:
    with st.spinner("Running LangGraph legal analysis pipeline — this may take a minute..."):
        try:
            result = _call_analyze_endpoint(api_base_url_input, uploaded_file, client_role)
            st.session_state.analysis_result = result
            st.session_state.file_id = result.get("file_id")
            st.success("Analysis completed successfully!")
        except requests.exceptions.HTTPError as http_err:
            try:
                detail = http_err.response.json().get("detail", str(http_err))
            except Exception:
                detail = str(http_err)
            st.error(f"Analysis failed: {detail}")
        except requests.exceptions.RequestException as req_err:
            st.error(f"Could not reach backend API: {req_err}")

st.divider()

# --------------------------------------------------------------------------
# RESULTS VIEW
# --------------------------------------------------------------------------

result = st.session_state.analysis_result

if result is None:
    st.info("💡 Upload a document above and click **Run Analysis** to generate a legal brief and court speech.")
else:
    fact_sheet = result.get("fact_sheet", {})
    errors = result.get("errors", [])

    if errors:
        with st.expander("⚠️ Processing Warnings", expanded=False):
            for error_message in errors:
                st.warning(error_message)

    jurisdiction = fact_sheet.get("jurisdiction", {})
    st.subheader(
        f"Case Routing: {jurisdiction.get('court_level', 'N/A')} — {jurisdiction.get('court_type', 'N/A')}"
    )

    tab_summary, tab_inconsistencies, tab_jurisdiction, tab_speech = st.tabs(
        ["📄 Summary", "⚠️ Inconsistencies", "🏛️ Jurisdiction & Precedents", "🗣️ Formal Speech"]
    )

    with tab_summary:
        st.markdown("### Executive Summary")
        st.write(fact_sheet.get("executive_summary", "No summary generated."))

        st.markdown("### Party Positions & Dispute Analysis")
        st.write(fact_sheet.get("party_positions", "No party position analysis generated."))

        st.markdown("### Parties Identified")
        parties = fact_sheet.get("parties", [])
        if parties:
            st.dataframe(parties, use_container_width=True, hide_index=True)
        else:
            st.write("No parties identified.")

        st.markdown("### Chronological Timeline")
        timeline = fact_sheet.get("timeline", [])
        if timeline:
            st.dataframe(timeline, use_container_width=True, hide_index=True)
        else:
            st.write("No timeline events extracted.")

    with tab_inconsistencies:
        st.markdown("### Contradiction & Inconsistency Audit")
        inconsistencies = fact_sheet.get("inconsistencies", [])
        if inconsistencies:
            for item in inconsistencies:
                severity = item.get("severity", "Low")
                severity_icon = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}.get(severity, "🟢")
                with st.expander(f"{severity_icon} [{severity}] {item.get('description', '')}"):
                    for statement in item.get("conflicting_statements", []):
                        st.markdown(f"> {statement}")
        else:
            st.write("No inconsistencies or contradictions were flagged.")

    with tab_jurisdiction:
        st.markdown("### Jurisdictional Assessment")
        col_a, col_b = st.columns(2)
        col_a.metric("Court Level", jurisdiction.get("court_level", "N/A"))
        col_b.metric("Estimated Court Fee", jurisdiction.get("estimated_court_fee", "N/A"))

        st.markdown(f"**Court Type:** {jurisdiction.get('court_type', 'N/A')}")
        st.markdown("**Legal Reasoning:**")
        st.write(jurisdiction.get("reasoning", "N/A"))

        st.markdown("**Filing Requirements:**")
        requirements = jurisdiction.get("filing_requirements", [])
        if requirements:
            for req in requirements:
                st.markdown(f"- {req}")
        else:
            st.write("No specific filing requirements specified.")

        st.markdown("### Relevant Precedents")
        precedents = fact_sheet.get("precedents", [])
        if precedents:
            for precedent in precedents:
                support_icon = "✅" if precedent.get("supports_client") else "⚠️"
                st.markdown(
                    f"{support_icon} **{precedent.get('case_name', 'Unnamed')}** "
                    f"— *{precedent.get('citation', 'No citation')}*"
                )
                st.caption(precedent.get("relevance", ""))
        else:
            st.write("No precedents matched.")

    with tab_speech:
        st.markdown("### Formal Court Oral Argument / Speech")
        speech_text = fact_sheet.get("formal_speech", "No speech generated.")
        st.markdown(speech_text)

    st.divider()

    # ----------------------------------------------------------------------
    # EXPORT ACTIONS
    # ----------------------------------------------------------------------

    st.subheader("📥 Export Case Files")
    download_col_1, download_col_2 = st.columns(2)

    file_id = st.session_state.file_id

    if file_id:
        with download_col_1:
            try:
                docx_bytes = _fetch_download_bytes(
                    api_base_url_input,
                    f"/api/download/docx/{file_id}",
                    st.session_state.api_key,
                )
                st.download_button(
                    label="📄 Download Formal Legal Brief (.docx)",
                    data=docx_bytes,
                    file_name=f"legal_brief_{file_id}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            except requests.exceptions.RequestException as exc:
                st.error(f"Could not fetch DOCX file: {exc}")

        with download_col_2:
            try:
                json_bytes = _fetch_download_bytes(
                    api_base_url_input,
                    f"/api/download/json/{file_id}",
                    st.session_state.api_key,
                )
                st.download_button(
                    label="🗂️ Download Fact-Sheet (.json)",
                    data=json_bytes,
                    file_name=f"fact_sheet_{file_id}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            except requests.exceptions.RequestException as exc:
                st.error(f"Could not fetch JSON file: {exc}")
    else:
        st.warning("File ID missing; cannot generate download links.")