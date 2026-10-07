"""Assemble the final submission folder and ZIP.

Usage: python scripts/build_submission.py [OUTPUT_DIR]   (default: dist/)

Folder layout and file naming follow the TechPulse FY-26 assessment guide (section VII):
  UniversityName_StudentName_RegisterNo_CSx_AIML/{Synopsis,Input_Data,Code,Model_Prompts_Config,
  Evaluation_Results,Documentation,Video,Declarations}/   and a ZIP of the whole folder.
Files are named <RegisterNo>_<Artifact>_v<Version>.<ext>.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

REPO = Path(__file__).resolve().parents[1]
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
RERUN = "--rerun" in sys.argv  # regenerate every experiment (slow)
OUT_BASE = Path(ARGS[0]) if ARGS else REPO / "dist"

UNIVERSITY = "AmritaVishwaVidyapeetham"
STUDENT = "AishwaryaManoj"
REG = "CB.SC.U4AIE23211"
CS = "CS1"
VERSION = "1.0"
ROOT_NAME = f"{UNIVERSITY}_{STUDENT}_{REG}_{CS}_AIML"
FULL_NAME, FULL_UNI = "Aishwarya Manoj", "Amrita Vishwa Vidyapeetham"
PY = sys.executable


def fname(artifact: str, ext: str) -> str:
    return f"{REG}_{artifact}_v{VERSION}.{ext}"


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


# ---------------------------------------------------------------------------- documents

ss = getSampleStyleSheet()
H = ParagraphStyle("H", parent=ss["Heading1"], fontSize=15, textColor=colors.HexColor("#17375E"))
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14.5)
C = ParagraphStyle("C", parent=B, fontSize=8.5, leading=11)


def pdf(path: Path, story):
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=18 * mm, bottomMargin=18 * mm, author=FULL_NAME).build(story)


def grid(rows, widths, header=True):
    t = Table([[Paragraph(str(c), C) for c in r] for r in rows], colWidths=[w * mm for w in widths])
    style = [("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E5F3")))
    t.setStyle(TableStyle(style))
    return t


def declarations(dest: Path):
    sig = [Spacer(1, 14 * mm),
           Paragraph("Student signature: ______________________________ &nbsp;&nbsp; Date: ______________", B),
           Spacer(1, 4 * mm),
           Paragraph(f"Name: {FULL_NAME} &nbsp;&nbsp; Register no.: {REG} &nbsp;&nbsp; University: {FULL_UNI}", B)]

    pdf(dest / fname("Academic_Integrity_Declaration", "pdf"), [
        Paragraph("Academic Integrity Declaration", H),
        Paragraph(f"Case study {CS}: AUTOSAR HLD Document Analysis Assistant", B), Spacer(1, 4 * mm),
        Paragraph(f"I, <b>{FULL_NAME}</b> ({REG}), {FULL_UNI}, declare that:", B), Spacer(1, 2 * mm),
        Paragraph("1. This submission is my original work for the stated case study.", B),
        Paragraph("2. All external code, libraries, datasets, pre-trained models and documents used are cited "
                  "(listed below and in the Technical Report).", B),
        Paragraph("3. No results have been fabricated; every metric reported can be reproduced with the "
                  "commands in the README.", B),
        Paragraph("4. My individual contribution is stated accurately: <i>(student to complete: describe which "
                  "parts you designed, wrote, tested and can explain)</i> "
                  "______________________________________________________________", B),
        Spacer(1, 3 * mm),
        Paragraph("<b>External software and models used</b>", B),
        grid([["Component", "Use", "Licence / source"],
              ["BAAI/bge-small-en-v1.5", "Pre-trained embedding model (retrieval)", "MIT, Hugging Face"],
              ["sentence-transformers/all-MiniLM-L6-v2", "Pre-trained embedding model, used only in the retrieval comparison", "Apache-2.0, Hugging Face"],
              ["scikit-learn, joblib, NumPy, matplotlib", "Training and evaluating the answerability classifier, PCA, plots", "BSD / PSF"],
              ["fastembed / ONNX Runtime", "Local embedding inference", "Apache-2.0"],
              ["ChromaDB", "Local vector store", "Apache-2.0"],
              ["PyMuPDF", "PDF parsing and tables", "AGPL-3.0 / commercial"],
              ["Tesseract OCR / pytesseract", "OCR fallback for scanned pages", "Apache-2.0"],
              ["FastAPI, Uvicorn, Pydantic, Streamlit, pandas, httpx", "Service, UI, data handling", "MIT / BSD / Apache-2.0"],
              ["ReportLab", "Synthetic sample HLD and report generation", "BSD"],
              ["vis-network (CDN)", "Interactive graph in the UI", "Apache-2.0 / MIT"]],
             [55, 70, 45]),
        *sig])

    pdf(dest / fname("AI_Tool_Usage_Declaration", "pdf"), [
        Paragraph("AI-Tool Usage Declaration", H),
        Paragraph(f"Case study {CS}: AUTOSAR HLD Document Analysis Assistant. Each AI tool or pre-trained model used, "
                  "including for coding assistance, is declared below. I remain accountable for correctness and can "
                  "explain all submitted work.", B), Spacer(1, 4 * mm),
        grid([["AI tool / model", "Purpose", "Artifact affected", "Verified by student (Y/N)"],
              ["Claude Code (Anthropic Claude models, incl. Claude Sonnet 5.5)",
               "Coding assistant: wrote and refactored code for retrieval (hybrid RAG), validation rules, revision "
               "comparison, reporting, security/audit, API, Streamlit UI and Docker deployment; wrote unit and "
               "integration tests; drafted the evaluation set, technical report generator, declarations and README.",
               "Code/, Evaluation_Results/, Documentation/, Model_Prompts_Config/, Declarations/",
               "____ (student to confirm after review)"],
              ["Claude Code (earlier sessions / earlier components)",
               "<i>Student to state whether the ingestion, chunking, extraction and normalisation modules were written "
               "with or without AI assistance.</i>", "Code/app/ingestion, chunking, extraction", "____"],
              ["BAAI/bge-small-en-v1.5 (pre-trained model, runs locally)",
               "Runtime component: converts chunks and queries to embeddings for retrieval.",
               "RAG layer", "Y (evaluated; see Evaluation_Results)"],
              ["Optional LLM via Ollama or Anthropic API",
               "<b>Not used in the submitted evaluation.</b> Disabled by default; extractive answers are produced "
               "without a generative model.", "None", "N/A"]],
             [40, 60, 40, 30]),
        Spacer(1, 3 * mm),
        Paragraph("Verification performed: all code was run; the automated test suite passes; extraction and Q&amp;A were "
                  "evaluated against hand-written ground truth; the UI was exercised manually and with automated "
                  "screenshots. Generated text in the report was reviewed for factual accuracy against the code and results.", B),
        *sig])


MODEL_CONFIG = f"""# Model, Prompts and Configuration - {CS} AUTOSAR HLD Document Analysis Assistant

