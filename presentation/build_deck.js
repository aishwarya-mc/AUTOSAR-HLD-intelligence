// Builds the 8-slide project presentation from the measured results.
// Usage: node presentation/build_deck.js OUTPUT.pptx   (requires: npm install pptxgenjs)
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const RES = path.join(ROOT, "data/evaluation/results");
const load = (f) => JSON.parse(fs.readFileSync(path.join(RES, f), "utf8"));
const ANS = load("answerability_report.json");
const RES_ALL = load("results.json");
const RET = load("retrieval_experiments.json");
const VAL = load("validation_eval.json");
const EDA = load("eda_summary.json");
const EXT_B = load("extraction_corpus_before_fix.json").summary.overall;
const EXT_A = load("extraction_corpus_after_fix.json").test.summary.overall;

const tm = ANS.test_metrics, rb = ANS.rule_baseline_test;
const ind = RES_ALL.independent.trained, indOld = RES_ALL.independent.legacy_gate;
const pct = (x) => `${Math.round(x * 100)}%`;
const f2 = (x) => x.toFixed(2);

// ---- palette: deep navy (dominant), teal, amber accent; cool light background
const NAVY = "0B2545", TEAL = "13A89E", AMBER = "F4A259", INK = "1F2933", MUTED = "5B6B7B";
const LIGHT = "F3F6FA", WHITE = "FFFFFF", PALE = "DCE7F3";
const HEAD = "Cambria", BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Aishwarya Manoj";
pres.title = "AUTOSAR HLD Intelligence & Traceability Platform";

const W = 10, H = 5.625;

pres.defineSlideMaster({
  title: "LIGHT", background: { color: LIGHT },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.8,
    fontFace: HEAD, fontSize: 32, bold: true, color: NAVY, valign: "middle", margin: 0 }, text: "" } }],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontFace: BODY, fontSize: 10, color: MUTED },
});
pres.defineSlideMaster({
  title: "DARK", background: { color: NAVY },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.8,
    fontFace: HEAD, fontSize: 32, bold: true, color: WHITE, valign: "middle", margin: 0 }, text: "" } }],
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontFace: BODY, fontSize: 10, color: PALE },
});

const shadow = () => ({ type: "outer", color: "000000", blur: 6, offset: 2, angle: 90, opacity: 0.12 });
const text = (s, t, o) => s.addText(t, { isTextBox: true, fontFace: BODY, color: INK, margin: 0, ...o });

function card(s, x, y, w, h, fill = WHITE) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.08,
    line: { color: PALE, width: 0.75 }, shadow: shadow() });
}
function badge(s, x, y, label, color = TEAL) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.46, h: 0.46, fill: { color }, line: { color, width: 0 } });
  text(s, label, { x, y, w: 0.46, h: 0.46, align: "center", valign: "middle", fontSize: 16, bold: true, color: WHITE });
}

// ===== 1. Title
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addShape(pres.shapes.OVAL, { x: 7.1, y: -0.9, w: 4.4, h: 4.4, fill: { color: TEAL, transparency: 80 }, line: { color: TEAL, width: 0 } });
  s.addShape(pres.shapes.OVAL, { x: 8.2, y: 2.9, w: 2.6, h: 2.6, fill: { color: AMBER, transparency: 82 }, line: { color: AMBER, width: 0 } });
  text(s, "CASE STUDY CS1  |  AUTOMOTIVE ENGINEERING AI", { x: 0.6, y: 0.7, w: 8, h: 0.3, fontSize: 12, bold: true, color: AMBER, charSpacing: 3 });
  text(s, "AUTOSAR HLD Intelligence & Traceability Platform",
    { x: 0.6, y: 1.2, w: 7.4, h: 1.7, fontFace: HEAD, fontSize: 38, bold: true, color: WHITE, valign: "top" });
  text(s, "Evidence-grounded analysis of AUTOSAR High-Level Design documents: extraction, cited Q&A, validation and revision comparison",
    { x: 0.6, y: 3.0, w: 6.8, h: 0.9, fontSize: 16, color: PALE, valign: "top" });
  text(s, [
    { text: "Aishwarya Manoj", options: { bold: true, color: WHITE, breakLine: true } },
    { text: "CB.SC.U4AIE23211  |  Amrita Vishwa Vidyapeetham", options: { color: PALE } },
  ], { x: 0.6, y: 4.35, w: 7, h: 0.7, fontSize: 14 });
  s.addNotes("Introduce the project: a retrieval-augmented assistant for AUTOSAR HLD documents (Tata case study CS1). Everything runs locally; all data is synthetic.");
}

