"""Generate the technical report PDF.

Usage: python scripts/build_report.py OUTPUT.pdf [tests_passed]
Reads data/evaluation/results/results.json and submission_assets/screenshots/*.png.
"""
import json
import sys
from datetime import date
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "technical_report.pdf")
TESTS = sys.argv[2] if len(sys.argv) > 2 else "34"
RESULTS = json.loads((ROOT / "data/evaluation/results/results.json").read_text(encoding="utf-8"))
SHOTS = ROOT / "submission_assets" / "screenshots"

NAME, UNI, REG = "Aishwarya Manoj", "Amrita Vishwa Vidyapeetham", "CB.SC.U4AIE23211"
TITLE = "AUTOSAR HLD Intelligence & Traceability Platform"

NAVY = colors.HexColor("#17375E")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=NAVY, fontSize=16, spaceBefore=14, spaceAfter=8, keepWithNext=1)
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


def table(rows, widths, header=True, font=8.5):
    data = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E5F3"))]
    t.setStyle(TableStyle(style))
    return t


# ------------------------------------------------------------------ diagrams

def diagram(width, height, boxes, arrows, caption_font=7.5):
    """boxes: (x, y, w, h, text, fill). arrows: (x1, y1, x2, y2)."""
    d = Drawing(width, height)
    for x1, y1, x2, y2 in arrows:
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#555555"), strokeWidth=1))
        dx, dy = x2 - x1, y2 - y1
        n = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / n, dy / n
        d.add(Polygon([x2, y2, x2 - 6 * ux + 3 * uy, y2 - 6 * uy - 3 * ux,
                       x2 - 6 * ux - 3 * uy, y2 - 6 * uy + 3 * ux],
                      fillColor=colors.HexColor("#555555"), strokeColor=None))
    for x, y, w, h, text, fill in boxes:
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=colors.HexColor(fill),
                   strokeColor=colors.HexColor("#33415c"), strokeWidth=0.8))
        lines = text.split("\n")
        for i, line in enumerate(lines):
            ty = y + h / 2 + (len(lines) / 2 - i - 0.75) * (caption_font + 2)
            d.add(String(x + w / 2, ty, line, textAnchor="middle", fontSize=caption_font,
                         fontName="Helvetica-Bold" if i == 0 else "Helvetica"))
    return d


def architecture_diagram():
    c1, c2, c3, c4, c5 = "#DCE6F7", "#E2F0D9", "#FFF2CC", "#FCE4D6", "#EADCF4"
    boxes = [
        (170, 300, 180, 28, "Engineering users", "#FFFFFF"),
        (90, 250, 340, 32, "Streamlit UI\nnavigation | chat | graph | review | export", c1),
        (90, 195, 340, 40, "FastAPI service layer\nAPI-key auth | roles | project isolation | audit log", c2),
        (20, 105, 150, 70, "Ingestion + extraction\nPyMuPDF tables | OCR fallback\nsection chunker | entity rules", c3),
        (185, 105, 150, 70, "RAG layer\nBGE embeddings | ChromaDB\nBM25 + RRF | relevance gate", c3),
        (350, 105, 150, 70, "Analysis engines\n11 validation rules | revision diff\ngraph + impact | reports", c3),
        (20, 20, 150, 55, "SQLite\ndocuments | reviews | audit", c4),
        (185, 20, 150, 55, "ChromaDB (persistent)\none collection per document", c4),
        (350, 20, 150, 55, "Optional local LLM\nOllama (off by default)", c5),
    ]
    arrows = [(260, 300, 260, 282), (260, 250, 260, 235), (95, 195, 95, 175), (260, 195, 260, 175),
              (425, 195, 425, 175), (95, 105, 95, 75), (260, 105, 260, 75), (425, 105, 425, 75)]
    return diagram(520, 335, boxes, arrows)


def workflow_diagram():
    c = "#DCE6F7"
    names = ["Upload\nPDF", "Parse text,\ntables, OCR", "Section-aware\nchunking", "Entity extraction\n+ dedup",
             "Embed (BGE)\n+ index", "Validate\n(11 rules)"]
    boxes = [(8 + i * 85, 55, 76, 42, n, c) for i, n in enumerate(names)]
    arrows = [(8 + i * 85 + 76, 76, 8 + (i + 1) * 85, 76) for i in range(5)]
    boxes += [(8, 0, 160, 34, "Query: hybrid retrieve\nBM25 + vector + gate", "#E2F0D9"),
              (186, 0, 160, 34, "Grounded answer\ncitations + confidence", "#E2F0D9"),
              (364, 0, 150, 34, "Human review\naccept / reject / export", "#FFF2CC")]
    arrows += [(168, 17, 186, 17), (346, 17, 364, 17)]
    return diagram(520, 105, boxes, arrows, caption_font=7)


