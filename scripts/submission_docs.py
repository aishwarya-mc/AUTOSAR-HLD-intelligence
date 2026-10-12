"""Text for the rubric self-assessment and the technical Q&A preparation notes (used by build_submission.py)."""
import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "data/evaluation/results"


def _n():
    ans = json.loads((RES / "answerability_report.json").read_text(encoding="utf-8"))
    res = json.loads((RES / "results.json").read_text(encoding="utf-8"))
    ret = json.loads((RES / "retrieval_experiments.json").read_text(encoding="utf-8"))
    val = json.loads((RES / "validation_eval.json").read_text(encoding="utf-8"))
    ext = json.loads((RES / "extraction_corpus_after_fix.json").read_text(encoding="utf-8"))
    before = json.loads((RES / "extraction_corpus_before_fix.json").read_text(encoding="utf-8"))
    return ans, res, ret, val, ext, before


def contribution_statement(reg: str) -> str:
    return f"""# Contribution Statement

Student: Aishwarya Manoj ({reg}), Amrita Vishwa Vidyapeetham. Case study CS1: AUTOSAR HLD Document Analysis Assistant.

This statement separates the work done by the student from the work done with AI assistance (Claude Code, Anthropic Claude
models). The student's authorship of the modules in column 2 is the student's own statement; the git history of the repository
(commits "establish project foundation", "implement document ingestion pipeline", "implement architecture entity extraction",
"normalize and deduplicate architecture entities") shows when they were created. The student directed all the AI-assisted work,
reviewed it, ran it and is accountable for it.

| Area | Student (Aishwarya Manoj) | AI assistance (Claude Code), directed and reviewed by the student |
|---|---|---|
| Project scope and plan | Chose case study CS1; defined objectives, users and the technology stack (FastAPI, Streamlit, vector store, SQLite, Docker); set the repository structure | Followed the student's plan; aligned the work to the guide and rubric the student supplied |
| Foundation | Configuration and settings, logging, error types, data schemas, FastAPI application skeleton | Added settings for new features (embeddings, authentication, model paths) |
| Document ingestion | PDF parsing (text, headings, tables), OCR fallback, file validation, metadata, ingestion service | Fixed the OCR trigger (only scanned pages); made the OCR import optional |
| Chunking | Section-aware chunker with deterministic chunk ids and page evidence | Reduced the default chunk size to fit the embedding model |
| Entity extraction | Extractors for components, interfaces, ports, signals, dependencies and functional flows; extraction orchestrator | Found by held-out testing and fixed: table-driven extraction for signals and other entities, flow-title parsing, interface pattern |
| Normalisation and deduplication | Entity normaliser and evidence-preserving de-duplication, with unit tests | None |
| Sample data | Synthetic sample HLD and its generator script | Second revision with seeded defects; nine more synthetic HLDs, ground truth and defect variants |
| Typed table model, graph, impact analysis | Reviewed | Implemented |
| Retrieval and Q&amp;A | Reviewed; chose the stack | BGE embeddings, ChromaDB store, BM25, weighted fusion, grounded answerer |
| Answerability model and ML experiments | Reviewed and ran the experiments; decides which results to report | Dataset generator, nested cross-validation, six-model comparison, calibration, PCA and retrieval experiments, EDA |
| Validation rules and revision comparison | Reviewed | Eleven rules, seeded-defect evaluation, revision diff and impact |
| API, security, audit, export | Reviewed | Routes, roles, project isolation, audit log, JSON/CSV export, component reports |
| Streamlit UI | Reviewed and tested | Implemented |
| Tests, CI, Docker, deployment config | Ran and verified | Unit and integration tests, Dockerfile, compose, CI workflow, Render blueprint |
| Evaluation, report and submission package | Supplied the guide and rubric, directed the work, reviews and submits; writes the personal reflection | Evaluation scripts, technical report, declarations, model/prompt configuration, video script, submission builder |

## Summary
- **Student:** project definition and direction, and the core pipeline that everything else builds on: foundation, ingestion,
  chunking, entity extraction, normalisation and deduplication, the sample HLD generator, and their tests.
- **AI-assisted, student-directed:** retrieval and embeddings, the trained model and experiments, validation, comparison,
  security, API, UI, deployment, evaluation and documentation.

## Accountability
The student has run the system, reviewed the AI-assisted work and can explain every module in the submission. Where the
two columns overlap (for example fixes inside the student's extractors), the AI-assisted change is the bug fix described in the
second column and the original module is the student's.

Student signature: ______________________________ Date: ______________
"""