Student: {FULL_NAME} ({REG}), {FULL_UNI}. Version {VERSION}, {date.today():%d %B %Y}.

## 1. Models and providers

| Role | Model / provider | Version | Where it runs | Notes |
|---|---|---|---|---|
| Embeddings | BAAI/bge-small-en-v1.5 (384 dimensions) | revision pinned by the fastembed cache baked into the Docker image | Local, CPU, ONNX Runtime through `fastembed` | Query prefix "Represent this sentence for searching relevant passages: " is applied to queries, as recommended for BGE retrieval |
| Answer generation (default) | None - extractive, rule-based composition from retrieved passages and graph facts | n/a | Local | Used for all reported evaluation results |
| Answer generation (optional) | Ollama-hosted local model (default name `llama3.2`, configurable with `LLM_MODEL`) | user-selected | Local | Enabled with `LLM_PROVIDER=ollama`; not part of the evaluation |
| Answer generation (optional, external) | Anthropic API (default `claude-haiku-4-5-20251001`) | n/a | External service | Disabled by default; requires `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`; would have to be declared before any demo |
| OCR | Tesseract (via pytesseract) | system package | Local | Only for pages with fewer than 20 extractable words |

## 2. Vector store and retrieval configuration

| Parameter | Value |
|---|---|
| Vector store | ChromaDB `PersistentClient`, path `data/vectorstore` (override `VECTOR_DIR`) |
| Collections | one per document (`hld_<document_id>`), distance = cosine |
| Chunking | section-aware, 250 words per chunk, 40 words overlap (`CHUNK_SIZE`, `CHUNK_OVERLAP`) |
| Lexical retrieval | BM25 (k1 = 1.5, b = 0.75) with CamelCase and underscore splitting |
| Fusion | reciprocal rank fusion, k = 60 |
| top_k | 8 (API allows 1-50) |
| Fusion weights | lexical 1, dense 10 (tuned on the development documents; held-out MRR 0.869 vs 0.837 equal weights) |
| Answer / refuse decision | trained answerability classifier (section 2b); the old 0.60 cosine gate is only a fallback when no model file exists |