// ===== 2. Problem and users
{
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText("The problem: HLDs are read by hand", { placeholder: "title" });
  const rows = [
    ["1", "Long, unstructured PDFs", "Components, interfaces, ports, signals and flows are buried in tables across hundreds of pages."],
    ["2", "Mismatches go unnoticed", "Missing dependencies, wrong port directions and inconsistent names are found late."],
    ["3", "Impact is hard to judge", "Reviewers cannot quickly see what a change touches or compare revisions."],
  ];
  rows.forEach(([n, head, body], i) => {
    const y = 1.35 + i * 1.12;
    card(s, 0.5, y, 5.6, 0.98);
    badge(s, 0.68, y + 0.26, n);
    text(s, head, { x: 1.35, y: y + 0.1, w: 4.6, h: 0.3, fontSize: 16, bold: true, color: NAVY });
    text(s, body, { x: 1.35, y: y + 0.42, w: 4.6, h: 0.5, fontSize: 12, color: MUTED, valign: "top" });
  });
  card(s, 6.4, 1.35, 3.1, 3.3, NAVY);
  text(s, "Who it is for", { x: 6.65, y: 1.5, w: 2.7, h: 0.35, fontSize: 18, bold: true, color: AMBER, fontFace: HEAD });
  text(s, [
    { text: "System and AUTOSAR architects", options: { bullet: true, breakLine: true } },
    { text: "Software developers", options: { bullet: true, breakLine: true } },
    { text: "Integration engineers", options: { bullet: true, breakLine: true } },
    { text: "Test engineers", options: { bullet: true, breakLine: true } },
    { text: "Engineering managers", options: { bullet: true } },
  ], { x: 6.65, y: 1.95, w: 2.7, h: 1.7, fontSize: 14, color: WHITE, paraSpaceAfter: 4, valign: "top" });
  text(s, "Advisory only: a human reviews every finding.", { x: 6.65, y: 3.85, w: 2.7, h: 0.6, fontSize: 12, italic: true, color: PALE, valign: "top" });
  s.addNotes("Problem statement from the case study. The system is advisory: it never approves a design decision.");
}

// ===== 3. Solution and architecture
{
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText("The solution: an end-to-end pipeline", { placeholder: "title" });
  const steps = [
    ["Upload PDF", "validate, parse text and tables, OCR if scanned"],
    ["Extract", "components, interfaces, ports, signals, flows"],
    ["Index", "BGE embeddings in ChromaDB, plus BM25"],
    ["Decide", "trained model: answer or refuse"],
    ["Answer", "cited facts, confidence, human review"],
  ];
  const bw = 1.66, gap = 0.175;
  steps.forEach(([head, sub], i) => {
    const x = 0.5 + i * (bw + gap);
    card(s, x, 1.35, bw, 1.55, i === 3 ? NAVY : WHITE);
    text(s, head, { x: x + 0.12, y: 1.45, w: bw - 0.24, h: 0.35, fontSize: 16, bold: true, color: i === 3 ? AMBER : NAVY, fontFace: HEAD });
    text(s, sub, { x: x + 0.12, y: 1.85, w: bw - 0.24, h: 0.95, fontSize: 12, color: i === 3 ? WHITE : MUTED, valign: "top" });
    if (i < steps.length - 1)
      s.addText(">", { isTextBox: true, x: x + bw - 0.02, y: 1.95, w: gap + 0.04, h: 0.3, fontSize: 14, bold: true, color: TEAL, align: "center", margin: 0 });
  });
  const feats = [
    ["11 validation rules", "cross-table consistency with page evidence"],
    ["Revision comparison", "diff and change-impact between two HLDs"],
    ["Reports and export", "cited component reports, JSON and CSV"],
    ["Access and audit", "roles, project isolation, audit log"],
  ];
  feats.forEach(([head, sub], i) => {
    const x = 0.5 + i * 2.28;
    card(s, x, 3.2, 2.15, 1.5);
    s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: 3.35, w: 0.3, h: 0.3, fill: { color: TEAL }, line: { color: TEAL, width: 0 } });
    text(s, head, { x: x + 0.15, y: 3.75, w: 1.85, h: 0.3, fontSize: 14, bold: true, color: NAVY });
    text(s, sub, { x: x + 0.15, y: 4.08, w: 1.85, h: 0.55, fontSize: 12, color: MUTED, valign: "top" });
  });
  s.addNotes("Stack: Streamlit UI, FastAPI, PyMuPDF, BGE-small embeddings, ChromaDB, SQLite, scikit-learn model, Docker. Runs offline.");
}

