# AUTOSAR HLD Intelligence & Traceability Platform

Evidence-grounded analysis of AUTOSAR High-Level Design (HLD) documents
(Tata Technologies Case Study 1: *AUTOSAR HLD Document Analysis Assistant*).

## What it does

| Capability | Where |
|---|---|
| PDF ingestion, table parsing, OCR fallback | `app/ingestion` |
| Section-aware chunking with page evidence | `app/chunking` |
| Entity extraction (components, interfaces, ports, signals, dependencies, flows) + dedup | `app/extraction` |
| Typed model of the HLD tables + traceability graph + change-impact | `app/extraction/structured_model.py`, `app/graph` |
| Natural-language Q&A with citations; refuses when evidence is missing | `app/rag` |
| Consistency validation (11 rules, severity + evidence, human review workflow) | `app/validation` |
| Revision comparison with impact analysis | `app/comparison` |
| Markdown engineering reports | `app/reporting` |
| REST API (FastAPI) and UI (Streamlit) | `app/api`, `frontend` |

## Run locally

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000                 # API docs: http://localhost:8000/docs
API_URL=http://localhost:8000 streamlit run frontend/app.py   # UI: http://localhost:8501
```

Use **Documents → Load sample HLD**. To demo comparison and validation, also upload
`data/sample/sample_hld_v2.pdf` (revision 2 with a new component and seeded defects;
regenerate with `python scripts/generate_sample_hld_v2.py`).

```bash
pytest                              # 24 tests
python -m app.evaluation.run_eval   # Q&A evaluation set (data/evaluation/qa_set.json)
```

## Deploy

### Docker Compose (any VM / server)

```bash
docker compose up --build -d
# API  -> http://<host>:8000/docs      UI -> http://<host>:8501
```

Data persists in the `hld-data` / `hld-uploads` volumes. Set `ANTHROPIC_API_KEY` and
`LLM_PROVIDER=anthropic` in the environment to have an LLM phrase answers (it is still
restricted to the retrieved evidence); without them the system runs fully offline.

### Managed hosts (Render, Railway, Fly.io, Azure Container Apps…)

Deploy the same `Dockerfile` as two services: the API (default `CMD`, port 8000) and the UI
(start command `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0`)
with `API_URL` pointing at the API's public URL. Mount a persistent disk at `/srv/data/db`
and set `DATABASE_URL=sqlite:////srv/data/db/autosar.db`.

## Design notes and deviations from the original plan

- **Retrieval** is BM25 over section-aware chunks (deterministic, no GPU, auditable). BGE
  embeddings + ChromaDB can be added behind `app/rag/retriever.py`; they were left out so the
  deployed image stays small. The same applies to Neo4j: the traceability graph is built in
  memory from the HLD tables, which is sufficient at HLD scale.
- **Extraction** is deterministic (regex + table parsing), so every entity carries exact
  page/section evidence. The flow-title splitter has a fallback but was tuned on the sample HLD.
- **Validation** is rule-based; findings are advisory and reviewable (accept / reject / needs review).
- The table parser expects the sample HLD's table layout (Component/Role, Interface/Provider/Consumer,
  Component/Port/Direction/Interface, Signal/Data Type/Source/Destination, Source/Relationship/Target/Reason).
  Real-world HLDs with different table headers will need extra mappings in `structured_model.py`.
- OCR needs the `tesseract` binary (included in the Docker image); it is only used for low-text pages.
- Authentication is not implemented; put the deployment behind your organisation's gateway/VPN.