## 2b. Answerability model

| Item | Value |
|---|---|
| Task | binary classification: can this document answer this question? |
| Algorithm | random forest (selected from logistic regression, RBF-SVM, k-NN, decision tree, random forest, gradient boosting) wrapped in sigmoid calibration |
| Features | 12 (see `FEATURE_NAMES` in `app/rag/hybrid.py`): similarity statistics, BM25 scores, vocabulary coverage, retriever agreement, entity matches |
| Training data | 288 labelled questions from 6 development documents (`data/evaluation/answerability_dataset.csv`) |
| Validation | nested leave-one-document-out CV (inner 5-fold grouped grid search) |
| Decision threshold | chosen on out-of-fold predictions to maximise F1 (stored in metadata) |
| Artefact | `models/answerability/v1.0.0/` (also `current/`): `model.joblib` + `metadata.json` with hyper-parameters, training/test documents, dataset hash, git commit, metrics |
| Reproduce | `python -m app.evaluation.train_answerability` |

## 3. Prompts

The default pipeline uses no generative prompt. When an optional LLM provider is enabled, this exact template is sent
(`app/rag/answerer.py`, `GroundedAnswerer._llm_answer`); retrieved text is inserted as delimited evidence:

```
Answer the engineering question using ONLY the evidence below. Cite evidence as [C1], [C2]. If the evidence does not
contain the answer, reply exactly: "The requested information was not found in the document."

EVIDENCE
[C1] (section: <section>, page <n>)
<chunk text>
...

STRUCTURED FACTS
- <source> <relationship> <target> (page <n>)
...

QUESTION: <user question>
```

Generation settings for Ollama: temperature 0. For the Anthropic path: `max_tokens` 700.

## 4. Tools and components

| Tool | Purpose |
|---|---|
| PyMuPDF | text, headings and table extraction with page numbers |
| Deterministic extractors (regex plus table parsing) | components, interfaces, ports, signals, dependencies, functional flows with confidence and evidence |
| `StructuredModel` | typed records parsed from the HLD tables, shared by graph, validation and comparison |
| `ValidationEngine` | 11 rules V001-V011 with severity, confidence and page evidence |
| `ArchitectureGraph` | in-memory property graph with neighbour and impact (BFS) queries |
| `compare_models` | revision diff and change-impact set |
| Report generators | document report, component report, structured JSON/CSV export |
| Security | API-key auth, roles (viewer, reviewer, admin), project isolation, audit log in SQLite |

## 5. Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | embedding model name |
| `EMBEDDINGS_ENABLED` | `true` | `false` falls back to BM25 only |
| `VECTOR_DIR` | `data/vectorstore` | vector store location |
| `LLM_PROVIDER` | `local` | `local` (extractive), `ollama`, `anthropic` |
| `LLM_MODEL` | empty | model name for the optional LLM |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `AUTH_ENABLED` / `API_KEYS` | `false` / empty | `key:role:name[:projectA|projectB]` entries separated by commas |
| `DATABASE_URL` | `sqlite:///./data/autosar.db` | SQLite file |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 250 / 40 | chunking |
| `MAX_UPLOAD_MB` | 100 | upload size limit |

## 6. Software versions (development machine)

Python 3.14 (Docker image uses Python 3.12), fastapi 0.142, uvicorn 0.54, streamlit 1.65, pymupdf 1.28,
chromadb 1.5, fastembed 0.8, onnxruntime 1.30, pydantic 2.13, httpx 0.28, pandas 3.0, pytest 9.1.
See `requirements.txt` in Code/ for the dependency list.

## 7. Reproduce

```bash
pip install -r requirements-dev.txt
pytest
python -m app.evaluation.run_eval --out data/evaluation/results
docker compose up --build        # API :8000, UI :8501
```
"""

VIDEO_SCRIPT = f"""# Video demonstration script (target 8-9 minutes, limit 5-10)

Student: {FULL_NAME} ({REG}). Record the screen with narration; show the application running from the submitted code.
Declare before the demo: no external API is used (LLM_PROVIDER=local; embeddings run locally after the one-time model download).