// ===== 4. Data and EDA
{
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText("Data: synthetic, split by document", { placeholder: "title" });
  const stats = [
    [String(EDA.totals.documents), "synthetic HLDs", "6 development, 3 held-out, sample + revision"],
    ["528", "labelled questions", "answerable and unanswerable, balanced 50/50"],
    [String(EDA.totals.wrapped_underscore_cells), "table cells cleaned", "PDF line-wrap artefacts found by EDA"],
    ["0", "documents in both sets", "no leakage between train and test"],
  ];
  stats.forEach(([num, label, sub], i) => {
    const x = 0.5 + i * 2.28;
    card(s, x, 1.35, 2.15, 2.0);
    text(s, num, { x: x + 0.1, y: 1.45, w: 1.95, h: 0.85, fontSize: 48, bold: true, color: i === 2 ? AMBER : TEAL, fontFace: HEAD, align: "center", valign: "middle" });
    text(s, label, { x: x + 0.1, y: 2.3, w: 1.95, h: 0.3, fontSize: 14, bold: true, color: NAVY, align: "center" });
    text(s, sub, { x: x + 0.15, y: 2.62, w: 1.85, h: 0.65, fontSize: 12, color: MUTED, align: "center", valign: "top" });
  });
  card(s, 0.5, 3.6, 9, 1.2, NAVY);
  text(s, [
    { text: "Why synthetic? ", options: { bold: true, color: AMBER } },
    { text: "Real HLDs are confidential. Synthetic documents give exact ground truth and seeded defects. ", options: { color: WHITE } },
    { text: "Limit: one layout, so results show generalisation across domains, not real-world accuracy.", options: { color: PALE } },
  ], { x: 0.75, y: 3.7, w: 8.5, h: 1.0, fontSize: 14, valign: "middle" });
  s.addNotes("Mention the EDA findings: wrapped-underscore artefacts fixed in preprocessing, OCR trigger corrected, class balance, correlated features.");
}

