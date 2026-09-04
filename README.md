# Legal Case Analysis & Court Speech Generation System

FastAPI + LangGraph backend, Streamlit frontend.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."          # required by state_graph.py
# optional: export LEGAL_LLM_MODEL="gpt-4o"   (defaults to gpt-4o)
```

## Run

Terminal 1 — backend:
```bash
uvicorn main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
streamlit run app.py
```

Open the Streamlit URL it prints (usually http://localhost:8501).

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app: `/api/analyze`, `/api/download/docx/{id}`, `/api/download/json/{id}` |
| `state_graph.py` | LangGraph `StateGraph` with 4 nodes: parse → extract timeline/parties → jurisdiction/precedent → draft |
| `document_builder.py` | Builds the 6-section `.docx` legal brief and `.json` fact sheet with `python-docx` |
| `app.py` | Streamlit UI: upload, run analysis, preview tabs, two download buttons |
| `requirements.txt` | All dependencies |

## Notes

- Uploaded files are written to `./uploads/`; generated briefs/fact-sheets go to `./output/` (both auto-created).
- The pipeline calls OpenAI via `langchain-openai`'s structured output (`with_structured_output`), so responses are parsed into typed Pydantic schemas rather than raw-string JSON parsing.
- `JurisdictionAndPrecedentNode` cross-checks the LLM's fee estimate against a small static fee schedule (`_COURT_FEE_SCHEDULE`) as a sanity reference — replace this with your real jurisdiction's fee rules before production use.
- The in-memory `_JOB_REGISTRY` in `main.py` is for demo purposes; swap in a real database (Postgres, Redis, etc.) for persistence across restarts.
- This tool drafts *materials for a licensed attorney's review* — it does not replace legal judgment, and generated precedents/fees should be verified before filing.