| Time | Show | Say |
|---|---|---|
| 0:00-0:45 | Title slide / README | Problem: HLDs are long PDFs; manual review misses mismatches. CS1 goals and users. |
| 0:45-1:30 | `Input_Data/`: open sample_hld.pdf | Synthetic Body Control System HLD, 3 pages: tables for components, interfaces, ports, signals, dependencies, flows. Revision 2 adds ClimateControl and seeded defects. |
| 1:30-2:30 | Architecture diagram (report Figure 1) and workflow (Figure 2) | Streamlit + FastAPI + BGE embeddings + ChromaDB + SQLite; hybrid BM25 + vector retrieval; deterministic extraction; rule-based validation. |
| 2:30-3:30 | UI > Documents: upload sample_hld.pdf (label v1) | Parsing, chunking, extraction, indexing, validation; point out the entity and finding counts. |
| 3:30-4:30 | Architecture tab: graph, filters, impact explorer on IDoorStatus; component report for WindowControl | Traceability: who provides/requires what, signals and ports, impact within N hops; every line cites a page. |
| 4:30-6:00 | Ask tab: "Which component provides IDoorStatus?", "How does the window controller learn the requested window position?", then "What is the maximum engine torque?" | Grounded answers with citations and confidence; open a citation; the last question is refused rather than guessed. |
| 6:00-7:00 | Upload sample_hld_v2.pdf (v2) > Validation tab > accept one finding > Compare tab | V003/V004/V005/V009 found with page evidence; human review; the diff shows 10 changes and impacted elements. |
| 7:00-7:40 | Report tab: download Markdown, JSON and CSV exports | Structured export for downstream tools. |
| 7:40-8:30 | Terminal: `pytest`, then show `Evaluation_Results` figures (nested-CV ROC, learning curve, retrieval comparison, confusion matrix) | The answerability classifier was chosen by nested leave-one-document-out CV; compare it with the old threshold; show the independent question set and the failures. State plainly that data are synthetic and test sets are small. |
| 8:30-9:00 | Responsible AI and limitations | Grounding, human review, RBAC and audit log, local data; limits: single table layout, small benchmark, no LLM evaluated. |

## Before recording
1. Start the app (`docker compose up --build`), open http://localhost:8501, delete old documents.
2. Pre-download the embedding model once (first run) so the demo works offline.
3. Have `sample_hld.pdf` and `sample_hld_v2.pdf` ready in `Input_Data/`.
4. If you enable authentication for the demo, enter the API key in the Access box first.
"""

SYNOPSIS_README = f"""# Synopsis

Place the **faculty-approved project synopsis and approval record** for {CS} here, named
`{REG}_Synopsis_v1.0.pdf` (and `{REG}_Faculty_Approval_v1.0.pdf` if the approval is a separate document).

This folder is intentionally empty: the synopsis and the approval must come from your faculty guide and cannot be
generated for you. The evaluation checklist requires that the approved synopsis matches the submitted project scope.
"""

INPUT_README = """# Input data

All input data is synthetic. No confidential, customer or proprietary content is used.

| File | Description |
|---|---|
| sample_hld.pdf | Body Control System HLD, revision 1.0 (3 pages). Consistent by design. |
| sample_hld_v2.pdf | Revision 2.0: adds ClimateControl, IClimateState, CabinTemperature; widens VehicleSpeed to uint32; two seeded defects (WindowCommand_In declared as P-PORT, one missing dependency). |
| generate_sample_hld.py / generate_sample_hld_v2.py | ReportLab scripts that regenerate the two PDFs. |

Structure of the HLD: 1 System Overview, 2 Software Architecture, 3 Software Components (table), 4 Interfaces (table),
5 Ports (table), 6 Signals (table), 7 Dependencies (table), 8 Functional Flows, 9 Integration Constraints,
10 Engineering Traceability. Ground truth and the question set are in `Evaluation_Results/`.
"""

ROOT_README = f"""# {ROOT_NAME}

Capstone submission for **{CS}: AUTOSAR HLD Document Analysis Assistant**
Student: {FULL_NAME} | Register no.: {REG} | {FULL_UNI} | Version {VERSION}

| Folder | Contents |
|---|---|
| Synopsis/ | Faculty-approved synopsis and approval record (to be added by the student) |
| Input_Data/ | Synthetic sample HLD revisions and generators |
| Code/ | Application source, tests, Docker files, README |
| Model_Prompts_Config/ | Models, embeddings, vector store, prompts, tools and settings |
| Evaluation_Results/ | Ground truth, question set, metrics, sample outputs with citations, test log |
| Documentation/ | Technical report (PDF) |
| Video/ | Demonstration video (to be recorded) and the script |
| Declarations/ | Academic-integrity and AI-tool-usage declarations (to be signed) |