// ===== 5. Approach and models (native charts)
{
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText("Choosing models with evidence", { placeholder: "title" });
  const a = RET.approaches;
  const tunedKey = Object.keys(a).find((k) => k.includes("tuned"));
  const retr = [
    ["BM25", a["BM25 (CamelCase-aware, used)"].test.mrr],
    ["TF-IDF", a["TF-IDF cosine"].test.mrr],
    ["MiniLM", a["Dense: MiniLM-L6"].test.mrr],
    ["BGE", a["Dense: BGE-small (used)"].test.mrr],
    ["Tuned hybrid", a[tunedKey].test.mrr],
  ];
  const cm = ANS.model_comparison;
  const clf = [
    ["Rule", cm["rule: sem_top1 >= 0.60 (previous)"].cv_auc_mean], ["Tree", cm.decision_tree.cv_auc_mean],
    ["LogReg", cm.logistic_regression.cv_auc_mean], ["SVM", cm.svm_rbf.cv_auc_mean],
    ["k-NN", cm.knn.cv_auc_mean], ["Forest", cm.random_forest.cv_auc_mean],
  ];
  const chartBase = (title, color) => ({
    showTitle: true, title, titleFontSize: 14, titleColor: NAVY, titleFontFace: BODY,
    chartColors: [color], showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
    dataLabelColor: INK, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, catAxisLabelColor: MUTED, valAxisLabelColor: MUTED,
    valGridLine: { color: "E1E8F0", size: 0.5 }, catGridLine: { style: "none" }, dataLabelFormatCode: "0.00", valAxisLabelFormatCode: "0.0",
  });
  card(s, 0.5, 1.3, 4.4, 3.1);
  s.addChart(pres.charts.BAR, [{ name: "MRR", labels: retr.map((r) => r[0]), values: retr.map((r) => r[1]) }],
    { x: 0.6, y: 1.35, w: 4.2, h: 3.0, barDir: "col", valAxisMinVal: 0.6, valAxisMaxVal: 1.0, ...chartBase("Retrieval, held-out MRR", TEAL) });
  card(s, 5.1, 1.3, 4.4, 3.1);
  s.addChart(pres.charts.BAR, [{ name: "AUC", labels: clf.map((r) => r[0]), values: clf.map((r) => r[1]) }],
    { x: 5.2, y: 1.35, w: 4.2, h: 3.0, barDir: "col", valAxisMinVal: 0.7, valAxisMaxVal: 1.0, ...chartBase("Answerability, nested CV AUC", AMBER) });
  text(s, [
    { text: "Dense weight tuned on development documents only. ", options: { bold: true, color: NAVY } },
    { text: "Six classifier families compared with leave-one-document-out cross-validation; random forest selected.", options: { color: MUTED } },
  ], { x: 0.5, y: 4.5, w: 9, h: 0.6, fontSize: 14, valign: "top" });
  s.addNotes("The equal-weight hybrid was worse than BGE alone, so the fusion weight was treated as a hyperparameter. PCA on embeddings lowered retrieval quality, so full 384 dimensions are kept.");
}

// ===== 6. Results (dark)
{
  const s = pres.addSlide({ masterName: "DARK" });
  s.addText("Results on unseen documents", { placeholder: "title" });
  const res = [
    [f2(tm.f1), "answerability F1", `rule baseline ${f2(rb.f1)}`],
    [pct(ind.refusal_accuracy), "refusals correct", `old threshold ${pct(indOld.refusal_accuracy)}`],
    [f2(EXT_A.f1), "extraction F1", `before fixes ${f2(EXT_B.f1)}`],
    [`${VAL.detected}/${VAL.seeded_defects}`, "defects found", "0 false findings on clean docs"],
  ];
  res.forEach(([num, label, sub], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.7;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.4, h: 1.5, fill: { color: "13315C" }, rectRadius: 0.08, line: { color: "1F4A80", width: 0.75 } });
    text(s, num, { x: x + 0.2, y: y + 0.15, w: 2.1, h: 1.2, fontSize: num.length > 5 ? 36 : 48, bold: true, color: AMBER, fontFace: HEAD, valign: "middle" });
    text(s, label, { x: x + 2.4, y: y + 0.35, w: 1.9, h: 0.35, fontSize: 16, bold: true, color: WHITE });
    text(s, sub, { x: x + 2.4, y: y + 0.75, w: 1.9, h: 0.5, fontSize: 12, color: PALE, valign: "top" });
  });
  text(s, `Independent hand-written questions: ${pct(ind.accuracy)} overall, ${pct(ind.answerable_accuracy)} of answerable ones answered. Small synthetic test sets.`,
    { x: 0.5, y: 4.75, w: 9, h: 0.5, fontSize: 12, italic: true, color: PALE, valign: "top" });
  s.addNotes("Be honest: the model refuses a few answerable paraphrased questions and answers one unanswerable question about a real entity. Test sets are small and synthetic.");
}

