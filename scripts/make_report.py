"""Generate the technical report PDF from the measured results.

Usage: python scripts/make_report.py OUTPUT.pdf [tests_passed]
Reads data/evaluation/results/*.json, data/evaluation/figures/*.png and submission_assets/screenshots/*.png.
"""
import itertools
import json
import sys
from datetime import date
from pathlib import Path

from PIL import Image as PILImage
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "technical_report.pdf")
TESTS = sys.argv[2] if len(sys.argv) > 2 else "43"
RES = ROOT / "data/evaluation/results"
FIG = ROOT / "data/evaluation/figures"
SHOTS = ROOT / "submission_assets" / "screenshots"


def load(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


R = load("results.json")
ANS = load("answerability_report.json")
RET = load("retrieval_experiments.json")
VAL = load("validation_eval.json")
EDA = load("eda_summary.json")
EXT_BEFORE = load("extraction_corpus_before_fix.json")
EXT_AFTER = load("extraction_corpus_after_fix.json")
META = ANS["metadata"]

NAME, UNI, REG = "Aishwarya Manoj", "Amrita Vishwa Vidyapeetham", "CB.SC.U4AIE23211"
TITLE = "AUTOSAR HLD Intelligence & Traceability Platform"

NAVY = colors.HexColor("#17375E")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=NAVY, fontSize=16, spaceBefore=14, spaceAfter=8,
                    keepWithNext=1)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=colors.HexColor("#2E75B6"), fontSize=12.5,
                    spaceBefore=10, spaceAfter=5, keepWithNext=1)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14.5, spaceAfter=6)
SMALL = ParagraphStyle("S", parent=BODY, fontSize=8.5, leading=11, textColor=colors.HexColor("#444444"))
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.5, leading=11, spaceAfter=0)
CAP = ParagraphStyle("Cap", parent=SMALL, alignment=TA_CENTER, spaceAfter=10)
BUL = ParagraphStyle("Bul", parent=BODY, leftIndent=14, bulletIndent=2, spaceAfter=3)


def P(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BUL, bulletText="•") for t in items]


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E5F3")))
    t.setStyle(TableStyle(style))
    return t


def fig(path: Path, caption: str, width_mm: float = 160):
    if not path.exists():
        return P(f"[missing figure {path.name}]", SMALL)
    w, h = PILImage.open(path).size
    scale = min(width_mm * mm / w, 200 * mm / h)
    return KeepTogether([Image(str(path), width=w * scale, height=h * scale), P(caption, CAP)])


def pct(x):
    return f"{x:.1%}" if isinstance(x, (int, float)) else str(x)


# ------------------------------------------------------------------ diagrams

def diagram(width, height, boxes, arrows, font=7.5):
    d = Drawing(width, height)
    for x1, y1, x2, y2 in arrows:
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#555555"), strokeWidth=1))
        dx, dy = x2 - x1, y2 - y1
        n = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / n, dy / n
        d.add(Polygon([x2, y2, x2 - 6 * ux + 3 * uy, y2 - 6 * uy - 3 * ux, x2 - 6 * ux - 3 * uy, y2 - 6 * uy + 3 * ux],
                      fillColor=colors.HexColor("#555555"), strokeColor=None))
    for x, y, w, h, text, fill in boxes:
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor("#33415c"),
                   strokeWidth=0.8))
        lines = text.split("\n")
        for i, line in enumerate(lines):
            ty = y + h / 2 + (len(lines) / 2 - i - 0.75) * (font + 2)
            d.add(String(x + w / 2, ty, line, textAnchor="middle", fontSize=font,
                         fontName="Helvetica-Bold" if i == 0 else "Helvetica"))
    return d


def architecture_diagram():
    c1, c2, c3, c4, c5 = "#DCE6F7", "#E2F0D9", "#FFF2CC", "#FCE4D6", "#EADCF4"
    boxes = [
        (170, 300, 180, 28, "Engineering users", "#FFFFFF"),
        (90, 250, 340, 32, "Streamlit UI\nnavigation | chat | graph | review | export", c1),
        (90, 195, 340, 40, "FastAPI service layer\nAPI-key auth | roles | project isolation | audit log | /version", c2),
        (20, 105, 150, 70, "Ingestion + extraction\nPyMuPDF tables | OCR fallback\nsection chunker | table + pattern rules", c3),
        (185, 105, 150, 70, "RAG layer\nBGE embeddings | ChromaDB | BM25\nweighted RRF | answerability model", c3),
        (350, 105, 150, 70, "Analysis engines\n11 validation rules | revision diff\ngraph + impact | reports", c3),
        (20, 20, 150, 55, "SQLite\ndocuments | reviews | audit", c4),
        (185, 20, 150, 55, "ChromaDB (persistent)\none collection per document", c4),
        (350, 20, 150, 55, "Model registry (files)\nmodels/answerability/vX + metadata", c5),
    ]
    arrows = [(260, 300, 260, 282), (260, 250, 260, 235), (95, 195, 95, 175), (260, 195, 260, 175),
              (425, 195, 425, 175), (95, 105, 95, 75), (260, 105, 260, 75), (425, 105, 425, 75)]
    return diagram(520, 335, boxes, arrows)


def workflow_diagram():
    names = ["Upload\nPDF", "Parse text,\ntables, OCR", "Section-aware\nchunking", "Entities: patterns\n+ tables, dedup",
             "Embed (BGE)\n+ index", "Validate\n(11 rules)"]
    boxes = [(8 + i * 85, 55, 76, 42, n, "#DCE6F7") for i, n in enumerate(names)]
    arrows = [(8 + i * 85 + 76, 76, 8 + (i + 1) * 85, 76) for i in range(5)]
    boxes += [(8, 0, 160, 34, "Query: BM25 + dense (w=10)\n12 retrieval features", "#E2F0D9"),
              (186, 0, 160, 34, "Answerability model\nanswer or refuse", "#E2F0D9"),
              (364, 0, 150, 34, "Cited answer + review\naccept / reject / export", "#FFF2CC")]
    arrows += [(168, 17, 186, 17), (346, 17, 364, 17)]
    return diagram(520, 105, boxes, arrows, font=7)