def rubric_self_assessment(reg: str, tests: str) -> str:
    ans, res, ret, val, ext, before = _n()
    tm, rb = ans["test_metrics"], ans["rule_baseline_test"]
    ind = res["independent"]["trained"]
    tuned = next(k for k in ret["approaches"] if "tuned" in k)
    return f"""# Rubric self-assessment (evidence checklist)

Student: Aishwarya Manoj ({reg}). This maps each criterion of the 100-mark rubric to the evidence in the submission and states
the known gaps honestly. It is a preparation aid, not a score claim; the Applied AI/ML Project Evaluation Workbook is the
authoritative instrument.

| # | Criterion (marks) | Evidence | Known gaps / weaker points |
|---|---|---|---|
| 1 | Problem understanding and industrial context (5) | Report s.1: problem, users, scope, measurable success criteria with measured results | No interview with real AUTOSAR users; value estimate (review time saved) not measured |
| 2 | AI/ML fundamentals and approach selection (5) | Report s.4: alternatives compared with numbers (regex vs tables, BM25/TF-IDF/MiniLM/BGE/hybrid, threshold vs classifier); learning types stated | Local LLM generation compared only by argument, not measured |
| 3 | Dataset understanding, preprocessing and EDA (15) | Report s.2-3, `eda_summary.json`, figures; 11 documents, 528 labelled questions; artefact cleaning (203 wrapped cells), OCR trigger fix, class balance, correlation, leakage checks (document-disjoint splits) | Data are synthetic and templated, single layout; no real-world HLD |
| 4 | Feature engineering, selection, dimensionality reduction (8) | Report s.6: CamelCase tokeniser ablation, 12 engineered features, permutation importance, leave-one-feature-out ablation, PCA on features and on embeddings with downstream results | PCA gave no accuracy gain (reported honestly); small corpus limits embedding PCA |
| 5 | Model development with taught techniques (18) | Report s.7: BM25, TF-IDF, two embedding models, hybrid; six classifier families (logistic regression, SVM, k-NN, decision tree, random forest, gradient boosting) with grids; calibrated final model | Confirm that these techniques match your syllabus; if a taught technique is missing (for example a neural network) add it to `SEARCH_SPACES` in `train_answerability.py` |
| 6 | Evaluation, validation, optimisation (15) | Report s.8: nested leave-one-document-out CV, train vs validation gap, learning curve, calibration, confusion matrix, per-category and per-document results, error analysis, held-out and independent hand-written tests, hyper-parameter and threshold tuning, fusion-weight tuning | Test sets are small; independent questions written by the same author |
| 7 | Completeness and working demonstration (15) | Full pipeline: upload, extraction, graph, Q&A with citations, validation, comparison, reports, export, RBAC, audit; Docker verified; {tests} automated tests | Real-HLD demo not possible; OCR not exercised on real scans |
| 8 | Python implementation and code quality (6) | Modular package, tests, Ruff clean, type hints, docstrings, scripts for every experiment | Some long evaluation scripts could be split further |
| 9 | Deployment and MLOps basics (5) | Model registry with metadata, dataset hash and git SHA; `runs.jsonl` experiment log; `/version`; Dockerfile + compose; GitHub Actions CI; pinned `requirements-lock.txt` | CI workflow written but has not run on GitHub until the branch is pushed with Actions enabled |
| 10 | Responsible AI and deployment ethics (3) | Report s.11: safety risk, hallucination control, privacy, access control, audit, layout/vocabulary bias, prompt injection, transparency | No formal red-team of prompt injection |
| 11 | Technical Q&A (3) | `Technical_QA_Prep` document; you must be able to explain every module | Depends on you; read the code you are asked about |
| 12 | Communication and presentation (2) | Video script, report structure, screenshots | Video still to be recorded |

## Headline numbers (all reproducible with the commands in the report appendix)
- Answerability model ({ans['selected'].replace('_', ' ')}): unseen-document F1 {tm['f1']:.3f}, ROC-AUC {tm['roc_auc']:.3f}; previous hand-set rule F1 {rb['f1']:.3f}, AUC {rb['roc_auc']:.3f}.
- Independent hand-written questions (36, held-out domains): accuracy {ind['accuracy']:.3f} (answerable {ind['answerable_accuracy']:.3f}, refusal {ind['refusal_accuracy']:.3f}).
- Retrieval: tuned hybrid held-out MRR {ret['approaches'][tuned]['test']['mrr']}; BGE alone {ret['approaches']['Dense: BGE-small (used)']['test']['mrr']}; BM25 {ret['approaches']['BM25 (CamelCase-aware, used)']['test']['mrr']}.
- Extraction F1 on unseen domains {ext['test']['summary']['overall']['f1']} (development F1 before fixes {before['summary']['overall']['f1']}).
- Validation rules: {val['detected']}/{val['seeded_defects']} seeded defects found, {val['findings_on_clean_documents']} false findings on clean documents.

## Things that would improve the score most
1. Check the taught-technique list in your syllabus against `SEARCH_SPACES` and the report section 7.
2. Write the personal reflection (report s.14) and complete both declarations.
3. Record the video following the script and rehearse live answers (see the Q&A preparation notes).
4. Run the GitHub Actions workflow once and note the result.
"""