## Run
```bash
cd Code
docker compose up --build        # UI http://localhost:8501, API http://localhost:8000/docs
# or, without Docker (Python 3.11+):
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000
API_URL=http://localhost:8000 streamlit run frontend/app.py
pytest                           # automated tests
python -m app.evaluation.run_eval --out data/evaluation/results
```
The first run downloads the BGE-small embedding model (about 130 MB) unless the Docker image is used.
Demo flow: Documents > Load sample HLD, then Architecture, Ask, Validation; upload `sample_hld_v2.pdf` and use Compare.
"""


def sample_outputs(results: dict) -> str:
    lines = ["# Sample outputs with citations", "",
             "Generated by `python -m app.evaluation.run_eval` from the sample HLD. "
             "Citation format: [id] section, page.", ""]
    for r in results["qa"]["results"]:
        lines += [f"## {r['id']} ({r['category']}): {r['question']}", "",
                  f"- Result: {'PASS' if r['passed'] else 'FAIL'} | grounded: {r['grounded']} | "
                  f"confidence: {r['confidence']}",
                  "- Citations: " + ("; ".join(f"[{c['id']}] {c['section']}, page {c['page']}"
                                              for c in r["citations"]) or "none (refused)"),
                  "", "```", r["answer"], "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------- build

def main():
    root = OUT_BASE / ROOT_NAME
    if root.exists():
        shutil.rmtree(root)
    dirs = {n: root / n for n in ["Synopsis", "Input_Data", "Code", "Model_Prompts_Config",
                                  "Evaluation_Results", "Documentation", "Video", "Declarations"]}
    for d in dirs.values():
        d.mkdir(parents=True)

    print("running tests ...")
    tests = run([PY, "-m", "pytest", "-q"])
    summary = re.findall(r"(\d+) passed", tests.stdout)
    passed = summary[-1] if summary else "?"
    (dirs["Evaluation_Results"] / fname("Pytest_Output", "txt")).write_text(
        tests.stdout + tests.stderr, encoding="utf-8")
    if tests.returncode != 0:
        sys.exit("tests failed; fix them before building the submission")

    if RERUN:
        for step in (["-m", "app.evaluation.extraction_eval", "--label", "after_fix", "--out", "data/evaluation/results"],
                     ["-m", "app.evaluation.train_answerability"], ["-m", "app.evaluation.retrieval_experiments"],
                     ["-m", "app.evaluation.validation_eval", "--out", "data/evaluation/results"], ["-m", "app.evaluation.eda"]):
            print("re-running", step[1], "...")
            out = run([PY, *step])
            if out.returncode != 0:
                sys.exit(f"{step[1]} failed:\n{out.stderr[-1500:]}")
    print("running evaluation ...")
    res_dir = REPO / "data/evaluation/results"
    ev = run([PY, "-m", "app.evaluation.run_eval", "--out", str(res_dir)])
    if ev.returncode != 0:
        print("note: some evaluation questions fail (expected; see Evaluation_Results)")
    results = json.loads((res_dir / "results.json").read_text(encoding="utf-8"))

    er = dirs["Evaluation_Results"]
    for src, artifact, ext in [("answerability_report.json", "Answerability_Model_Report", "json"),
                               ("retrieval_experiments.json", "Retrieval_Experiments", "json"),
                               ("validation_eval.json", "Validation_Rules_Evaluation", "json"),
                               ("eda_summary.json", "EDA_Summary", "json"),
                               ("extraction_corpus_before_fix.json", "Extraction_Before_Fixes", "json"),
                               ("extraction_corpus_after_fix.json", "Extraction_After_Fixes", "json")]:
        shutil.copy(res_dir / src, er / fname(artifact, ext))
    shutil.copy(REPO / "data/evaluation/answerability_dataset.csv", er / fname("Answerability_Dataset", "csv"))
    shutil.copy(REPO / "data/evaluation/runs.jsonl", er / fname("Experiment_Log", "jsonl"))
    shutil.copy(REPO / "data/evaluation/qa_set_independent.json", er / fname("QA_Independent_Set", "json"))
    shutil.copytree(REPO / "data/evaluation/figures", er / "Figures")
    shutil.copy(res_dir / "results.json", er / fname("Evaluation_Metrics", "json"))
    shutil.copy(res_dir / "results.md", er / fname("Evaluation_Summary", "md"))
    shutil.copy(REPO / "data/evaluation/qa_set.json", er / fname("QA_Ground_Truth", "json"))
    shutil.copy(REPO / "data/evaluation/ground_truth_entities.json", er / fname("Entity_Ground_Truth", "json"))
    (er / fname("Sample_Outputs_With_Citations", "md")).write_text(sample_outputs(results), encoding="utf-8")

    print("building technical report ...")
    rep = dirs["Documentation"] / fname("Technical_Report", "pdf")
    r = run([PY, "scripts/make_report.py", str(rep), passed])
    if r.returncode != 0:
        sys.exit("report build failed:\n" + r.stderr[-1500:])
    shots = REPO / "submission_assets/screenshots"
    if shots.exists():
        shutil.copytree(shots, dirs["Documentation"] / "Screenshots")

    print("copying code and data ...")
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.db", "uploads",
                                    "vectorstore", "results", ".git", "dist", "submission_assets")
    code = dirs["Code"]
    for item in ["app", "frontend", "scripts", "tests"]:
        shutil.copytree(REPO / item, code / item, ignore=ignore)
    (code / "data").mkdir()
    shutil.copytree(REPO / "data/sample", code / "data/sample")
    shutil.copytree(REPO / "data/evaluation", code / "data/evaluation", ignore=ignore)
    for f in ["Dockerfile", "docker-compose.yml", "render.yaml", "requirements.txt", "requirements-dev.txt",
              "README.md", "pytest.ini", ".env.example", ".dockerignore"]:
        if (REPO / f).exists():
            shutil.copy(REPO / f, code / f)
    shutil.copy(REPO / "scripts/capture_screenshots.py", code / "scripts" / "capture_screenshots.py")
    shutil.copytree(shots, code / "submission_assets" / "screenshots") if shots.exists() else None

    inp = dirs["Input_Data"]
    for f in ["sample_hld.pdf", "sample_hld_v2.pdf"]:
        shutil.copy(REPO / "data/sample" / f, inp / f)
    for f in ["generate_sample_hld.py", "generate_sample_hld_v2.py"]:
        shutil.copy(REPO / "scripts" / f, inp / f)
    (inp / "README_Input_Data.md").write_text(INPUT_README, encoding="utf-8")

    import submission_docs

    docs_dir = dirs["Documentation"]
    (docs_dir / fname("Rubric_Self_Assessment", "md")).write_text(submission_docs.rubric_self_assessment(REG, passed), encoding="utf-8")
    (docs_dir / fname("Technical_QA_Preparation", "md")).write_text(submission_docs.qa_prep(REG), encoding="utf-8")
    shutil.copytree(REPO / "models", dirs["Model_Prompts_Config"] / "models")
    shutil.copytree(REPO / "models", code / "models")
    shutil.copytree(REPO / "data/synthetic", code / "data/synthetic")
    shutil.copytree(REPO / "data/synthetic", inp / "synthetic")
    shutil.copy(REPO / "scripts/generate_synthetic_hlds.py", inp / "generate_synthetic_hlds.py")
    shutil.copy(REPO / "requirements-lock.txt", code / "requirements-lock.txt")
    (dirs["Model_Prompts_Config"] / fname("Model_Prompts_Config", "md")).write_text(MODEL_CONFIG, encoding="utf-8")
    (dirs["Video"] / fname("Video_Script", "md")).write_text(VIDEO_SCRIPT, encoding="utf-8")
    (dirs["Video"] / "PLACE_VIDEO_HERE.txt").write_text(
        f"Record the demo (5-10 min) and save it here as {REG}_Demo_Video_v{VERSION}.mp4\n", encoding="utf-8")
    (dirs["Synopsis"] / "README.md").write_text(SYNOPSIS_README, encoding="utf-8")
    (root / "README.md").write_text(ROOT_README, encoding="utf-8")
    declarations(dirs["Declarations"])
    (dirs["Declarations"] / "SIGN_BEFORE_SUBMITTING.txt").write_text(
        "Print, complete the blanks, sign and date both declarations, then replace the PDFs here with the "
        "signed scans (same file names plus _signed). Unsigned submissions are not evaluated.\n", encoding="utf-8")

    archive = shutil.make_archive(str(OUT_BASE / ROOT_NAME), "zip", OUT_BASE, ROOT_NAME)
    print("folder:", root)
    print("zip   :", archive)


if __name__ == "__main__":
    main()