# ------------------------------------------------------------------ content

def build():
    ind_t, ind_l = R["independent"]["trained"], R["independent"]["legacy_gate"]
    qa = R["qa"]
    cmp_ = ANS["model_comparison"]
    sel = ANS["selected"]
    tm, rb = ANS["test_metrics"], ANS["rule_baseline_test"]
    approaches = RET["approaches"]
    tuned_key = next(k for k in approaches if "tuned" in k)
    ext_b = EXT_BEFORE["summary"]
    ext_a_dev, ext_a_test = EXT_AFTER["dev"]["summary"], EXT_AFTER["test"]["summary"]
    tot = EDA["totals"]
    story = []

    # ---- title page
    story += [Spacer(1, 45 * mm),
              P(f"<font size=24 color='#17375E'><b>{TITLE}</b></font>",
                ParagraphStyle("t", alignment=TA_CENTER, leading=30)),
              Spacer(1, 6 * mm),
              P("<font size=13>Technical Report</font>",
                ParagraphStyle("t2", alignment=TA_CENTER, leading=20, spaceAfter=6)),
              P("<font size=11>Case Study CS1: AUTOSAR HLD Document Analysis Assistant<br/>"
                "TechPulse FY-26 | Applied AI/ML Capstone</font>",
                ParagraphStyle("t3", alignment=TA_CENTER, leading=16)),
              Spacer(1, 22 * mm),
              table([["Student", NAME], ["Register number", REG], ["University", UNI],
                     ["Case study", "CS1: AUTOSAR HLD Document Analysis Assistant"],
                     ["Version / date", f"v1.0 / {date.today():%d %B %Y}"]], [45, 110], header=False),
              Spacer(1, 12 * mm),
              P("All input data is synthetic. AI-generated outputs are advisory and require review by a qualified engineer.",
                ParagraphStyle("n", parent=SMALL, alignment=TA_CENTER)),
              PageBreak()]

    # ---- summary and rubric map
    story += [P("Summary and map to the evaluation rubric", H1),
              P("This report describes a retrieval-augmented assistant for AUTOSAR High-Level Design (HLD) documents. It extracts the "
                "architecture (components, interfaces, ports, signals, dependencies, flows), answers questions with page citations, "
                "refuses questions the document cannot answer, validates cross-table consistency, compares revisions and exports "
                "structured findings. Its learned component is an <b>answerability classifier</b> selected from six model families "
                f"by nested leave-one-document-out cross-validation ({sel.replace('_', ' ')} selected; held-out test F1 {tm['f1']:.2f} vs "
                f"{rb['f1']:.2f} for the earlier hand-set threshold)."),
              table([["Rubric criterion", "Where addressed"],
                     ["1 Problem understanding and context", "Section 1 (problem, users, measurable success criteria)"],
                     ["2 AI/ML fundamentals and approach selection", "Section 4 (alternatives compared with evidence)"],
                     ["3 Dataset understanding, preprocessing, EDA", "Sections 2 and 3 (corpus, splits, EDA, leakage checks)"],
                     ["4 Feature engineering, selection, dimensionality reduction", "Section 6 (tokenisation ablation, 12 features, importance, PCA)"],
                     ["5 Model development with taught techniques", "Section 7 (retrieval models, six classifier families, tuning)"],
                     ["6 Evaluation, validation, optimisation", "Section 8 (nested CV, overfitting, errors, held-out and independent tests)"],
                     ["7 Completeness and working demonstration", "Sections 5, 9, 13 (end-to-end system, screenshots)"],
                     ["8 Python implementation and code quality", "Section 9 (modules, tests, linting)"],
                     ["9 Deployment and MLOps basics", "Section 10 (versioning, tracking, Docker, CI)"],
                     ["10 Responsible AI and ethics", "Section 11"],
                     ["11-12 Technical Q&amp;A, communication", "Section 14 and the Technical Q&amp;A preparation notes"]],
                    [75, 95]),
              PageBreak()]

    # ---- 1 problem, 2 data
    story += [P("1. Problem statement, users and success criteria", H1),
              P("AUTOSAR HLD documents describe software components, interfaces, ports, signals, dependencies and functional flows. They "
                "are long unstructured PDFs, so architects and integrators read them manually to find mismatches and missing "
                "dependencies and to judge what a change affects. Manual review is slow, inconsistent and hard to audit."),
              P("<b>Intended users:</b> system and AUTOSAR architects, software developers, integration engineers, test engineers and "
                "engineering managers. <b>Out of scope:</b> automatic approval of architecture decisions and modification of source HLDs; "
                "every output is advisory and passes a human review step."),
              P("<b>Measurable success criteria</b> (defined before the experiments, results measured on held-out data):"),
              table([["Criterion", "Target", "Measured", "Where"],
                     ["Entity extraction F1 on unseen documents", "&ge; 0.95", f"{ext_a_test['overall']['f1']:.2f}", "7.3"],
                     ["Refusal accuracy, independent hand-written set", "&ge; 0.90", f"{ind_t['refusal_accuracy']:.2f}", "8.4"],
                     ["Answerable-question accuracy, independent set", "&ge; 0.85", f"{ind_t['answerable_accuracy']:.2f}", "8.4"],
                     ["Answerability F1, unseen documents", "&ge; 0.90", f"{tm['f1']:.2f}", "8.3"],
                     ["Answers carrying valid citations", "100%", pct(qa["groundedness_valid_citations"]), "8.4"],
                     ["Seeded-defect recall / false positives on clean documents", "&ge; 0.90 / 0",
                      f"{VAL['defect_recall']:.2f} / {VAL['findings_on_clean_documents']}", "8.6"]],
                    [80, 25, 25, 40]),
              P("Business value: less manual review effort, a searchable architecture repository, traceability and impact analysis, "
                "and an auditable record of which findings humans accepted or rejected."),
              P("2. Data and knowledge base", H1),
              P("No real HLD was available, and real ones are confidential, so the project uses <b>synthetic HLDs</b> generated with "
                "ReportLab in the layout of the sample document (system overview, components, interfaces, ports, signals, dependency "
                "table, functional flows, constraints). Eleven documents are used:"),
              table([["Group", "Documents", "Use"],
                     ["Development (6)", "powertrain, adas, infotainment, battery, lighting, thermal (4-6 components each)",
                      "Developing extractors, training and cross-validating the classifier, tuning the retrieval weight"],
                     ["Held-out test (3)", "steering, keyless, wiper (generated after the development set was frozen)",
                      "Final evaluation only"],
                     ["Sample + revision (2)", "sample_hld.pdf (Body Control System) and sample_hld_v2.pdf",
                      "Demo document, revision comparison, hand-written question set, final test"]],
                    [32, 80, 58]),
              Spacer(1, 2 * mm),
              P("Each synthetic document has a <b>ground-truth file</b> with its entities, and a <b>defective twin</b> with four seeded "
                "defects (wrong port direction, dropped dependency, undefined interface on a port, signal endpoint mismatch). "
                "<b>Question data:</b> for every document, 24 answerable questions are generated from its own tables (so gold answers and "
                "gold sections are known) and 24 unanswerable ones of three kinds: off-topic, plausible-but-absent attributes of real "
                "entities (for example the CAN baud rate of a component), and invented entities. This gives 528 labelled questions "
                "(288 development, 240 test), balanced 50/50. Two <b>hand-written</b> sets provide independent checks: 32 questions on the sample "
                "HLD and 36 questions on the three held-out domains, written before the final model was evaluated."),
              P("<b>Limitation:</b> the data is synthetic and uniform in layout. Results show that the method works and generalises across "
                "domains and naming styles; they do not establish accuracy on real-world HLDs."),
              PageBreak()]

    # ---- 3 EDA
    story += [P("3. Exploratory data analysis and preprocessing", H1),
              P(f"The corpus has {tot['documents']} documents, {tot['pages']} pages, {tot['words']:,} words, {tot['tables']} tables and "
                f"{tot['chunks']} section-aware chunks (mean {EDA['chunk_words']['mean']} words, maximum {EDA['chunk_words']['max']}). "
                "The most relevant observations:")]
    story += bullets([
        f"<b>Table text artefacts:</b> {tot['wrapped_underscore_cells']} table cells contain a PDF line-wrap artefact in which a long "
        "identifier such as <font face='Courier'>DoorStatus_Out</font> is extracted as 'DoorStatus Out' followed by a stray underscore line. "
        "Left untreated, port names would not match their definitions. A cleaning step rejoins them (preprocessing).",
        "<b>OCR trigger:</b> the first version sent any page with fewer than 20 words to OCR, including nearly empty text pages at the end "
        "of a section. OCR is now used only for pages with images or no text layer; no page in the corpus needs it.",
        f"<b>Chunk size:</b> chunks are short (median {EDA['chunk_words']['median']:.0f} words) because HLD sections are short tables, so the "
        "250-word chunk limit rarely applies here. It is set to stay within the 512-token window of the embedding model; with 1200 words "
        "long sections would be silently truncated.",
        f"<b>Missing values:</b> {EDA['quality_checks']['missing_values']} in the feature matrix; "
        f"{EDA['quality_checks']['duplicate_rows']} duplicate question row (negligible).",
        "<b>Class balance:</b> 144 / 144 (development) and 120 / 120 (test) answerable vs unanswerable, so accuracy is meaningful; F1 and "
        "ROC-AUC are reported as well.",
        "<b>Leakage control:</b> no document appears in both development and test sets. "
        f"{EDA['quality_checks']['identical_questions_in_dev_and_test']} identical questions occur in both splits "
        f"({pct(EDA['quality_checks']['identical_question_share_of_test'])} of the test set); these are generic off-topic sentences that are "
        "unanswerable in every document, so they cannot leak document-specific information. Templates are shared by design.",
        "<b>Feature relationships:</b> several features are strongly correlated (top-1/top-2/mean similarity, 0.97-0.99; BM25 score vs score "
        "per token, 0.94; coverage vs uncovered tokens, -0.85). This motivates regularised and tree-based models and the PCA analysis in Section 6.",
    ])
    story += [fig(FIG / "eda_corpus.png", "Figure 1: Corpus overview and chunk-length distribution."),
              fig(FIG / "eda_questions.png", "Figure 2: Question categories and two discriminative features by class."),
              PageBreak()]

    # ---- 4 approach selection, 5 architecture
    story += [P("4. Approach selection and justification", H1),
              P("Three design questions were answered by comparing alternatives rather than by assumption."),
              table([["Decision", "Alternatives", "Choice and evidence"],
                     ["How to extract architecture entities",
                      "(a) generative LLM; (b) naming-pattern regular expressions only; (c) table parsing plus patterns",
                      f"(c). Patterns alone reached F1 {ext_b['overall']['f1']:.2f} on development domains (signal recall {ext_b['signal']['recall']:.2f}, flow "
                      "recall 0): names that do not end in Status/Speed/Position/Command were missed. Adding table-driven extraction and "
                      f"parsing titles from structure gave F1 {ext_a_test['overall']['f1']:.2f} on three further unseen domains. "
                      "Deterministic extraction keeps every entity traceable to a page and is reproducible; an LLM would add cost and non-determinism."],
                     ["How to retrieve evidence",
                      "BM25, TF-IDF, MiniLM embeddings, BGE embeddings, hybrid",
                      f"Weighted hybrid of BGE dense retrieval and BM25 (held-out MRR {approaches[tuned_key]['test']['mrr']}). "
                      f"BGE alone scored {approaches['Dense: BGE-small (used)']['test']['mrr']}; BM25 {approaches['BM25 (CamelCase-aware, used)']['test']['mrr']}; "
                      f"TF-IDF {approaches['TF-IDF cosine']['test']['mrr']}; MiniLM {approaches['Dense: MiniLM-L6']['test']['mrr']}. See Section 7."],
                     ["When to refuse a question",
                      "(a) hand-set similarity threshold; (b) trained classifier",
                      f"(b). The 0.60 threshold gave held-out F1 {rb['f1']:.2f}; it answered {pct(1 - ind_l['refusal_accuracy'])} of the unanswerable "
                      f"questions in the independent set. The trained classifier reached F1 {tm['f1']:.2f} (Section 8)."],
                     ["How to phrase answers",
                      "LLM generation vs extractive composition",
                      "Extractive composition from retrieved passages and graph facts by default: no hallucination risk, offline, auditable. "
                      "An optional local LLM (Ollama) can rewrite the evidence; it was not part of the evaluation."]],
                    [30, 45, 95]),
              P("<b>Learning types.</b> Embedding models are pre-trained (self-supervised); the answerability classifier is <b>supervised binary "
                "classification</b> trained on labelled questions; retrieval ranking and extraction are unsupervised/rule-based. The task has "
                "a small labelled corpus, so low-variance models and grouped cross-validation are appropriate."),
              P("5. Solution architecture", H1),
              architecture_diagram(), P("Figure 3: System architecture.", CAP),
              workflow_diagram(), P("Figure 4: Processing and query workflow.", CAP),
              table([["Layer", "Choice", "Note"],
                     ["UI / API", "Streamlit / FastAPI", "As recommended in the case-study document"],
                     ["Ingestion", "PyMuPDF (text, tables), Tesseract OCR for scanned pages", "Table cleaning for wrapped identifiers"],
                     ["Embeddings / vectors", f"{R['config']['embedding_model']} (ONNX, local), ChromaDB persistent, one collection per document",
                      "Runs offline from the Docker image"],
                     ["Structured store", "SQLite: documents, reviews, audit log", "PostgreSQL for production"],
                     ["Graph", "In-memory property graph built from the HLD tables", "Neo4j not used at this document size"],
                     ["LLM", "Off by default; optional Ollama (local) or Anthropic (external, must be declared)", "Not part of reported results"]],
                    [32, 90, 48]),
              PageBreak()]

    # ---- 6 features
    abl = ANS["feature_ablation_auc"]
    pca = ANS["pca"]
    pca_ret = RET["pca_dense_test"]
    cam = approaches["BM25 (CamelCase-aware, used)"]
    plain = approaches["BM25 (plain tokens)"]
    n90 = next(i + 1 for i, v in enumerate(itertools.accumulate(pca["explained_variance_ratio"])) if v >= 0.9)
    max_drop = max(abs(v - abl["(all features)"]) for k, v in abl.items() if k != "(all features)")
    story += [P("6. Feature engineering, selection and dimensionality reduction", H1),
              P("6.1 Text representation", H2),
              P("HLD identifiers are CamelCase (<font face='Courier'>DoorControl</font>) and snake_case (<font face='Courier'>DoorStatus_In</font>) so a "
                "plain tokeniser cannot match the natural-language question 'door control' to the identifier. The tokeniser indexes each "
                "identifier whole and split into words, and drops function words (a stop-word list extended after error analysis showed that "
                f"words such as 'have' counted as unseen vocabulary). Ablation: BM25 with plain tokens reached held-out MRR {plain['test']['mrr']}; "
                f"the CamelCase-aware tokeniser reached {cam['test']['mrr']} (recall@1 {plain['test']['recall@1']} to {cam['test']['recall@1']}). "
                "The gain is modest because the dense model also handles part of the matching."),
              P("6.2 Answerability features", H2),
              table([["Feature", "Meaning"],
                     ["sem_top1, sem_top2, sem_margin, sem_mean5", "Cosine similarity of the best, second-best chunk, their gap, mean of top five"],
                     ["bm25_top1, bm25_per_token", "Best BM25 score, and per query token"],
                     ["coverage, uncovered, n_tokens", "Share and count of query words that exist anywhere in the document vocabulary; query length"],
                     ["agree", "1 if BM25 and dense retrieval choose the same top chunk"],
                     ["top_chunk_cov", "Share of query words found in the best chunk"],
                     ["entity_match", "Number of known architecture entities named in the question"]],
                    [62, 108]),
              Spacer(1, 2 * mm),
              P("6.3 Feature selection and importance", H2),
              P("Permutation importance on the held-out documents and leave-one-feature-out ablation (logistic regression) were used. "
                f"Using all features gives test AUC {abl['(all features)']}; removing any single feature changes it by at most "
                f"{max_drop:.3f}, which confirms the redundancy seen in the correlation matrix. The most informative features are those that "
                "measure how much of the question the document actually contains (entity match, share of query words found in the best chunk, "
                "vocabulary coverage); raw similarity and BM25 magnitudes add little once those are present."),
              fig(FIG / "feature_importance.png", "Figure 5: Permutation importance on held-out documents.", 110),
              P("6.4 Dimensionality reduction (PCA)", H2),
              P(f"PCA on the 12 standardised features: the first {n90} components explain at least 90% of the variance. A logistic regression "
                "trained on PCA scores recovers most of the full-feature AUC with few components (figure), so PCA is a valid compression but "
                "gives no accuracy gain; the classifier uses the original, interpretable features. PCA was also applied to the 384-dimensional "
                f"chunk embeddings: reducing to 64 dimensions lowered held-out retrieval MRR from {pca_ret['384']['mrr']} to {pca_ret['64']['mrr']} "
                f"and to {pca_ret['16']['mrr']} at 16 dimensions, so the full embedding is kept. (With only 66 development chunks, components "
                "beyond about 30 are noise; this limits the experiment.)"),
              fig(FIG / "pca_features.png", "Figure 6: PCA of the answerability features and downstream AUC."),
              fig(FIG / "embedding_pca.png", "Figure 7: PCA of BGE chunk embeddings, coloured by HLD section.", 120),
              PageBreak()]

    # ---- 7 model development
    rows = [["Retrieval method", "Dev MRR", "Test R@1", "Test R@3", "Test MRR"]]
    for name, v in approaches.items():
        rows.append([name, v["dev"]["mrr"], v["test"]["recall@1"], v["test"]["recall@3"], v["test"]["mrr"]])
    story += [P("7. Model development", H1),
              P("7.1 Retrieval models", H2),
              P("Retrieval ranks the chunks of a document for each answerable question; a result is correct if a chunk from a gold section "
                "is returned. Taught techniques compared: lexical (BM25, TF-IDF), two pre-trained sentence-embedding models and hybrids."),
              table(rows, [74, 20, 24, 24, 24]),
              Spacer(1, 2 * mm),
              P("The equal-weight hybrid was worse than BGE alone, which contradicted the initial design. The dense weight in the "
                "reciprocal-rank fusion was therefore treated as a hyperparameter and tuned on the development documents only (grid "
                f"{', '.join(RET['dense_weight_grid_dev_mrr'])}); weight {RET['best_dense_weight']} won and was confirmed on held-out documents "
                f"(MRR {approaches[tuned_key]['test']['mrr']}). BM25 now mostly acts as a tie-breaker and keeps exact identifiers findable."),
              fig(FIG / "retrieval_comparison.png", "Figure 8: Retrieval comparison on development and held-out documents.", 130),
              P("7.2 Answerability classifier (supervised learning)", H2),
              P("Task: given a question and the retrieval evidence from one document, predict whether the document can answer it. Six taught model "
                "families were compared with hyperparameter grids: logistic regression (C), RBF-SVM (C, gamma), k-nearest neighbours (k), decision "
                "tree (depth), random forest (depth, leaf size) and gradient boosting (trees, depth, learning rate), plus two baselines: the "
                "previous hand-set threshold and the majority class. Features are standardised for the distance- and margin-based models. "
                "<b>Protocol:</b> nested cross-validation grouped by <i>document</i> (outer leave-one-document-out, inner 5-fold grouped grid search), "
                "so every score is for a document the model has never seen and hyperparameters are not tuned on the evaluation fold. The "
                "decision threshold was chosen on out-of-fold predictions.")]
    rows = [["Model", "CV AUC (mean &plusmn; std)", "Train AUC", "Overfit gap", "F1 (tuned thr.)"]]
    for name, v in cmp_.items():
        rows.append([name, f"{v['cv_auc_mean']:.3f} &plusmn; {v['cv_auc_std']:.3f}", v.get("train_auc_mean", "-"),
                     v.get("overfit_gap", "-"), v.get("f1", "-")])
    story += [table(rows, [58, 40, 22, 22, 28]),
              Spacer(1, 2 * mm),
              P("All learned models clearly beat the hand-set rule (AUC 0.83) and the majority baseline. Differences among the top models "
                f"(SVM, k-NN, random forest, boosting) are within one standard deviation, so the choice is not critical; <b>{sel.replace('_', ' ')}</b> was "
                "selected for the highest mean AUC and wrapped in sigmoid calibration so its probability can serve as a confidence value. "
                f"Chosen hyperparameters: {META['best_params']}; decision threshold {META['threshold']}."),
              P("7.3 Extraction improvements found by error analysis", H2),
              P("Running the first extractors on the six development domains exposed generalisation failures. They were fixed one cause at "
                "a time, then confirmed on three further domains that had not been used for debugging."),
              table([["Failure (before)", "Cause", "Fix"],
                     [f"Signal recall {ext_b['signal']['recall']:.2f}", "Signals recognised only if named *Status/Speed/Position/Command",
                      "Read signals, components, interfaces and ports directly from the tables"],
                     [f"Flow precision/recall {ext_b['functional_flow']['precision']:.0f}/{ext_b['functional_flow']['recall']:.0f}",
                      "Flow titles taken from a hard-coded list of the sample document",
                      "Title = leading plain words before the first identifier-like token"],
                     [f"Interface precision {ext_b['interface']['precision']:.2f}", "Pattern matched all-caps words such as IVI",
                      "Require a lowercase letter after the leading I"],
                     ["OCR attempted on blank text pages", "Low word count treated as scanned", "OCR only for pages with images or no text layer"]],
                    [45, 65, 60]),
              Spacer(1, 2 * mm),
              table([["Split", "Overall precision", "Overall recall", "F1"],
                     ["Development, before fixes", ext_b["overall"]["precision"], ext_b["overall"]["recall"], ext_b["overall"]["f1"]],
                     ["Development, after fixes", ext_a_dev["overall"]["precision"], ext_a_dev["overall"]["recall"], ext_a_dev["overall"]["f1"]],
                     ["Held-out (3 unseen domains), after fixes", ext_a_test["overall"]["precision"], ext_a_test["overall"]["recall"],
                      ext_a_test["overall"]["f1"]]],
                    [70, 35, 35, 30]),
              P("Honest note: the development numbers after the fixes are optimistic because the fixes were derived from those documents; the "
                "held-out row is the fair estimate, and it is perfect partly because the synthetic documents share one table layout.", SMALL),
              PageBreak()]

    # ---- 8 evaluation
    story += [P("8. Evaluation, validation and optimisation", H1),
              P("8.1 Protocol", H2),
              P("Development documents were used for model development, cross-validation and tuning. The held-out documents (three unseen "
                "domains plus the sample HLD and its revision) were evaluated once, after the model, threshold and retrieval weight were fixed. "
                "Metrics: ROC-AUC (threshold-free), precision, recall, F1 for the answerable class, accuracy, Brier score (calibration), and for "
                "retrieval recall@k and MRR."),
              P("8.2 Validation and overfitting analysis", H2),
              P(f"Nested cross-validation AUC for {sel.replace('_', ' ')} is {cmp_[sel]['cv_auc_mean']:.3f} &plusmn; {cmp_[sel]['cv_auc_std']:.3f} across "
                f"six unseen documents, against a training AUC of {cmp_[sel].get('train_auc_mean', '-')}; the gap of {cmp_[sel].get('overfit_gap', '-')} is "
                f"small, and the held-out test AUC ({tm['roc_auc']:.3f}) is in line with the cross-validation estimate, which indicates no material "
                "overfitting. The decision tree, the least regularised model, has the largest train-validation gap and the lowest AUC (the random forest fits its training data almost perfectly, as expected, so the validation figures are the ones that matter). "
                "The learning curve shows validation AUC rising and flattening with more training examples, so more documents would help "
                "only marginally."),
              fig(FIG / "learning_curve.png", "Figure 9: Learning curve (grouped by document).", 105),
              fig(FIG / "roc_cv.png", "Figure 10: Nested-CV ROC curves for all models and the hand-set rule.", 105),
              P("8.3 Results on unseen documents", H2),
              table([["", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC", "Brier"],
                     ["Trained model", tm["accuracy"], tm["precision"], tm["recall"], tm["f1"], tm["roc_auc"], tm["brier"]],
                     ["Hand-set rule (sem_top1 &ge; 0.60)", rb["accuracy"], rb["precision"], rb["recall"], rb["f1"], rb["roc_auc"], rb["brier"]]],
                    [55, 18, 18, 18, 18, 22, 18]),
              Spacer(1, 2 * mm),
              P(f"On {META['n_test']} questions from {len(META['test_documents'])} unseen documents the model makes {tm['fp']} false-positive and "
                f"{tm['fn']} false-negative decisions. By category the hand-set rule fails on questions about invented entities "
                f"({pct(ANS['by_category_test']['fake_entity']['rule_correct'])} correct) and absent attributes "
                f"({pct(ANS['by_category_test']['absent_attribute']['rule_correct'])}); the trained model handles them "
                f"({pct(ANS['by_category_test']['fake_entity']['model_correct'])} and {pct(ANS['by_category_test']['absent_attribute']['model_correct'])}). "
                "Probabilities are reasonably calibrated (Brier score above), so the confidence shown to users is meaningful."),
              fig(FIG / "confusion_test.png", "Figure 11: Confusion matrix on unseen documents.", 80),
              fig(FIG / "calibration.png", "Figure 12: Reliability diagram on unseen documents.", 80),
              P("8.4 Independent hand-written questions (end to end)", H2),
              table([["Question set", "System", "Overall", "Answerable", "Refusal"],
                     ["36 questions, 3 held-out domains (never tuned on)", "Trained model", ind_t["accuracy"],
                      ind_t["answerable_accuracy"], ind_t["refusal_accuracy"]],
                     ["", "Previous hand-set gate", ind_l["accuracy"], ind_l["answerable_accuracy"], ind_l["refusal_accuracy"]],
                     ["32 questions, sample HLD (used for error analysis, so no longer independent)", "Trained model",
                      qa["accuracy_overall"], qa["answer_accuracy_answerable"], qa["refusal_accuracy_unanswerable"]]],
                    [62, 38, 22, 24, 24]),
              Spacer(1, 2 * mm),
              P("The earlier gate answered almost every question, which gave perfect recall but only "
                f"{pct(ind_l['refusal_accuracy'])} refusal accuracy; its 32/32 on the first sample question set was inflated because the threshold had been "
                "calibrated on that same set (data leakage), which is why the independent set was created. The trained model trades a small loss "
                "of recall for a large gain in safe refusals."),
              P("<b>Error analysis of the independent set:</b>")]
    story += bullets([f"<b>{f['id']}</b> ({'answered an unanswerable question' if not f['answerable'] else 'refused an answerable question'}): "
                      f"'{f['question']}'" for f in ind_t["failures"]])
    story += [P("Refusals of answerable questions occur for unusual paraphrases ('how much current to apply' for the AssistCurrent signal) "
                "whose wording shares little vocabulary with the document; the wrongly answered question names a real interface and asks for an "
                "attribute (CAN identifier) that is absent, the hardest case for a retrieval-based system. Remedies are a larger and more varied "
                "training set and a verification step that checks whether the asked-for attribute appears in the cited evidence."),
              P("8.5 Entity extraction", H2),
              P(f"Held-out extraction (3 unseen domains): precision {ext_a_test['overall']['precision']:.2f}, recall {ext_a_test['overall']['recall']:.2f}, "
                "F1 1.00 for every entity type. See Section 7.3 for the before/after analysis."),
              P("8.6 Validation rules", H2),
              P(f"Across the 9 synthetic documents, {VAL['detected']} of {VAL['seeded_defects']} seeded defects were detected "
                f"(recall {VAL['defect_recall']:.2f}; by kind {VAL['recall_by_kind']}), with {VAL['findings_on_clean_documents']} findings on the clean "
                f"versions and {VAL['unexplained_findings_on_defect_documents']} findings on the defective versions that were not explained by a defect. "
                "Caveat: the defect kinds were chosen to match the rules, so the recall confirms correct implementation, not coverage of all "
                "possible HLD inconsistencies."),
              P("8.7 Optimisation summary", H2),
              table([["What was optimised", "How", "Effect (held-out)"],
                     ["Answerability model", "Six families, nested grouped CV, grid search, sigmoid calibration, threshold on out-of-fold F1",
                      f"F1 {rb['f1']:.2f} to {tm['f1']:.2f}; AUC {rb['roc_auc']:.2f} to {tm['roc_auc']:.2f}"],
                     ["Retrieval fusion weight", "Grid on development documents",
                      f"MRR {approaches['Hybrid BM25 + BGE, equal weights']['test']['mrr']} to {approaches[tuned_key]['test']['mrr']}"],
                     ["Stop-word list", "Error analysis on refused answerable questions", "Fewer spurious uncovered tokens"],
                     ["Extractors", "Error analysis on development corpus", f"F1 {ext_b['overall']['f1']:.2f} to {ext_a_test['overall']['f1']:.2f}"]],
                    [45, 70, 55]),
              P("8.8 Limitations of the evaluation", H2)]
    story += bullets([
        "Synthetic, template-generated data with one document layout; real HLDs vary more.",
        "Question templates are shared between training and test documents; only documents differ. The hand-written sets are the check against this.",
        "Gold labels for retrieval are section-level and the documents are small (about 10 chunks), so recall@5 saturates; MRR and recall@1 are the informative metrics.",
        "The local-LLM answer path, OCR on real scans and user-time savings were not evaluated.",
        f"Test and independent sets are small ({META['n_test']} and {ind_t['n']} questions); differences of a few percentage points are not significant.",
    ])
    story.append(PageBreak())

    # ---- 9 implementation, 10 MLOps
    story += [P("9. Implementation", H1),
              P("The code base is organised by responsibility: <font face='Courier'>app/ingestion</font> (parsing, OCR, metadata), "
                "<font face='Courier'>chunking</font>, <font face='Courier'>extraction</font> (pattern and table extractors, normalisation, structured model), "
                "<font face='Courier'>graph</font>, <font face='Courier'>rag</font> (tokeniser/BM25, embeddings, vector store, hybrid retriever, "
                "answerability model, answerer), <font face='Courier'>validation</font>, <font face='Courier'>comparison</font>, "
                "<font face='Courier'>reporting</font>, <font face='Courier'>api</font>, <font face='Courier'>evaluation</font> and a Streamlit "
                f"<font face='Courier'>frontend</font>. {TESTS} automated tests (unit and integration) cover parsing helpers, extraction, validation rules, "
                "retrieval, the answerability artefact, the API, security (roles, project isolation, audit), exports and the version endpoint; the "
                "code passes the Ruff linter."),
              P("<b>Pipeline.</b> A PDF is validated, parsed per page with PyMuPDF, cleaned, chunked by section, embedded and indexed, and "
                "its entities are extracted from patterns and tables and de-duplicated with merged evidence. A typed model of the tables feeds "
                "the graph, the 11 validation rules and the revision comparison. At query time BM25 and dense rankings are fused, 12 features "
                "are computed, the answerability model decides to answer or refuse, and the answer is composed from graph facts and "
                "cited passages with a probability-based confidence."),
              table([["Rule", "Check", "Severity"],
                     ["V001", "Provider/consumer/port owner not a declared component", "critical"],
                     ["V002", "Port references an undefined interface", "critical"],
                     ["V003", "Port direction contradicts component role", "critical"],
                     ["V004", "Interface endpoint without a matching port", "warning"],
                     ["V005", "Dependency table missing or contradicting the interface table", "warning / critical"],
                     ["V006", "Unknown relationship or undefined dependency target", "warning / critical"],
                     ["V007", "Signal endpoints differ from interface provider/consumer", "critical"],
                     ["V008", "Signal undefined, unused or without data type", "warning"],
                     ["V009", "Port name suffix disagrees with direction", "info"],
                     ["V010", "Component takes part in no interface", "info"],
                     ["V011", "Functional flow mentions an undefined signal/interface/port", "warning"]],
                    [16, 128, 26]),
              Spacer(1, 2 * mm),
              P("<b>Security and governance.</b> API keys map to roles (viewer, reviewer, admin) and projects; each document has its own vector "
                "collection and every route checks role and project; uploads, queries, reviews, exports, comparisons and deletions are written to an "
                "audit log; the reviewer recorded on a finding is the authenticated user."),
              P("10. Deployment and MLOps basics", H1)]
    story += bullets([
        f"<b>Model versioning and registry:</b> each trained model is stored under <font face='Courier'>models/answerability/v{META['version']}</font> "
        "(and <font face='Courier'>current</font>) with metadata: algorithm, hyperparameters, threshold, feature list, training and test documents, "
        f"dataset hash ({META['dataset_sha256_16']}), library version, git commit ({META['git_sha']}), seed and metrics. The service refuses to load a model "
        "whose feature list does not match the code.",
        "<b>Experiment tracking:</b> every training and retrieval experiment appends a JSON record (run id, timestamp, git commit, parameters, "
        "metrics, artefact paths) to <font face='Courier'>data/evaluation/runs.jsonl</font>.",
        "<b>Reproducibility:</b> fixed seeds, deterministic dataset generation, a dataset hash, pinned dependencies "
        "(<font face='Courier'>requirements-lock.txt</font>) and single-command scripts for every experiment (appendix).",
        "<b>Service traceability:</b> <font face='Courier'>GET /version</font> reports the git commit, embedding model, answerability model version, "
        "threshold, training documents and test F1 of the running service.",
        "<b>Docker:</b> one image with the embedding model baked in, docker-compose for API + UI with persistent volumes, and a single-container mode "
        "for one-port hosts (Render blueprint included). The build was verified, including login-enabled operation.",
        "<b>CI (simulated CD):</b> a GitHub Actions workflow runs lint, tests, the extraction/validation/Q&amp;A evaluations and a Docker build with "
        "a health and version smoke test on every push and pull request.",
    ])
    story.append(PageBreak())

    # ---- 11-12 responsible AI, innovation
    story += [P("11. Responsible AI and deployment ethics", H1)]
    story += bullets([
        "<b>Safety risk:</b> a wrong architecture answer could mislead a design review. Mitigations: answers use only retrieved evidence and graph "
        "facts, every answer cites section and page, a trained classifier refuses questions the document cannot answer, confidence is a calibrated "
        "probability, and findings need human accept/reject decisions. The report and UI carry an advisory notice; the system never approves a design.",
        "<b>Hallucination:</b> by default there is no generative model; an optional LLM is restricted to the retrieved evidence and instructed to reply 'not found' otherwise.",
        "<b>Privacy and confidentiality:</b> embeddings, vector store and database are local; the embedding model runs offline; external APIs are disabled by default and must be declared. Only synthetic documents are used.",
        "<b>Access control and accountability:</b> roles, per-project isolation, authenticated reviewer identity and a complete audit log.",
        "<b>Bias and fairness:</b> the data are technical documents, not personal data, so demographic bias does not apply; the relevant bias is "
        "<i>layout and vocabulary bias</i>: the system was built on documents with a single table layout and automotive vocabulary, and may fail silently on others. "
        "This is stated in the limitations, and the intended failure mode is refusal rather than a wrong answer.",
        "<b>Prompt injection:</b> document text is treated as data and delimited in prompts; not red-teamed.",
        "<b>Transparency:</b> model metadata, thresholds and training documents are exposed through /version and stored with the artefact.",
        "<b>Environmental/cost:</b> small CPU models (about 130 MB embedding model, a classifier of a few hundred KB) keep energy and cost low.",
    ])
    story += [P("12. Innovation highlights", H1)]
    story += bullets([
        "A learned, document-grouped answerability model that replaces a brittle similarity threshold and supplies calibrated confidence.",
        "Evidence-based design decisions: every component choice is backed by a measured comparison on held-out documents, including results that contradicted the initial design (equal-weight hybrid, PCA compression).",
        "Rule-based validation engine over a typed model of the HLD tables with page-level evidence and a human review workflow; verified on seeded defects.",
        "Revision comparison with graph-based change-impact analysis; interactive traceability graph and per-component cited reports.",
        "Leakage-aware evaluation: disjoint development and test documents, an untouched independent hand-written set, and recorded provenance for the model.",
    ])
    story.append(PageBreak())

    # ---- 13 screenshots
    story += [P("13. Screenshots and evidence", H1),
              P("Screenshots were captured automatically from the running application "
                "(<font face='Courier'>scripts/capture_screenshots.py</font>) using the two sample revisions.")]
    captions = {
        "01_home": "Figure 13: Home page.", "02_documents": "Figure 14: Documents page with project label.",
        "03_architecture_graph": "Figure 15: Interactive traceability graph.", "04_component_report": "Figure 16: Cited component report.",
        "05_impact_analysis": "Figure 17: Change-impact explorer.",
        "06_ask_grounded": "Figure 18: Grounded answer with citations and calibrated confidence.",
        "07_ask_refusal": "Figure 19: Refusal of an out-of-scope question.", "08_validation": "Figure 20: Validation findings and review actions.",
        "09_compare": "Figure 21: Revision comparison.", "10_report": "Figure 22: Report page with structured export.",
    }
    for stem, cap in captions.items():
        f = SHOTS / f"{stem}.png"
        if f.exists():
            story.append(fig(f, cap, 150))
    story += [P("Logs and raw results are included in the submission under Evaluation_Results/ (pytest output, metrics JSON, experiment log, "
                "sample outputs with citations).")]

    # ---- 14 reflection
    story += [P("14. Reflection and conclusions", H1),
              P("The strongest lesson was that decisions have to be measured. Three design choices that looked sensible were contradicted by held-out "
                "data: a similarity threshold tuned on one document did not transfer (it answered most unanswerable questions), an equal-weight hybrid "
                "retriever was worse than the dense model alone, and extractors tuned on one document missed half of the signals in other domains. "
                "Grouping cross-validation by document and keeping untouched test documents exposed these problems, and the fixes (a trained answerability "
                "model, a tuned fusion weight, table-driven extraction) each improved held-out results."),
              P("The main limitation is realism: all data are synthetic and share one layout, the question sets are small, and the system was not "
                "evaluated on real HLDs, scanned documents or with a generative model. Next steps are an independent evaluation set from real or "
                "differently structured HLDs, table-header mapping for other layouts, a verification step for 'absent attribute' questions, "
                "evaluation of a local LLM, a graph database for large documents and enterprise identity management."),
              P("<i>Personal reflection (to be written by the student):</i> what you learned, what was difficult, what you would do differently.", SMALL),
              P("Appendix: reproduction commands", H2),
              P("<font face='Courier' size=8>pip install -r requirements-dev.txt<br/>"
                "python scripts/generate_synthetic_hlds.py<br/>"
                "pytest<br/>"
                "python -m app.evaluation.extraction_eval --label after_fix --out data/evaluation/results<br/>"
                "python -m app.evaluation.train_answerability<br/>"
                "python -m app.evaluation.retrieval_experiments<br/>"
                "python -m app.evaluation.validation_eval --out data/evaluation/results<br/>"
                "python -m app.evaluation.eda<br/>"
                "python -m app.evaluation.run_eval --out data/evaluation/results<br/>"
                "docker compose up --build</font>", SMALL)]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=f"{TITLE} - Technical Report", author=NAME)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(20 * mm, 10 * mm, f"{REG} | {NAME} | CS1 Technical Report v1.0")
        canvas.drawRightString(190 * mm, 10 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onLaterPages=footer)
    print("wrote", OUT)


if __name__ == "__main__":
    build()
