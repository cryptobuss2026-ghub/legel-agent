import json
import os
import uuid
import streamlit as st
from dotenv import load_dotenv

# Direct in-memory execution imports (No FastAPI/Uvicorn HTTP server required)
from state_graph import run_case_pipeline
from document_builder import save_case_outputs

load_dotenv()

UPLOAD_DIR = os.environ.get("LEGAL_UPLOAD_DIR", "uploads")
OUTPUT_DIR = os.environ.get("LEGAL_OUTPUT_DIR", "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.set_page_config(
    page_title="Legal Case Analysis & Court Speech Generator",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# --------------------------------------------------------------------------

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "file_id" not in st.session_state:
    st.session_state.file_id = None
if "output_paths" not in st.session_state:
    st.session_state.output_paths = None
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("OPENAI_API_KEY", "")


def _reset_state() -> None:
    """Clear session analysis context."""
    st.session_state.analysis_result = None
    st.session_state.file_id = None
    st.session_state.output_paths = None


def _call_analyze_pipeline(uploaded_file, client_role: str) -> dict:
    """Run analysis directly in Python using the user's input API key."""
    if st.session_state.api_key:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key

    file_id = uuid.uuid4().hex
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    saved_upload_path = os.path.join(UPLOAD_DIR, f"{file_id}{extension}")

    # Save uploaded file locally
    with open(saved_upload_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    # 1. Run LangGraph pipeline directly
    final_state = run_case_pipeline(
        file_path=saved_upload_path,
        file_name=uploaded_file.name,
        client_role=client_role,
        file_id=file_id,
    )

    # 2. Generate output DOCX and JSON documents
    output_paths = save_case_outputs(final_state)

    # 3. Load generated fact sheet JSON
    with open(output_paths["json_path"], "r", encoding="utf-8") as json_file:
        fact_sheet = json.load(json_file)

    st.session_state.output_paths = output_paths

    return {
        "file_id": file_id,
        "status": final_state.get("status", "unknown"),
        "errors": final_state.get("errors", []),
        "fact_sheet": fact_sheet,
    }


# --------------------------------------------------------------------------
# SIDEBAR: CONFIGURATION & KEYS
# --------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Settings & Credentials")
    
    # Force a unique widget key and force the display value to empty string unless typed
    api_key_input = st.text_input(
        "API Key (OpenAI / LLM Provider)",
        value="",
        type="password",
        key="client_entered_api_key",
        placeholder="sk-...",
        help="Enter your OpenAI API key to run analysis.",
    )
    
    # Store the entered key (or fallback to empty)
    st.session_state.api_key = api_key_input
    
    # Inject into environment immediately if provided
    if api_key_input:
        os.environ["OPENAI_API_KEY"] = api_key_input

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
        type=[".pdf", ".docx", ".doc", ".txt"],
        help="Accepted formats: PDF, DOCX, DOC, TXT",
    )

with col_options:
    client_role = st.radio(
        "Client representation type",
        options=["Plaintiff / Victim", "Defendant / Respondent"],
        help="Which side of the dispute does your client represent?",
    )

run_clicked = st.button(
    "🚀 Run Analysis",
    type="primary",
    disabled=uploaded_file is None,
    use_container_width=True,
)

if run_clicked and uploaded_file is not None:
    if not st.session_state.api_key:
        st.error("Please enter your OpenAI API Key in the sidebar to proceed.")
    else:
        with st.spinner("Running LangGraph legal analysis pipeline — this may take a minute..."):
            try:
                result = _call_analyze_pipeline(uploaded_file, client_role)
                st.session_state.analysis_result = result
                st.session_state.file_id = result.get("file_id")
                st.success("Analysis completed successfully!")
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")

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

    output_paths = st.session_state.output_paths or {}
    file_id = st.session_state.file_id

    docx_path = output_paths.get("docx_path")
    json_path = output_paths.get("json_path")

    with download_col_1:
        if docx_path and os.path.exists(docx_path):
            with open(docx_path, "rb") as f:
                st.download_button(
                    label="📄 Download Formal Legal Brief (.docx)",
                    data=f.read(),
                    file_name=f"legal_brief_{file_id}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
        else:
            st.warning("DOCX file not found.")

    with download_col_2:
        if json_path and os.path.exists(json_path):
            with open(json_path, "rb") as f:
                st.download_button(
                    label="🗂️ Download Fact-Sheet (.json)",
                    data=f.read(),
                    file_name=f"fact_sheet_{file_id}.json",
                    mime="application/json",
                    use_container_width=True,
                )
        else:
            st.warning("JSON file not found.")