# ------------------------------------------------------------------ content

def build():
    ext, qa = RESULTS["extraction"], RESULTS["qa"]
    cfg = RESULTS["config"]
    story = []

    # Title page
    story += [Spacer(1, 50 * mm),
              P(f"<font size=24 color='#17375E'><b>{TITLE}</b></font>",
                ParagraphStyle("t", alignment=TA_CENTER, leading=30)),
              Spacer(1, 6 * mm),
              P("<font size=13>Technical Report</font>", ParagraphStyle("t2", alignment=TA_CENTER, leading=20, spaceAfter=6)),
              P("<font size=11>Case Study CS1: AUTOSAR HLD Document Analysis Assistant<br/>"
                "TechPulse FY-26 | Applied AI/ML Capstone</font>", ParagraphStyle("t3", alignment=TA_CENTER, leading=16)),
              Spacer(1, 25 * mm),
              table([["Student", NAME], ["Register number", REG], ["University", UNI],
                     ["Case study", "CS1: AUTOSAR HLD Document Analysis Assistant"],
                     ["Version / date", f"v1.0 / {date.today():%d %B %Y}"]], [45, 110], header=False),
              Spacer(1, 12 * mm),
              P("All input data is synthetic. AI-generated outputs are advisory and require review by a "
                "qualified engineer before use.", ParagraphStyle("n", parent=SMALL, alignment=TA_CENTER)),
              PageBreak()]

    # 1 Problem
    story += [P("1. Problem statement and intended users", H1),
              P("AUTOSAR High-Level Design (HLD) documents describe software components, interfaces, ports, signals, "
                "dependencies and functional flows. They are long, unstructured PDFs, so architects and integrators "
                "must read them manually to find mismatches, missing dependencies and inconsistent terminology, and "
                "to judge what a design change affects."),
              P("This project builds an evidence-grounded assistant that turns an HLD PDF into a structured, "
                "searchable repository, answers questions with page citations, flags potential inconsistencies, "
                "compares revisions and exports structured findings. It never approves a design decision: every "
                "output is advisory and goes through a human review step."),
              P("<b>Intended users:</b> system and AUTOSAR architects, software developers, integration engineers, "
                "test engineers and engineering managers (as listed in the CS1 brief)."),
              P("<b>Scope.</b> In scope: PDF ingestion with OCR fallback, section/table/metadata extraction, "
                "component/interface/port/signal/flow extraction, natural-language Q&amp;A with citations, "
                "revision comparison, inconsistency reporting, structured export. Out of scope: automatic approval "
                "of architecture decisions and modification of source HLDs."),

              # 2 Input data
              P("2. Input data and knowledge base", H1),
              P("Only synthetic data is used. Two documents were generated with ReportLab "
                "(<font face='Courier'>scripts/generate_sample_hld.py</font> and "
                "<font face='Courier'>generate_sample_hld_v2.py</font>); no confidential or customer content is involved."),
              table([["File", "Content", "Purpose"],
                     ["sample_hld.pdf (3 pages)", "Body Control System HLD: 4 components, 3 interfaces, 6 ports, 3 signals, "
                      "6 dependencies, 3 functional flows, integration constraints", "Baseline revision; consistent by design"],
                     ["sample_hld_v2.pdf (3 pages)", "Revision 2: adds ClimateControl, IClimateState and CabinTemperature, "
                      "widens VehicleSpeed to uint32, plus two seeded defects", "Revision comparison and validation tests"]],
                    [42, 80, 48]),
              Spacer(1, 3 * mm),
              P("<b>Seeded defects in revision 2:</b> WindowCommand_In is declared as a P-PORT although WindowControl is "
                "the consumer, and the dependency WindowControl REQUIRES_INTERFACE IVehicleState is missing from the "
                "dependency table. Ground truth for extraction and a 32-question Q&amp;A set were written by hand "
                "(<font face='Courier'>data/evaluation/</font>)."),

              # 3 Architecture
              P("3. Solution architecture", H1),
              P("The solution follows the common reference architecture of the case-study document: a Streamlit "
                "interface, a FastAPI service layer, a RAG layer with local embeddings and a local vector store, "
                "structured storage in SQLite, and Docker deployment."),
              architecture_diagram(),
              P("Figure 1: System architecture.", CAP),
              table([["Layer", "Choice in this project", "Reference stack in the brief / difference"],
                     ["UI", "Streamlit", "As recommended"],
                     ["API", "FastAPI (REST, OpenAPI docs)", "As recommended"],
                     ["Ingestion", "PyMuPDF (text, tables), Tesseract OCR fallback", "As recommended"],
                     ["Embeddings", f"{cfg['embedding_model']} via fastembed (ONNX, CPU, local)", "BGE family, as recommended"],
                     ["Vector store", "ChromaDB, persistent, one collection per document", "ChromaDB or FAISS"],
                     ["Retrieval", "Hybrid BM25 + vector, reciprocal rank fusion, relevance gate", "Extension of plain vector search"],
                     ["LLM", "Off by default (extractive grounded answers). Optional local LLM via Ollama; "
                      "optional Anthropic API, disabled by default and must be declared if used",
                      "Brief asks for a locally hosted LLM; see limitations"],
                     ["Structured store", "SQLite (documents, reviews, audit log)", "SQLite for pilot"],
                     ["Graph / traceability", "In-memory property graph built from the HLD tables", "Neo4j or equivalent; a lightweight equivalent is used"],
                     ["Deployment", "Docker, docker-compose, single-container mode", "Docker"]],
                    [30, 80, 60]),

              # 4 Implementation
              P("4. Implementation and configuration", H1),
              workflow_diagram(),
              P("Figure 2: Processing and query workflow.", CAP),
              P("4.1 Ingestion", H2),
              P("The PDF is validated (extension, size limit, <font face='Courier'>%PDF</font> signature), then parsed page by page "
                "with PyMuPDF. Text, headings and tables are kept with page numbers. Pages with fewer than 20 words are "
                "treated as scanned and passed to Tesseract OCR; OCR text replaces the page text only if it yields more words."),
              P("4.2 Chunking", H2),
              P("A section-aware chunker detects numbered headings, so a page holding several sections yields chunks "
                "tagged with the correct section and page. Chunks are word-based (default 250 words, 40 overlap, chosen to stay within the "
                "512-token limit of the embedding model). Chunk ids are deterministic hashes."),
              P("4.3 Entity extraction and normalisation", H2),
              P("Deterministic extractors (regular expressions and table parsing) produce components, interfaces, ports, signals, "
                "dependencies and functional flows, each with confidence and evidence (page, section, source text). A normaliser "
                "de-duplicates entities while merging evidence. A separate structured model parses the Interfaces, Ports, "
                "Signals and Dependencies tables into typed records used by the graph, validation and comparison engines. "
                "Deterministic extraction was chosen because every result is reproducible and auditable."),
              P("4.4 Retrieval and grounded answering", H2),
              P("Chunks are embedded with BGE-small and stored in ChromaDB. A query runs BM25 (keeps exact identifiers such as "
                "IDoorStatus reliable, with CamelCase/underscore-aware tokenisation) and vector search, fused with reciprocal "
                "rank fusion (k=60). A relevance gate refuses to retrieve anything when the best semantic similarity is "
                "below 0.60, so unrelated questions return 'not found in the document' instead of a guess. Entities named in the "
                "question are resolved against the graph and their relationships are added as cited structured facts. "
                "The answer lists the facts and the best-matching passages, with up to five citations (section and page) and a "
                "confidence value; if a local LLM is configured it only rewrites this evidence."),
              P("4.5 Validation engine", H2),
              table([["Rule", "Check", "Severity"],
                     ["V001", "Interface provider/consumer or port owner is not a declared component", "critical"],
                     ["V002", "Port references an interface that is not defined", "critical"],
                     ["V003", "Port direction contradicts the component's role (provider needs P-PORT, consumer R-PORT)", "critical"],
                     ["V004", "Interface provider/consumer has no matching port", "warning"],
                     ["V005", "Dependency table missing or contradicting the Interfaces table", "warning / critical"],
                     ["V006", "Unknown relationship type, or dependency targets an undefined interface", "warning / critical"],
                     ["V007", "Signal source/destination differs from its interface's provider/consumer", "critical"],
                     ["V008", "Signal used but undefined, defined but unused, or missing a data type", "warning"],
                     ["V009", "Port name suffix (_In/_Out) disagrees with its direction", "info"],
                     ["V010", "Component takes part in no interface", "info"],
                     ["V011", "Functional flow mentions an undefined signal, interface or port", "warning"]],
                    [16, 128, 26]),
              P("4.6 Revision comparison, reports and export", H2),
              P("Two revisions are diffed per category (added, removed, modified fields). A change-impact set lists unchanged "
                "elements within two graph hops of anything that changed, in either revision. Markdown reports are generated per "
                "document (with an optional revision diff) and per component, each statement citing its page. Structured export "
                "is available as a JSON bundle and as CSV (entities, relationships, findings)."),
              P("4.7 Security, governance and deployment", H2),
              P("API keys map to roles (viewer, reviewer, admin) and to the projects a user may access. Documents belong to a project; "
                "the vector store uses one collection per document, and every route checks role and project. Uploads, queries, reviews, "
                "exports, comparisons and deletions are written to an audit log (admin-only endpoint). Authentication is off by default "
                "for local development and enabled with <font face='Courier'>AUTH_ENABLED=true</font> and "
                "<font face='Courier'>API_KEYS</font>. The application runs from Docker with the embedding model baked into the image, so "
                "it works offline."),
              table([["Setting", "Value"],
                     ["Embedding model", f"{cfg['embedding_model']} (384-dim, ONNX)"],
                     ["Vector store / metric", "ChromaDB persistent, cosine"],
                     ["Chunking", "250 words, 40 overlap, section-aware"],
                     ["Retrieval", "BM25 + vector, RRF k=60, top_k=8, relevance gate 0.60, semantic-only floor 0.65"],
                     ["LLM", f"provider = {cfg['llm_provider']} (extractive answers); optional Ollama / Anthropic"]],
                    [45, 125]),
              PageBreak()]

    # 5 Evaluation
    rows = [["Entity type", "Expected", "Extracted", "Precision", "Recall"]]
    for kind, r in ext.items():
        if kind != "overall":
            rows.append([kind, r["expected"], r["extracted"], r["precision"], r["recall"]])
    rows.append(["<b>overall</b>", "", "", f"<b>{ext['overall']['precision']}</b>", f"<b>{ext['overall']['recall']}</b>"])
    story += [P("5. Evaluation steps and results", H1),
              P("<b>Method.</b> (1) Entity extraction is compared with a hand-built ground truth for the sample HLD "
                "(precision and recall per entity type). (2) A 32-question set (26 answerable across lookup, paraphrase, flow, data-type and "
                "integration categories; 6 unanswerable) measures answer correctness (expected terms present), whether a citation points to "
                "the expected page, groundedness (every answered question carries citations) and refusal accuracy. "
                f"(3) {TESTS} automated unit and integration tests cover parsing, extraction, validation rules, retrieval, API, "
                "security (roles, project isolation, audit) and export. All results are reproducible with "
                "<font face='Courier'>python -m app.evaluation.run_eval</font> and <font face='Courier'>pytest</font>."),
              P("5.1 Entity extraction", H2), table(rows, [50, 28, 28, 32, 32]),
              Spacer(1, 3 * mm),
              P("5.2 Question answering", H2),
              table([["Metric", "Result"],
                     ["Questions (answerable / unanswerable)", f"{qa['total_questions']} (26 / 6)"],
                     ["Overall accuracy", qa["accuracy_overall"]],
                     ["Accuracy on answerable questions", qa["answer_accuracy_answerable"]],
                     ["Citation on the expected page", qa["citation_page_hit_rate"]],
                     ["Groundedness (answers with valid citations)", qa["groundedness_valid_citations"]],
                     ["Refusal accuracy on unanswerable questions", qa["refusal_accuracy_unanswerable"]],
                     ["Per category", ", ".join(f"{k} {v}" for k, v in qa["by_category"].items())]], [90, 80]),
              Spacer(1, 3 * mm),
              P("5.3 Validation", H2),
              P("On revision 1 the engine reports no findings. On revision 2 it reports exactly the seeded problems: V003 "
                "(critical, WindowControl uses a P-PORT for IWindowCommand), V004 (warning, no R-PORT for it), V005 (warning, missing "
                "WindowControl REQUIRES_INTERFACE IVehicleState) and V009 (info, port naming), with no false positives. The comparison "
                "reports 10 changes between the revisions."),
              P("5.4 Honest reading of the results", H2)]
    story += bullets([
        "The scores are high because the benchmark is small, synthetic and written by the author of the system; thresholds "
        "(relevance gate, chunk size) were calibrated on the same document. They show the pipeline works end to end, not that it will "
        "reach the same accuracy on real HLDs.",
        "An earlier run of this evaluation exposed two weak answers (flow questions whose key sentence was cut off); the excerpt "
        "logic was changed to include the following sentence and the set re-run. The question set was not changed to make tests pass.",
        "Not evaluated: OCR quality on real scans, the optional local-LLM answer path, behaviour on documents whose table layout "
        "differs from the sample, and user-effort reduction (no baseline review time was measured).",
    ])

    # 6 Responsible AI
    story += [P("6. Responsible AI measures", H1)]
    story += bullets([
        "<b>Grounding:</b> answers are built from retrieved evidence and graph facts; each answer cites section and page. "
        "When nothing relevant is retrieved the system says so and gives no citations.",
        "<b>Confidence and limitations:</b> every answer shows a confidence value and a limitation note; the confidence is a heuristic "
        "from retrieval strength and entity recognition, not a calibrated probability.",
        "<b>Human oversight:</b> findings can be accepted, rejected or marked needs-review; the reviewer identity is taken from the "
        "authenticated key. The system never approves designs and the report carries an advisory notice.",
        "<b>Privacy and data residency:</b> embeddings, vector store and database are local; the embedding model runs offline from "
        "the image; the LLM is off by default. Optional external APIs are disabled by default and would need to be declared.",
        "<b>Security:</b> role-based access, project isolation (separate vector collection and project check per document), file "
        "type/size/signature checks on upload, and a complete audit log.",
        "<b>Data governance:</b> only synthetic documents are used; documents carry a version label.",
        "<b>Prompt-injection handling:</b> when a local LLM is used, retrieved document text is passed as delimited evidence and the "
        "model is told to answer only from it; this reduces but does not eliminate the risk and was not red-teamed.",
        "<b>Known limitations:</b> deterministic extraction depends on the documented table layout; diagrams in PDFs are not "
        "interpreted; authentication uses static API keys (no SSO); the in-memory graph is rebuilt from stored tables, not a "
        "graph database.",
    ])

    # 7 Innovation
    story += [P("7. Innovation highlights", H1)]
    story += bullets([
        "Hybrid retrieval with a calibrated relevance gate: exact-identifier recall from BM25 plus semantic recall from BGE, and "
        "principled refusal for out-of-scope questions.",
        "Table-aware structured model feeding a rule-based validation engine (11 rules) that finds real cross-table inconsistencies "
        "with page evidence, rather than relying on an LLM to notice them.",
        "Revision comparison with graph-based change-impact analysis across two revisions.",
        "Per-component cited reports and interactive traceability graph with an impact explorer.",
        "Offline-capable Docker deployment with RBAC, project isolation and audit trail.",
    ])
    story.append(PageBreak())

    # 8 Evidence
    story += [P("8. Screenshots, logs and evidence", H1),
              P("Screenshots were captured automatically from the running application "
                "(<font face='Courier'>scripts/capture_screenshots.py</font>) using the two sample revisions.")]
    captions = {
        "01_home": "Figure 3: Home page with summary metrics.",
        "02_documents": "Figure 4: Documents page with upload, project label and processed documents.",
        "03_architecture_graph": "Figure 5: Interactive traceability graph (revision 2).",
        "04_component_report": "Figure 6: Cited component report.",
        "05_impact_analysis": "Figure 7: Change-impact explorer.",
        "06_ask_grounded": "Figure 8: Grounded answer with citations and confidence.",
        "07_ask_refusal": "Figure 9: Refusal for an out-of-scope question.",
        "08_validation": "Figure 10: Validation findings with severity filters and review actions.",
        "09_compare": "Figure 11: Revision comparison.",
        "10_report": "Figure 12: Report page with structured export.",
    }
    for stem, cap in captions.items():
        f = SHOTS / f"{stem}.png"
        if f.exists():
            from PIL import Image as PILImage
            w, h = PILImage.open(f).size
            max_w, max_h = 165 * mm, 205 * mm
            scale = min(max_w / w, max_h / h)
            story.append(KeepTogether([Image(str(f), width=w * scale, height=h * scale), P(cap, CAP)]))
    story += [P("Test and evaluation logs are included in the submission under Evaluation_Results/ "
                "(pytest_output.txt, results.json, results.md, sample_outputs.md).")]

    # 9 Reflection
    story += [P("9. Reflection and conclusions", H1),
              P("The project shows that a large share of HLD review can be automated reliably when the document structure is exploited: "
                "tables give exact, citable facts, and rules over those facts find genuine inconsistencies that a language model might "
                "paraphrase away. Retrieval was useful mainly for narrative sections and paraphrased questions, and the relevance gate "
                "was essential: without it, semantic search returned plausible but unrelated passages for off-topic questions."),
              P("The main limitation is generality. Extraction was developed against one synthetic layout, so real HLDs will need table-header "
                "mappings and a larger, independently labelled benchmark. The next steps are an independent evaluation set, evaluation of a "
                "local LLM for fluent answers, a graph database for large documents and enterprise identity management."),
              P("<i>Personal reflection (to be written by the student):</i> what you learned, what was difficult, and what you would do differently.",
                SMALL)]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"{TITLE} - Technical Report", author=NAME)

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
