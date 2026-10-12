import json
import os
import time

import httpx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="AUTOSAR HLD Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

INK, TEAL, MUTED = "#E6EDF7", "#2DD4BF", "#94A3B8"  # text, accent number colour, secondary text (dark theme)
TYPE_COLORS = {
    "component": "#2563EB",
    "interface": "#0D9488",
    "port": "#D97706",
    "signal": "#BE185D",
}
SEVERITY = {"critical": "#B91C1C", "warning": "#B45309", "info": "#1D4ED8"}  # badge backgrounds (white text)
SEVERITY_TEXT = {"critical": "#F87171", "warning": "#FBBF24", "info": "#60A5FA"}  # numbers on dark cards
PAGES = ["Home", "Documents", "Architecture", "Ask", "Validation", "Compare", "Report", "System", "Audit"]

st.markdown(
    """
<style>
:root {--navy:#0A1626; --teal:#0F766E; --line:#24324D; --muted:#94A3B8; --bg:#0B1220; --card:#111B2F; --ink:#E6EDF7;}
#MainMenu, footer, header[data-testid="stHeader"] {display: none;}
[data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none;}
.stApp {background: var(--bg); color: var(--ink);}
html, body, [class*="css"] {font-family: "Segoe UI", "Inter", system-ui, -apple-system, sans-serif;}
.block-container {padding-top: 1.1rem; max-width: 1300px;}
h1, h2, h3, h4, h5 {color: var(--ink); letter-spacing: -0.01em;}
.topbar {
    display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    background: var(--navy); color: #fff; padding: .85rem 1.2rem; border-radius: 10px; margin-bottom: .9rem;
    border: 1px solid var(--line);
}
.brand {display: flex; align-items: center; gap: .8rem;}
.brand-mark {
    background: var(--teal); color: #fff; font-weight: 700; font-size: .85rem; letter-spacing: .06em;
    padding: .45rem .6rem; border-radius: 6px;
}
.brand-name {font-size: 1.1rem; font-weight: 600; line-height: 1.15;}
.brand-sub {font-size: .76rem; opacity: .72;}
.pills {display: flex; gap: .45rem; flex-wrap: wrap;}
.pill {
    font-size: .74rem; padding: .22rem .65rem; border-radius: 999px; border: 1px solid rgba(255,255,255,.28);
    background: rgba(255,255,255,.08); white-space: nowrap;
}
.pill .dot {display: inline-block; width: .5rem; height: .5rem; border-radius: 50%; margin-right: .4rem;}
.card {
    background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.15rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.35);
}
.card .num {font-size: 1.9rem; font-weight: 700; line-height: 1.1; color: var(--ink);}
.card .lbl {color: var(--muted); font-size: .76rem; text-transform: uppercase; letter-spacing: .06em; margin-top: .15rem;}
.card .sub {color: var(--muted); font-size: .82rem; margin-top: .35rem;}
.badge {
    display: inline-block; padding: .12rem .6rem; border-radius: 4px; font-size: .72rem; font-weight: 600;
    color: #fff; margin-right: .35rem; letter-spacing: .02em;
}
.badge.soft {background: #1E2B45; color: #CBD5E1;}
.step-title {font-weight: 600; color: var(--ink);}
.step-desc {color: var(--muted); font-size: .84rem; margin: .2rem 0 .6rem 0; min-height: 4.2rem;}
div[data-testid="stFileUploaderDropzone"] {border: 1.5px dashed #3B4F73; border-radius: 10px; background: var(--card);}
.stButton > button, .stDownloadButton > button {border-radius: 6px; font-weight: 500;}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {background: var(--teal); border-color: var(--teal);}
[data-testid="stExpander"] {background: var(--card); border-radius: 8px; border-color: var(--line);}
.section-note {color: var(--muted); font-size: .85rem; margin-bottom: .6rem;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- helpers


def api(method: str, path: str, quiet: bool = False, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    if st.session_state.get("api_key"):
        headers["X-API-Key"] = st.session_state["api_key"]
    try:
        resp = httpx.request(method, f"{API_URL}{path}", timeout=180, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        st.error(f"Cannot reach the API at {API_URL}: {exc}")
        st.stop()
    if resp.status_code == 401:
        st.warning("This server requires an access key. Open Access above and enter your API key.")
        return None
    if resp.status_code >= 400:
        if not quiet:
            try:
                body = resp.json()
                st.error(body.get("message") or body.get("detail") or resp.text)
            except ValueError:
                st.error(resp.text)
        return None
    return resp


def get_json(path: str, **kwargs):
    resp = api("GET", path, **kwargs)
    return resp.json() if resp is not None else None


@st.cache_data(ttl=10, show_spinner=False)
def system_status(api_key: str) -> dict | None:
    """Cached /version call for the status bar (never raises)."""
    try:
        headers = {"X-API-Key": api_key} if api_key else {}
        r = httpx.get(f"{API_URL}/version", timeout=4, headers=headers)
        return r.json() if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


def doc_label(d: dict) -> str:
    return f"{d['filename']}  |  {d['version']}"


def card(value, label, sub: str = "", color: str = INK) -> str:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="card"><div class="num" style="color:{color}">{value}</div>'
        f'<div class="lbl">{label}</div>{sub_html}</div>'
    )


def badge(text, color=None, soft=False) -> str:
    cls = "badge soft" if soft else "badge"
    style = "" if soft or color is None else f' style="background:{color}"'
    return f'<span class="{cls}"{style}>{text}</span>'


def goto(page: str) -> None:
    st.session_state["nav"] = page


def current_document():
    """Global document picker shown under the navigation bar."""
    docs = get_json("/documents") or []
    if not docs:
        st.info("No documents yet. Open the Documents page to upload an HLD or load the sample.")
        return None
    ids = [d["document_id"] for d in docs]
    if st.session_state.get("doc_id") not in ids:
        st.session_state["doc_id"] = ids[0]
    by_id = {d["document_id"]: d for d in docs}
    st.selectbox("Active document", ids, format_func=lambda i: doc_label(by_id[i]), key="doc_id")
    return st.session_state["doc_id"]


def header() -> None:
    status = system_status(st.session_state.get("api_key", ""))
    if status is None:
        pills = '<span class="pill"><span class="dot" style="background:#EF4444"></span>API offline</span>'
    else:
        llm = status.get("llm", {})
        model = status.get("answerability_model") or {}
        llm_ok = llm.get("ready")
        llm_text = f"LLM {llm.get('model')} ready" if llm_ok else (
            "LLM unavailable, extractive answers" if llm.get("enabled") else "LLM disabled")
        pills = (
            '<span class="pill"><span class="dot" style="background:#22C55E"></span>API online</span>'
            f'<span class="pill"><span class="dot" style="background:{"#22C55E" if llm_ok else "#F59E0B"}"></span>{llm_text}</span>'
            f'<span class="pill">Answerability model v{model.get("version", "-")}</span>'
            f'<span class="pill">{"Access control on" if status.get("auth_enabled") else "Access control off"}</span>'
        )
    st.markdown(
        '<div class="topbar"><div class="brand"><span class="brand-mark">HLD</span><div>'
        '<div class="brand-name">AUTOSAR HLD Intelligence</div>'
        '<div class="brand-sub">Architecture extraction, traceability and review</div></div></div>'
        f'<div class="pills">{pills}</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- pages


def page_home():
    docs = get_json("/documents") or []
    c = st.columns(4)
    c[0].markdown(card(len(docs), "Documents"), unsafe_allow_html=True)
    c[1].markdown(card(sum(d.get("entity_count", 0) for d in docs), "Architecture entities", color=TEAL),
                  unsafe_allow_html=True)
    c[2].markdown(card(sum(d.get("finding_count", 0) for d in docs), "Validation findings"), unsafe_allow_html=True)
    c[3].markdown(card(sum(d.get("page_count", 0) for d in docs), "Pages analysed"), unsafe_allow_html=True)
    st.write("")

    st.markdown("#### Workflow")
    st.markdown('<div class="section-note">Follow the steps in order, or jump to any step that is available.</div>',
                unsafe_allow_html=True)
    have, two = len(docs) > 0, len(docs) > 1
    steps = [
        ("1  Upload", "Add an HLD PDF or load the bundled sample.", "Documents", True, have),
        ("2  Explore", "Inspect components, ports, signals and the traceability graph.", "Architecture", have, False),
        ("3  Ask", "Question the document; answers cite their pages.", "Ask", have, False),
        ("4  Validate", "Review rule-based findings and record decisions.", "Validation", have, False),
        ("5  Compare", "Diff two revisions and see what a change affects.", "Compare", two, False),
    ]
    cols = st.columns(5)
    for col, (title, desc, target, enabled, done) in zip(cols, steps):
        with col:
            status = badge("Complete", "#15803D") if done else (badge("Available", soft=True) if enabled
                                                                else badge("Needs documents", "#94A3B8"))
            st.markdown(
                f'<div class="card"><div class="step-title">{title}</div><div class="step-desc">{desc}</div>{status}</div>',
                unsafe_allow_html=True,
            )
            st.button("Open", key=f"open_{target}", on_click=goto, args=(target,), disabled=not enabled,
                      width="stretch")

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Recent documents")
        if docs:
            df = pd.DataFrame(docs)[["filename", "version", "entity_count", "finding_count"]].head(6)
            df.columns = ["Document", "Revision", "Entities", "Findings"]
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("Nothing processed yet.")
    with right:
        st.markdown("#### Quick start")
        st.write("Load the synthetic Body Control System HLD to try every page.")
        if st.button("Load sample HLD", type="primary", width="stretch"):
            with st.spinner("Processing the sample document"):
                resp = api("POST", "/documents/sample")
            if resp is not None:
                st.toast("Sample HLD processed")
                st.rerun()
        st.caption("All findings are advisory and need review by a qualified engineer.")


def page_documents():
    st.markdown("#### Documents")
    left, right = st.columns([3, 2])
    with left:
        upload = st.file_uploader("Select or drag an HLD PDF", type=["pdf"])
        c1, c2 = st.columns(2)
        version = c1.text_input("Revision label", value="v1")
        project = c2.text_input("Project", value="default",
                                help="Documents are isolated per project; users only see projects they may access.")
        if st.button("Process document", type="primary", disabled=upload is None):
            with st.status("Processing document", expanded=True) as status:
                st.write("Validating the file and parsing text and tables")
                resp = api("POST", "/documents",
                           files={"file": (upload.name, upload.getvalue(), "application/pdf")},
                           data={"version": version, "project": project})
                if resp is not None:
                    m = resp.json()
                    st.write("Extracted entities, indexed the text, ran the validation rules")
                    status.update(label="Processing complete", state="complete")
                    st.session_state["doc_id"] = m["document_id"]
                    r = st.columns(3)
                    r[0].markdown(card(m["entity_count"], "Entities extracted"), unsafe_allow_html=True)
                    r[1].markdown(card(m["finding_count"], "Validation findings"), unsafe_allow_html=True)
                    r[2].markdown(card(m["page_count"], "Pages"), unsafe_allow_html=True)
                else:
                    status.update(label="Processing failed", state="error")
    with right:
        st.markdown(
            '<div class="card"><div class="step-title">No file at hand?</div>'
            '<div class="step-desc">Load the bundled synthetic Body Control System HLD.</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Load sample HLD", width="stretch"):
            with st.spinner("Processing the sample document"):
                resp = api("POST", "/documents/sample")
            if resp is not None:
                st.toast("Sample HLD processed")
                st.rerun()

    docs = get_json("/documents") or []
    if docs:
        st.divider()
        st.markdown("#### Processed documents")
        df = pd.DataFrame(docs)
        wanted = ["filename", "version", "project", "page_count", "entity_count", "finding_count", "created_at"]
        df = df[[c for c in wanted if c in df.columns]]
        st.dataframe(
            df, hide_index=True, width="stretch",
            column_config={
                "filename": "Document", "version": "Revision", "project": "Project", "page_count": "Pages",
                "entity_count": "Entities", "finding_count": "Findings", "created_at": "Processed at",
            },
        )
        with st.expander("Delete a document (admin only)"):
            victim = st.selectbox("Document", docs, format_func=doc_label, key="del_doc")
            if st.button("Delete permanently"):
                api("DELETE", f"/documents/{victim['document_id']}")
                st.toast("Document deleted")
                st.rerun()


def graph_html(graph: dict, visible_types: set, focus: str | None, physics: bool) -> str:
    nodes = [
        {
            "id": n["id"], "label": n["id"],
            "color": {"background": TYPE_COLORS.get(n["type"], "#94A3B8"), "border": "#FFFFFF" if n["id"] == focus else "#0B1220"},
            "shape": "dot" if n["type"] != "component" else "box",
            "font": {"color": "#F1F5F9", "size": 14},
            "borderWidth": 4 if n["id"] == focus else 1,
            "size": 22 if n["id"] == focus else 14,
            "title": f"{n['id']} ({n['type']})",
        }
        for n in graph["nodes"]
        if n["type"] in visible_types
    ]
    ids = {n["id"] for n in nodes}
    edges = [
        {
            "from": e["source"], "to": e["target"], "label": e["relation"].replace("_", " ").lower(),
            "arrows": "to", "font": {"size": 9, "color": "#94A3B8", "strokeWidth": 0},
            "color": {"color": "#64748B", "opacity": 0.75},
        }
        for e in graph["edges"]
        if e["source"] in ids and e["target"] in ids
    ]
    focus_js = (
        f"net.once('stabilizationIterationsDone', () => {{ net.selectNodes([{json.dumps(focus)}]); "
        f"net.focus({json.dumps(focus)}, {{scale: 1.1, animation: true}}); }});"
        if focus in ids else ""
    )
    return f"""
<div id="g" style="height:560px;border:1px solid #24324D;border-radius:10px;background:#070D18"></div>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<script>
const data = {{nodes: new vis.DataSet({json.dumps(nodes)}), edges: new vis.DataSet({json.dumps(edges)})}};
const net = new vis.Network(document.getElementById('g'), data, {{
  physics: {{enabled: {str(physics).lower()}, solver: 'forceAtlas2Based', stabilization: {{iterations: 150}}}},
  interaction: {{hover: true, navigationButtons: true, tooltipDelay: 100}},
  nodes: {{shadow: true}}
}});
{focus_js}
</script>"""


def page_architecture(doc):
    st.markdown("#### Architecture explorer")
    model = get_json(f"/architecture/{doc}/model")
    graph = get_json(f"/architecture/{doc}/graph")
    if not model or not graph:
        return

    cols = st.columns(5)
    for col, key in zip(cols, ["components", "interfaces", "ports", "signals", "dependencies"]):
        col.markdown(card(len(model[key]), key.title()), unsafe_allow_html=True)
    st.write("")

    view = st.segmented_control(
        "View", ["Interactive graph", "Tables", "Component report", "Functional flows", "Impact analysis"],
        default="Interactive graph", key="arch_view",
    )
    if view == "Interactive graph" or view is None:
        c1, c2, c3 = st.columns([3, 3, 1])
        types = c1.multiselect("Node types", list(TYPE_COLORS), default=list(TYPE_COLORS), key="graph_types")
        names = ["(none)"] + sorted(n["id"] for n in graph["nodes"])
        focus = c2.selectbox("Highlight element", names, key="graph_focus")
        physics = c3.toggle("Auto layout", value=True, key="graph_physics")
        focus = None if focus == "(none)" else focus
        st.markdown(
            "Drag nodes, scroll to zoom, hover for details.&nbsp; "
            + " ".join(badge(t.title(), c) for t, c in TYPE_COLORS.items()),
            unsafe_allow_html=True,
        )
        components.html(graph_html(graph, set(types), focus, physics), height=580)
        if focus:
            info = get_json(f"/architecture/{doc}/impact/{focus}", params={"depth": 1})
            if info:
                st.markdown(
                    f"**{focus}** {badge(info['type'].title(), TYPE_COLORS.get(info['type'], '#94A3B8'))} "
                    f"has {len(info['relationships'])} direct relationship(s):",
                    unsafe_allow_html=True,
                )
                rel = pd.DataFrame(info["relationships"])[["source", "relation", "target", "page"]]
                rel["relation"] = rel["relation"].str.replace("_", " ").str.lower()
                st.dataframe(rel, hide_index=True, width="stretch")
    elif view == "Component report":
        comp = st.selectbox("Component", [c["name"] for c in model["components"]])
        rep = api("GET", f"/reports/{doc}/component/{comp}")
        if rep is not None:
            st.markdown(rep.text)
            st.download_button("Download component report", rep.text, file_name=f"{comp}_report.md")
    elif view == "Tables":
        for key in ["components", "interfaces", "ports", "signals", "dependencies"]:
            with st.expander(f"{key.title()} ({len(model[key])})", expanded=key == "components"):
                st.dataframe(pd.DataFrame(model[key]), width="stretch", hide_index=True)
    elif view == "Functional flows":
        flows = get_json(f"/architecture/{doc}/entities", params={"entity_type": "functional_flow"})
        for f in flows or []:
            ev = f["evidence"][0]
            st.markdown(
                f'<div class="card"><b>{f["name"]}</b><br>{f["description"]}<br>'
                f'<span style="color:#94A3B8;font-size:.82rem">Evidence: {ev["section"]}, page {ev["page_number"]}</span>'
                "</div><div style='height:.6rem'></div>",
                unsafe_allow_html=True,
            )
    else:
        names = sorted(n["id"] for n in graph["nodes"])
        c1, c2 = st.columns([3, 1])
        element = c1.selectbox("Element", names)
        depth = c2.slider("Depth (hops)", 1, 4, 2)
        data = get_json(f"/architecture/{doc}/impact/{element}", params={"depth": depth})
        if data:
            st.markdown(
                f"**{element}** is a {badge(data['type'].title(), TYPE_COLORS.get(data['type'], '#64748B'))} "
                f"connected to **{len(data['impacted'])}** element(s) within {depth} hop(s).",
                unsafe_allow_html=True,
            )
            st.dataframe(pd.DataFrame(data["impacted"]), width="stretch", hide_index=True)


SUGGESTIONS = [
    "Which component provides IDoorStatus?",
    "What ports does BodyControlManager have?",
    "What signal does IWindowCommand carry?",
    "What does flow F-003 describe?",
]


def ask(doc: str, question: str):
    history = st.session_state.setdefault("chat", {}).setdefault(doc, [])
    history.append({"role": "user", "content": question})
    started = time.perf_counter()
    resp = api("POST", "/queries", json={"question": question, "document_id": doc})
    if resp is not None:
        history.append({"role": "assistant", "data": resp.json(), "seconds": time.perf_counter() - started})


def page_ask(doc):
    st.markdown("#### Ask the document")
    st.markdown('<div class="section-note">Answers are built from retrieved evidence and cite their pages. '
                "Questions the document cannot answer are refused.</div>", unsafe_allow_html=True)
    history = st.session_state.setdefault("chat", {}).setdefault(doc, [])

    if not history:
        st.caption("Suggested questions")
        cols = st.columns(len(SUGGESTIONS))
        for col, q in zip(cols, SUGGESTIONS):
            if col.button(q, key=f"sugg_{q}", width="stretch"):
                with st.spinner("Retrieving evidence and writing the answer"):
                    ask(doc, q)
                st.rerun()

    for msg in history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
            continue
        r = msg["data"]
        with st.chat_message("assistant"):
            badges = [badge("Answered", "#15803D") if r["grounded"] else badge("Not answerable", "#B45309")]
            if r["grounded"]:
                badges.append(badge("LLM wording: " + r["generated_by"], "#0F766E") if r.get("generated_by")
                              else badge("Extracted evidence", soft=True))
            badges.append(badge(f"Confidence {r['confidence']:.0%}", soft=True))
            badges.append(badge(f"{msg.get('seconds', 0):.1f} s", soft=True))
            st.markdown(" ".join(badges), unsafe_allow_html=True)
            if r["grounded"]:
                st.markdown(r["answer"])
                st.progress(min(max(r["confidence"], 0.0), 1.0))
                tabs = st.tabs(["Citations", "Verbatim facts"] if r.get("facts") else ["Citations"])
                with tabs[0]:
                    for c in r["citations"]:
                        with st.expander(f"[{c['citation_id']}]  {c['section']}  |  page {c['page_number']}"):
                            st.write(c["excerpt"])
                if r.get("facts"):
                    with tabs[1]:
                        st.caption("Facts read directly from the document tables. Check the wording above against these.")
                        for fact in r["facts"]:
                            st.markdown(f"- {fact}")
            else:
                st.warning(r["answer"])
            st.caption(" | ".join(r["limitations"]))

    question = st.chat_input("Ask about components, interfaces, ports, signals or flows")
    if question:
        with st.spinner("Retrieving evidence and writing the answer"):
            ask(doc, question)
        st.rerun()
    if history and st.button("Clear conversation"):
        st.session_state["chat"][doc] = []
        st.rerun()


def page_validation(doc):
    st.markdown("#### Validation findings")
    data = get_json(f"/validation/{doc}")
    if not data:
        return
    findings = data["findings"]
    s = data["summary"]
    c = st.columns(4)
    c[0].markdown(card(s.get("critical", 0), "Critical", color=SEVERITY_TEXT["critical"]), unsafe_allow_html=True)
    c[1].markdown(card(s.get("warning", 0), "Warning", color=SEVERITY_TEXT["warning"]), unsafe_allow_html=True)
    c[2].markdown(card(s.get("info", 0), "Info", color=SEVERITY_TEXT["info"]), unsafe_allow_html=True)
    reviewed = sum(1 for f in findings if (f["review"] or {}).get("status", "pending") != "pending")
    c[3].markdown(card(f"{reviewed} / {len(findings)}", "Reviewed", color=TEAL), unsafe_allow_html=True)
    st.write("")
    if not findings:
        st.success("No inconsistencies were detected by the rule set.")
        return
    st.progress(reviewed / len(findings), text=f"Review progress: {reviewed} of {len(findings)} findings decided")

    f1, f2, f3 = st.columns(3)
    sev = f1.multiselect("Severity", list(SEVERITY), default=list(SEVERITY))
    all_states = ["pending", "accepted", "rejected", "needs_review"]
    state = f2.multiselect("Review status", all_states, default=all_states)
    reviewer = f3.text_input("Reviewer", value="reviewer")

    for f in findings:
        status = (f["review"] or {}).get("status", "pending")
        if f["severity"] not in sev or status not in state:
            continue
        with st.expander(f"[{f['severity'].title()}]  {f['rule_id']}  |  {f['title']}  |  {status.replace('_', ' ')}"):
            st.markdown(
                badge(f["severity"].title(), SEVERITY[f["severity"]]) + badge(status.replace("_", " ").title(), soft=True)
                + badge(f"Confidence {f['confidence']:.0%}", soft=True),
                unsafe_allow_html=True,
            )
            st.write(f["description"])
            if f["evidence"]:
                ev = f["evidence"][0]
                st.caption(f"Evidence: {ev['section']}, page {ev['page_number']}")
                st.code(ev["excerpt"] or "", language=None)
            b = st.columns(3)
            for col, action, label in zip(b, ["accepted", "rejected", "needs_review"],
                                          ["Accept", "Reject", "Needs review"]):
                if col.button(label, key=f"{f['finding_id']}_{action}", width="stretch",
                              type="primary" if action == status else "secondary"):
                    api("POST", f"/validation/{doc}/review",
                        json={"finding_id": f["finding_id"], "status": action, "reviewer": reviewer})
                    st.toast(f"Marked as {action.replace('_', ' ')}")
                    st.rerun()


def page_compare():
    st.markdown("#### Revision comparison")
    docs = get_json("/documents") or []
    if len(docs) < 2:
        st.info("Process at least two revisions (for example upload sample_hld_v2.pdf) to compare them.")
        return
    by_id = {d["document_id"]: d for d in docs}
    ids = list(by_id)
    c1, c2 = st.columns(2)
    old = c1.selectbox("Baseline (old)", ids, index=min(1, len(ids) - 1), format_func=lambda i: doc_label(by_id[i]))
    new = c2.selectbox("Revision (new)", ids, index=0, format_func=lambda i: doc_label(by_id[i]))
    if old == new:
        st.warning("Choose two different documents.")
        return
    data = get_json("/comparison", params={"old_document_id": old, "new_document_id": new})
    if not data:
        return

    summ = data["summary"]
    left, right = st.columns([1, 2])
    left.markdown(card(summ["total_changes"], "Total changes", "added, removed or modified items"), unsafe_allow_html=True)
    chart = pd.DataFrame(
        {"Added": [summ[k]["added"] for k in data["categories"]],
         "Removed": [summ[k]["removed"] for k in data["categories"]],
         "Modified": [summ[k]["modified"] for k in data["categories"]]},
        index=[k.title() for k in data["categories"]],
    )
    right.bar_chart(chart, color=["#15803D", "#B91C1C", "#B45309"], height=230, horizontal=True)

    for cat, ch in data["categories"].items():
        if not any(ch.values()):
            continue
        st.markdown(f"#### {cat.title()}")
        for item in ch["added"]:
            st.markdown(badge("Added", "#15803D") + f"`{_label(item)}`", unsafe_allow_html=True)
        for item in ch["removed"]:
            st.markdown(badge("Removed", "#B91C1C") + f"`{_label(item)}`", unsafe_allow_html=True)
        for m in ch["modified"]:
            st.markdown(badge("Modified", "#B45309") + f"`{m['name']}`", unsafe_allow_html=True)
            st.dataframe(
                pd.DataFrame([{"Field": k, "Old": str(v["old"]), "New": str(v["new"])} for k, v in m["changes"].items()]),
                hide_index=True, width="stretch",
            )
    st.markdown("#### Change impact")
    st.caption("Unchanged elements that are connected to something that changed.")
    st.dataframe(pd.DataFrame(data["impact"]), hide_index=True, width="stretch")
    report = api("GET", f"/reports/{new}", params={"compare_with": old})
    if report is not None:
        st.download_button("Download comparison report (Markdown)", report.text,
                           file_name="hld_comparison_report.md", type="primary")


def _label(item: dict) -> str:
    if "relationship" in item:
        return f"{item['source']} {item['relationship']} {item['target']}"
    return item.get("name") or item.get("interface") or str(item)


def page_report(doc):
    st.markdown("#### Engineering report")
    resp = api("GET", f"/reports/{doc}")
    if resp is None:
        return
    top = st.columns([1, 3])
    top[0].download_button("Download report (Markdown)", resp.text, file_name="hld_report.md", type="primary",
                           width="stretch")
    with st.expander("Structured export for downstream tools", expanded=True):
        cols = st.columns(4)
        for col, (label, path, name) in zip(cols, [
            ("JSON bundle", f"/export/{doc}.json", "hld_export.json"),
            ("Entities (CSV)", f"/export/{doc}/entities.csv", "entities.csv"),
            ("Relationships (CSV)", f"/export/{doc}/relationships.csv", "relationships.csv"),
            ("Findings (CSV)", f"/export/{doc}/findings.csv", "findings.csv"),
        ]):
            data = api("GET", path)
            if data is not None:
                col.download_button(label, data.text, file_name=name, key=f"exp_{name}", width="stretch")
    st.divider()
    st.markdown(resp.text)


def page_system():
    st.markdown("#### System status")
    info = get_json("/version")
    if not info:
        return
    llm, model = info.get("llm", {}), info.get("answerability_model") or {}
    c = st.columns(4)
    c[0].markdown(card("Online", "API", f"version {info.get('app_version')} | build {info.get('git_sha')}"), unsafe_allow_html=True)
    c[1].markdown(card("Ready" if llm.get("ready") else "Not ready", "Local LLM",
                       f"{llm.get('provider')} : {llm.get('model')}"), unsafe_allow_html=True)
    c[2].markdown(card(info.get("embedding_model", "-").split("/")[-1], "Embedding model", "local, offline"),
                  unsafe_allow_html=True)
    c[3].markdown(card("On" if info.get("auth_enabled") else "Off", "Access control", "API-key roles"),
                  unsafe_allow_html=True)
    st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("##### Language model")
        st.write(f"Status: **{llm.get('detail')}**")
        if not llm.get("ready"):
            st.info("To enable LLM-written answers, install Ollama, run `ollama pull llama3.2`, and restart the API. "
                    "Until then the system shows the extracted evidence, so every answer stays correct.")
        st.caption("The LLM only rewrites retrieved evidence. A trained model decides whether to answer, and two guards "
                   "reject unfaithful wording.")
    with right:
        st.markdown("##### Answerability model")
        if model:
            st.dataframe(pd.DataFrame({
                "Item": ["Algorithm", "Version", "Decision threshold", "Test F1 (unseen documents)", "Trained on"],
                "Value": [model.get("algorithm"), model.get("version"), model.get("threshold"),
                          model.get("test_f1"), ", ".join(model.get("trained_on", []))],
            }), hide_index=True, width="stretch")


def page_audit():
    st.markdown("#### Audit log")
    st.caption("Admin only: uploads, questions, reviews, exports and deletions.")
    rows = get_json("/audit")
    if rows is not None:
        df = pd.DataFrame(rows)
        if not df.empty:
            users = st.multiselect("Filter by action", sorted(df["action"].unique()))
            if users:
                df = df[df["action"].isin(users)]
        st.dataframe(df, width="stretch", hide_index=True)


# ---------------------------------------------------------------- shell

header()
with st.expander("Access", expanded=False):
    st.text_input("API key (leave empty when access control is off)", type="password", key="api_key")

st.session_state.setdefault("nav", "Home")
st.segmented_control("Navigate", PAGES, key="nav", label_visibility="collapsed")
page = st.session_state.get("nav") or "Home"

if page == "Home":
    page_home()
elif page == "Documents":
    page_documents()
elif page == "Compare":
    page_compare()
elif page == "System":
    page_system()
elif page == "Audit":
    page_audit()
else:
    active = current_document()
    if active:
        {"Architecture": page_architecture, "Ask": page_ask, "Validation": page_validation, "Report": page_report}[page](active)
