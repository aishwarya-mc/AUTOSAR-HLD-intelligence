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
| Hybrid RAG: BGE embeddings + ChromaDB + BM25, cited Q&A, refuses when evidence is missing | `app/rag` |
| Consistency validation (11 rules, severity + evidence, human review workflow) | `app/validation` |
| Revision comparison with impact analysis | `app/comparison` |
| Document and per-component cited reports; JSON/CSV structured export | `app/reporting`, `app/api/export.py` |
| API-key auth, roles (viewer/reviewer/admin), project isolation, audit log | `app/core/security.py`, `app/api` |
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
pytest                              # 34 tests
python -m app.evaluation.run_eval --out data/evaluation/results   # extraction P/R + 32-question Q&A metrics
```

## Deploy

### Docker Compose (any VM / server)

```bash
docker compose up --build -d
# API  -> http://<host>:8000/docs      UI -> http://<host>:8501
```

Data persists in the `hld-data`, `hld-uploads` and `hld-vectors` volumes. The BGE embedding model is
baked into the image, so the stack runs offline. Authentication is off by default; enable it with
`AUTH_ENABLED=true API_KEYS="key:role:name[:projectA|projectB],..." docker compose up -d` and enter the key
in the UI's **Access** box. For LLM-phrased answers set `LLM_PROVIDER=ollama` (local, preferred) or
`LLM_PROVIDER=anthropic` with `ANTHROPIC_API_KEY` (external API: declare it before a demo); the LLM only
rewrites retrieved evidence. Without either, answers are extractive and fully local.

### One-click: Render (free tier, single container)

1. Sign in at https://render.com with GitHub, then **New + → Blueprint** and pick this repository.
2. Render reads `render.yaml` and builds the `Dockerfile`; `scripts/start_single.sh` runs the API
   (private) and the UI (public) in one container. Open the service URL when the deploy is live.
3. Free instances sleep when idle and have no persistent disk, so uploaded documents reset on restart.
   Use the sample HLD for demos, or add a paid disk mounted at `/srv/data/db`.

### Managed hosts (Railway, Fly.io, Azure Container Apps…)

Deploy the same `Dockerfile` as two services: the API (default `CMD`, port 8000) and the UI
(start command `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0`)
with `API_URL` pointing at the API's public URL. Mount a persistent disk at `/srv/data/db`
and set `DATABASE_URL=sqlite:////srv/data/db/autosar.db`.

## Design notes and limitations

- **Retrieval** is hybrid: BM25 (exact identifiers such as `IDoorStatus`) fused with BGE-small vector search in
  ChromaDB (one collection per document) using reciprocal rank fusion. A relevance gate (best cosine similarity
  >= 0.60) makes off-topic questions return "not found" instead of a guess. Thresholds were calibrated on the
  sample HLD; re-calibrate for other corpora. Set `EMBEDDINGS_ENABLED=false` for a BM25-only fallback.
- **Extraction** is deterministic (regex + table parsing), so every entity carries exact page/section evidence.
- **Validation** is rule-based (V001-V011); findings are advisory and reviewable (accept / reject / needs review).
- **Graph**: the traceability graph is built in memory from the HLD tables (Neo4j is not used).
- **LLM**: not required for the reported results; optional local (Ollama) or external (Anthropic) providers are untested in the evaluation.
- **Security**: static API keys with roles and project isolation plus an audit log (`GET /audit`, admin). There is no SSO/IAM integration.
- The table parser expects the sample HLD's table layout (Component/Role, Interface/Provider/Consumer,
  Component/Port/Direction/Interface, Signal/Data Type/Source/Destination, Source/Relationship/Target/Reason).
  Real-world HLDs with different headers need extra mappings in `app/extraction/structured_model.py`.
- OCR needs the `tesseract` binary (included in the Docker image) and is only used for low-text pages; it was not evaluated on real scans.
- The evaluation benchmark is small and synthetic; it shows the pipeline works end to end, not real-world accuracy.

## Submission package

`python scripts/build_submission.py` builds the folder and ZIP required by the assessment guide
(`dist/AmritaVishwaVidyapeetham_AishwaryaManoj_CB.SC.U4AIE23211_CS1_AIML/`), including the technical
report PDF, evaluation results, model/prompt configuration and declaration templates.