def qa_prep(reg: str) -> str:
    ans, res, ret, val, ext, before = _n()
    tm, rb = ans["test_metrics"], ans["rule_baseline_test"]
    ind_t, ind_l = res["independent"]["trained"], res["independent"]["legacy_gate"]
    tuned = next(k for k in ret["approaches"] if "tuned" in k)
    return f"""# Technical Q&A preparation notes

For {reg}. Every team member is questioned on ownership, design choices, metrics and limitations. Read the code behind each
answer so you can explain it in your own words. Short answers first, details after.

## Problem and approach
**Q: What problem does the project solve?**
Reviewing long AUTOSAR HLD PDFs by hand is slow and misses inconsistencies. The system extracts the architecture, answers
questions with page citations, flags inconsistencies, compares revisions and exports findings, always with human review.

**Q: Why not just ask an LLM?**
An LLM can invent relationships and cannot cite exact pages reliably. Here, structure comes from deterministic table parsing
(reproducible, auditable), answers are composed from retrieved evidence, and an optional LLM may only rephrase that evidence.

**Q: Where is machine learning in this project?**
(1) Pre-trained BGE embeddings for semantic retrieval. (2) A supervised answerability classifier trained on labelled
questions that decides whether the document can answer. (3) Tuned retrieval fusion. Extraction and validation are
rule-based on purpose.

**Q: Supervised, unsupervised or reinforcement learning?**
The answerability model is supervised binary classification. Embedding models are pre-trained with self-supervised
learning. Retrieval ranking (BM25) is unsupervised. No reinforcement learning.

## Data
**Q: Why synthetic data? Is that a weakness?**
Real HLDs are confidential. Synthetic documents let me know the ground truth exactly and generate defects at known
places. The weakness is realism: one layout, templated questions. The report says this and claims generalisation only
across domains and naming styles.

**Q: How did you avoid data leakage?**
Documents are split into development (6) and test (3 + sample HLD + its revision); the same document is never in both.
Cross-validation is grouped by document. The test documents were generated after the development set was frozen. I also
wrote an independent hand-written question set and ran it once. I admit that the hand-set threshold I first used was
calibrated on the sample question set, which made its 32/32 score misleading; that is why the independent set exists.

**Q: What did EDA tell you?**
203 table cells had wrapped-underscore artefacts (fixed by cleaning); pages with few words are not necessarily scans (OCR
trigger fixed); chunks are short (median about 30 words), so chunk size barely matters here; features are strongly
correlated (similarities 0.97-0.99), which favours regularised or tree models.

## Features and models
**Q: Which features does the answerability model use and which matter?**
Twelve: semantic similarity statistics, BM25 scores, vocabulary coverage, uncovered token count, agreement between
retrievers, share of query words in the top chunk, entity matches. Permutation importance ranks entity match, top-chunk
coverage and coverage highest; raw similarity adds little once those are known.

**Q: Did you use PCA? What happened?**
Yes, on the 12 features (few components keep 90% of variance, no accuracy gain) and on the 384-dim embeddings (64 dims
dropped held-out MRR from {ret['pca_dense_test']['384']['mrr']} to {ret['pca_dense_test']['64']['mrr']}). So I kept the full representation. Negative results
are reported.

**Q: Why random forest? Why not logistic regression?**
It had the highest nested-CV AUC ({ans['model_comparison'][ans['selected']]['cv_auc_mean']}), but the top models (SVM, k-NN, forest, boosting, logistic regression) are within one standard
deviation, so the choice is not critical. I calibrated it so its probability can be shown as confidence. If asked for
interpretability, logistic regression is nearly as good.

**Q: How do you know it is not overfitting?**
Nested leave-one-document-out CV scores the model on documents it never saw; train-validation gap is about 0.006 AUC; the
learning curve flattens; the held-out test AUC ({tm['roc_auc']}) matches CV. The decision tree overfits most (gap 0.022).
Caveat: a forest fits training data almost perfectly, so only validation figures count.

**Q: What are precision and recall here? What did you optimise?**
Positive class = answerable. Precision = answered questions that were truly answerable; recall = answerable questions that were
answered. I picked the decision threshold on out-of-fold predictions to maximise F1 ({ans['metadata']['threshold']}). In a safety setting you might raise
the threshold to refuse more.

**Q: Why was the hybrid retrieval changed?**
Equal-weight fusion scored MRR {ret['approaches']['Hybrid BM25 + BGE, equal weights']['test']['mrr']} on held-out documents, below BGE alone ({ret['approaches']['Dense: BGE-small (used)']['test']['mrr']}). I tuned the dense weight on development documents
only (best 10) and confirmed {ret['approaches'][tuned]['test']['mrr']} on held-out documents.

**Q: What is reciprocal rank fusion?**
Each retriever ranks chunks; a chunk's fused score is the sum of weight / (60 + rank) over retrievers, so chunks ranked high
by either list rise. The 60 is a standard smoothing constant.

## Results and honesty
**Q: Give your main results.**
Answerability model on unseen documents: F1 {tm['f1']}, AUC {tm['roc_auc']} (rule baseline F1 {rb['f1']}, AUC {rb['roc_auc']}). Independent hand-written
questions: accuracy {ind_t['accuracy']} (answerable {ind_t['answerable_accuracy']}, refusal {ind_t['refusal_accuracy']}); the old gate refused only {ind_l['refusal_accuracy']} of the
unanswerable ones. Extraction F1 {ext['test']['summary']['overall']['f1']} on unseen domains; validation recall {val['defect_recall']} with
no false findings on clean documents.

**Q: Why is extraction perfect? Is that believable?**
Not as a general claim. The first extractors scored F1 {before['summary']['overall']['f1']} on my development domains. I fixed the causes and
confirmed on three unseen domains, but all documents share one layout, so I would expect lower scores on real HLDs.

**Q: What are the limitations?**
Synthetic, single-layout data; small test sets; local-LLM answers and OCR on real scans not evaluated; the model refuses some
unusual paraphrases and answers some "absent attribute" questions about real entities; no SSO; in-memory graph only.

**Q: What would you do next?**
Test on real or differently formatted HLDs, add header mapping for other layouts, add a check that the requested attribute
appears in the cited evidence, evaluate a local LLM, and expand the labelled set.

## System and MLOps
**Q: How is the system versioned and reproducible?**
Models are stored with metadata (algorithm, parameters, threshold, features, training documents, dataset hash, git commit);
experiments log to `runs.jsonl`; `/version` reports what is running; dependencies are pinned; Docker and a CI workflow rebuild
and test everything.

**Q: How do you handle security?**
API keys map to roles (viewer, reviewer, admin) and projects; each document has its own vector collection; every action is
audited; the reviewer on a finding is the authenticated user.

**Q: What are the risks of wrong answers?**
A wrong answer could mislead a design review. Mitigations: citations on every answer, refusal for unanswerable questions,
calibrated confidence, human accept/reject workflow, advisory notice, no automatic approval.

## Honest declarations
**Q: Which parts did you write and which used AI assistance?**
Answer from your declaration. AI tools (Claude Code) were used for code, tests, evaluation scripts and documentation; you
are accountable for all of it. Be ready to open any module and walk through it.
"""