// ===== 7. Responsible AI and MLOps
{
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText("Responsible AI and MLOps", { placeholder: "title" });
  const cols = [
    ["Responsible AI", TEAL, [
      "Every answer cites page and section",
      "Refuses what the document cannot answer",
      "Calibrated confidence, human accept/reject",
      "Local models, synthetic data only",
      "Roles, project isolation, audit log",
    ]],
    ["MLOps basics", AMBER, [
      "Versioned model with metadata and dataset hash",
      "Experiment log and /version endpoint",
      "Docker image with embedding model baked in",
      "CI: lint, tests, evaluation, Docker smoke test",
      "Pinned dependencies, fixed seeds",
    ]],
  ];
  cols.forEach(([head, color, items], i) => {
    const x = 0.5 + i * 4.6;
    card(s, x, 1.3, 4.4, 3.2);
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: 1.45, w: 0.4, h: 0.4, fill: { color }, line: { color, width: 0 } });
    text(s, head, { x: x + 0.75, y: 1.42, w: 3.4, h: 0.46, fontSize: 20, bold: true, color: NAVY, fontFace: HEAD, valign: "middle" });
    text(s, items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })),
      { x: x + 0.25, y: 2.05, w: 3.95, h: 2.6, fontSize: 14, color: INK, paraSpaceAfter: 6, valign: "top" });
  });
  s.addNotes("Layout/vocabulary bias is the relevant bias for this data; the intended failure mode is refusal, not a wrong answer.");
}

// ===== 8. Contribution, limits, next steps
{
  const s = pres.addSlide({ masterName: "LIGHT" });
  s.addText("My contribution, limits and next steps", { placeholder: "title" });
  card(s, 0.5, 1.3, 4.4, 3.5);
  text(s, "What I built", { x: 0.75, y: 1.42, w: 3.9, h: 0.35, fontSize: 18, bold: true, color: TEAL, fontFace: HEAD });
  text(s, [
    { text: "Foundation, ingestion and OCR", options: { bullet: true, breakLine: true } },
    { text: "Section-aware chunking", options: { bullet: true, breakLine: true } },
    { text: "Entity extraction and deduplication", options: { bullet: true, breakLine: true } },
    { text: "Sample HLD generator and tests", options: { bullet: true, breakLine: true } },
    { text: "Project direction and review", options: { bullet: true } },
  ], { x: 0.75, y: 1.85, w: 3.9, h: 1.7, fontSize: 14, color: INK, paraSpaceAfter: 4, valign: "top" });
  text(s, "Retrieval, ML experiments, UI, security and deployment were built with AI assistance (Claude Code) under my direction and review.",
    { x: 0.75, y: 3.65, w: 3.9, h: 1.05, fontSize: 12, italic: true, color: MUTED, valign: "top" });
  card(s, 5.1, 1.3, 4.4, 3.5, NAVY);
  text(s, "Limits", { x: 5.35, y: 1.42, w: 3.9, h: 0.35, fontSize: 18, bold: true, color: AMBER, fontFace: HEAD });
  text(s, [
    { text: "Synthetic data, one layout", options: { bullet: true, breakLine: true } },
    { text: "Small test sets", options: { bullet: true, breakLine: true } },
    { text: "Local LLM and real scans not evaluated", options: { bullet: true } },
  ], { x: 5.35, y: 1.85, w: 3.9, h: 1.2, fontSize: 14, color: WHITE, paraSpaceAfter: 4, valign: "top" });
  text(s, "Next", { x: 5.35, y: 3.1, w: 3.9, h: 0.35, fontSize: 18, bold: true, color: AMBER, fontFace: HEAD });
  text(s, [
    { text: "Test on real HLD layouts", options: { bullet: true, breakLine: true } },
    { text: "Check absent attributes in evidence", options: { bullet: true, breakLine: true } },
    { text: "Evaluate a local LLM", options: { bullet: true } },
  ], { x: 5.35, y: 3.5, w: 3.9, h: 1.2, fontSize: 14, color: WHITE, paraSpaceAfter: 4, valign: "top" });
  s.addNotes("Be ready to explain every module in the left column and the AI-assisted modules too: you are accountable for all of it. Thank the audience and invite questions.");
}

const out = process.argv[2] || "presentation.pptx";
pres.writeFile({ fileName: out }).then(() => console.log("wrote", out));
