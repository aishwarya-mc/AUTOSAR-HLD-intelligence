import json
import os

import httpx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="AUTOSAR HLD Intelligence",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TYPE_COLORS = {
    "component": "#6366f1",
    "interface": "#10b981",
    "port": "#f59e0b",
    "signal": "#ec4899",
}
SEVERITY = {
    "critical": ("🔴", "#ef4444"),
    "warning": ("🟠", "#f59e0b"),
    "info": ("🔵", "#3b82f6"),
}

st.markdown(
    """
<style>
#MainMenu, footer {visibility: hidden;}
[data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none;}
.block-container {padding-top: 4rem; max-width: 1280px;}
.hero {
    background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 55%, #db2777 100%);
    border-radius: 18px; padding: 2rem 2.2rem; color: #fff; margin-bottom: 1.2rem;
}
.hero h1 {margin: 0 0 .3rem 0; font-size: 2rem; color: #fff;}
.hero p {margin: 0; opacity: .92; font-size: 1.02rem;}
.card {
    border: 1px solid rgba(128,128,128,.25); border-radius: 14px;
    padding: 1rem 1.2rem; background: rgba(128,128,128,.07);
}
.card .num {font-size: 2rem; font-weight: 700; line-height: 1.1;}
.card .lbl {opacity: .7; font-size: .85rem; text-transform: uppercase; letter-spacing: .05em;}
.badge {
    display: inline-block; padding: .1rem .6rem; border-radius: 999px;
    font-size: .75rem; font-weight: 600; color: #fff; margin-right: .4rem;
}
.step {border-left: 4px solid #7c3aed; padding: .3rem 0 .3rem .9rem; margin-bottom: .7rem;}
div[data-testid="stFileUploaderDropzone"] {border: 2px dashed #7c3aed; border-radius: 14px;}
.stButton > button {border-radius: 10px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- helpers


def api(method: str, path: str, quiet: bool = False, **kwargs):
    try:
        resp = httpx.request(method, f"{API_URL}{path}", timeout=120, **kwargs)
    except httpx.HTTPError as exc:
        st.error(f"Cannot reach the API at {API_URL}: {exc}")
        st.stop()
    if resp.status_code >= 400:
        if not quiet:
            try:
                st.error(resp.json().get("message", resp.text))
            except ValueError:
                st.error(resp.text)
        return None
    return resp


def get_json(path: str, **kwargs):
    resp = api("GET", path, **kwargs)
    return resp.json() if resp is not None else None


def doc_label(d: dict) -> str:
    return f"{d['filename']} · {d['version']}"


def card(value, label, color="#7c3aed"):
    return (
        f'<div class="card"><div class="num" style="color:{color}">{value}</div>'
        f'<div class="lbl">{label}</div></div>'
    )


def badge(text, color):
    return f'<span class="badge" style="background:{color}">{text}</span>'


def current_document():
    """Global document picker shown under the navigation bar."""
    docs = get_json("/documents") or []
    if not docs:
        st.info("No documents yet — go to **Documents** to upload an HLD or load the sample.")
        return None
    ids = [d["document_id"] for d in docs]
    if st.session_state.get("doc_id") not in ids:
        st.session_state["doc_id"] = ids[0]
    by_id = {d["document_id"]: d for d in docs}
    st.selectbox(
        "Active document",
        ids,
        format_func=lambda i: doc_label(by_id[i]),
        key="doc_id",
    )
    return st.session_state["doc_id"]


# ---------------------------------------------------------------- pages


def page_home():
    st.markdown(
        '<div class="hero"><h1>AUTOSAR HLD Intelligence</h1>'
        "<p>Upload a High-Level Design, explore its architecture, ask questions with "
        "page-level citations, validate consistency and compare revisions.</p></div>",
        unsafe_allow_html=True,
    )
    docs = get_json("/documents") or []
    c = st.columns(4)
    c[0].markdown(card(len(docs), "Documents"), unsafe_allow_html=True)
    c[1].markdown(
        card(sum(d.get("entity_count", 0) for d in docs), "Entities", "#10b981"),
        unsafe_allow_html=True,
    )
    c[2].markdown(
        card(sum(d.get("finding_count", 0) for d in docs), "Findings", "#f59e0b"),
        unsafe_allow_html=True,
    )
    c[3].markdown(
        card(sum(d.get("page_count", 0) for d in docs), "Pages analysed", "#ec4899"),
        unsafe_allow_html=True,
    )
    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.subheader("How it works")
        for n, (t, d) in enumerate(
            [
                ("Upload", "Drop an HLD PDF on the Documents tab."),
                ("Explore", "Browse components, ports, signals and an interactive graph."),
                ("Ask", "Chat with the document; every answer cites its source pages."),
                ("Validate", "Review rule-based findings and accept / reject them."),
                ("Compare", "Diff two revisions and see what a change impacts."),
            ],
            1,
        ):
            st.markdown(f'<div class="step"><b>{n}. {t}</b><br>{d}</div>', unsafe_allow_html=True)
    with right:
        st.subheader("Quick start")
        st.write("No HLD at hand? Load the bundled synthetic Body Control System document.")
        if st.button("⚡ Load sample HLD", type="primary", width="stretch"):
            with st.spinner("Processing sample…"):
                resp = api("POST", "/documents/sample")
            if resp is not None:
                st.toast("Sample HLD processed", icon="✅")
                st.rerun()
        st.caption("AI-generated findings remain subject to human engineering review.")


def page_documents():
    st.subheader("Documents")
    left, right = st.columns([3, 2])
    with left:
        upload = st.file_uploader("Drag & drop an HLD PDF", type=["pdf"])
        c1, c2 = st.columns([2, 1])
        version = c1.text_input("Revision label", value="v1")
        c2.write("")
        c2.write("")
        if c2.button("Process", type="primary", disabled=upload is None, width="stretch"):
            with st.status("Processing document…", expanded=True) as status:
                st.write("Parsing PDF and tables")
                resp = api(
                    "POST",
                    "/documents",
                    files={"file": (upload.name, upload.getvalue(), "application/pdf")},
                    data={"version": version},
                )
                if resp is not None:
                    m = resp.json()
                    st.write("Extracted entities, built graph, ran validation")
                    status.update(label="Done", state="complete")
                    st.session_state["doc_id"] = m["document_id"]
                    st.success(
                        f"{m['filename']}: {m['entity_count']} entities, "
                        f"{m['finding_count']} findings, {m['page_count']} pages."
                    )
                else:
                    status.update(label="Failed", state="error")
    with right:
        st.markdown("**No file?**")
        if st.button("⚡ Load sample HLD", width="stretch"):
            with st.spinner("Processing sample…"):
                resp = api("POST", "/documents/sample")
            if resp is not None:
                st.toast("Sample HLD processed", icon="✅")
                st.rerun()

    docs = get_json("/documents") or []
    if docs:
        st.divider()
        st.markdown("#### Processed documents")
        df = pd.DataFrame(docs)[
            ["filename", "version", "page_count", "entity_count", "finding_count", "created_at"]
        ]
        st.dataframe(df, width="stretch", hide_index=True)
        with st.expander("Delete a document"):
            victim = st.selectbox("Document", docs, format_func=doc_label, key="del_doc")
            if st.button("Delete permanently"):
                api("DELETE", f"/documents/{victim['document_id']}")
                st.toast("Deleted", icon="🗑️")
                st.rerun()


def graph_html(graph: dict, visible_types: set, focus: str | None) -> str:
    nodes = [
        {
            "id": n["id"],
            "label": n["id"],
            "color": TYPE_COLORS.get(n["type"], "#94a3b8"),
            "shape": "dot" if n["type"] != "component" else "box",
            "font": {"color": "#e5e7eb" if n["type"] == "component" else "#cbd5e1", "size": 14},
            "borderWidth": 3 if n["id"] == focus else 1,
            "size": 14,
        }
        for n in graph["nodes"]
        if n["type"] in visible_types
    ]
    ids = {n["id"] for n in nodes}
    edges = [
        {
            "from": e["source"],
            "to": e["target"],
            "label": e["relation"].replace("_", " ").lower(),
            "arrows": "to",
            "font": {"size": 9, "color": "#94a3b8", "strokeWidth": 0},
            "color": {"color": "#64748b", "opacity": 0.7},
        }
        for e in graph["edges"]
        if e["source"] in ids and e["target"] in ids
    ]
    return f"""
<div id="g" style="height:560px;border:1px solid #64748b55;border-radius:14px;background:#0f172a"></div>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<script>
const data = {{nodes: new vis.DataSet({json.dumps(nodes)}), edges: new vis.DataSet({json.dumps(edges)})}};
new vis.Network(document.getElementById('g'), data, {{
  physics: {{solver: 'forceAtlas2Based', stabilization: {{iterations: 150}}}},
  interaction: {{hover: true, navigationButtons: true, tooltipDelay: 100}},
  nodes: {{shadow: true}}
}});
</script>"""


def page_architecture(doc):
    st.subheader("Architecture explorer")
    model = get_json(f"/architecture/{doc}/model")
    graph = get_json(f"/architecture/{doc}/graph")
    if not model or not graph:
        return

    cols = st.columns(5)
    for col, key, color in zip(
        cols,
        ["components", "interfaces", "ports", "signals", "dependencies"],
        ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#3b82f6"],
    ):
        col.markdown(card(len(model[key]), key.title(), color), unsafe_allow_html=True)
    st.write("")

    view = st.segmented_control(
        "View",
        ["Interactive graph", "Tables", "Functional flows", "Impact analysis"],
        default="Interactive graph",
        key="arch_view",
    )
    if view == "Interactive graph" or view is None:
        types = st.multiselect(
            "Show node types",
            list(TYPE_COLORS),
            default=list(TYPE_COLORS),
            key="graph_types",
        )
        st.markdown(
            "Drag nodes, scroll to zoom. &nbsp; "
            + " ".join(badge(t, c) for t, c in TYPE_COLORS.items()),
            unsafe_allow_html=True,
        )
        components.html(graph_html(graph, set(types), None), height=580)
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
                f'<span style="opacity:.6">Evidence: {ev["section"]}, page {ev["page_number"]}</span>'
                "</div><br>",
                unsafe_allow_html=True,
            )
    else:
        names = sorted(n["id"] for n in graph["nodes"])
        c1, c2 = st.columns([3, 1])
        element = c1.selectbox("Element", names)
        depth = c2.slider("Depth", 1, 4, 2)
        data = get_json(f"/architecture/{doc}/impact/{element}", params={"depth": depth})
        if data:
            st.markdown(
                f"**{element}** is a {badge(data['type'], TYPE_COLORS.get(data['type'], '#64748b'))}"
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
    resp = api("POST", "/queries", json={"question": question, "document_id": doc})
    if resp is not None:
        history.append({"role": "assistant", "data": resp.json()})


def page_ask(doc):
    st.subheader("Ask the HLD")
    history = st.session_state.setdefault("chat", {}).setdefault(doc, [])

    if not history:
        st.caption("Try one of these:")
        cols = st.columns(len(SUGGESTIONS))
        for col, q in zip(cols, SUGGESTIONS):
            if col.button(q, key=f"sugg_{q}", width="stretch"):
                ask(doc, q)
                st.rerun()

    for msg in history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            r = msg["data"]
            with st.chat_message("assistant"):
                if r["grounded"]:
                    st.markdown(r["answer"])
                    st.progress(r["confidence"], text=f"Confidence {r['confidence']:.0%}")
                    for c in r["citations"]:
                        with st.expander(f"📄 [{c['citation_id']}] {c['section']} — page {c['page_number']}"):
                            st.write(c["excerpt"])
                else:
                    st.warning(r["answer"])
                st.caption(" · ".join(r["limitations"]))

    question = st.chat_input("Ask about components, interfaces, ports, signals, flows…")
    if question:
        with st.spinner("Retrieving evidence…"):
            ask(doc, question)
        st.rerun()
    if history and st.button("Clear conversation"):
        st.session_state["chat"][doc] = []
        st.rerun()


def page_validation(doc):
    st.subheader("Validation findings")
    data = get_json(f"/validation/{doc}")
    if not data:
        return
    s = data["summary"]
    c = st.columns(3)
    c[0].markdown(card(s.get("critical", 0), "Critical", "#ef4444"), unsafe_allow_html=True)
    c[1].markdown(card(s.get("warning", 0), "Warning", "#f59e0b"), unsafe_allow_html=True)
    c[2].markdown(card(s.get("info", 0), "Info", "#3b82f6"), unsafe_allow_html=True)
    st.write("")
    if not data["findings"]:
        st.success("No inconsistencies detected by the rule set. 🎉")
        return

    f1, f2, f3 = st.columns([2, 2, 2])
    sev = f1.multiselect("Severity", list(SEVERITY), default=list(SEVERITY))
    state = f2.multiselect(
        "Review status", ["pending", "accepted", "rejected", "needs_review"],
        default=["pending", "accepted", "rejected", "needs_review"],
    )
    reviewer = f3.text_input("Reviewer", value="reviewer")

    for f in data["findings"]:
        status = (f["review"] or {}).get("status", "pending")
        if f["severity"] not in sev or status not in state:
            continue
        icon, color = SEVERITY[f["severity"]]
        with st.expander(f"{icon} {f['rule_id']} · {f['title']}"):
            st.markdown(
                badge(f["severity"], color) + badge(status.replace("_", " "), "#64748b")
                + f"confidence {f['confidence']:.0%}",
                unsafe_allow_html=True,
            )
            st.write(f["description"])
            if f["evidence"]:
                ev = f["evidence"][0]
                st.caption(f"Evidence — {ev['section']}, page {ev['page_number']}")
                st.code(ev["excerpt"] or "", language=None)
            b = st.columns(3)
            for col, action, label in zip(
                b,
                ["accepted", "rejected", "needs_review"],
                ["✅ Accept", "❌ Reject", "🔎 Needs review"],
            ):
                if col.button(label, key=f"{f['finding_id']}_{action}", width="stretch"):
                    api(
                        "POST",
                        f"/validation/{doc}/review",
                        json={"finding_id": f["finding_id"], "status": action, "reviewer": reviewer},
                    )
                    st.toast(f"Marked as {action.replace('_', ' ')}", icon="📝")
                    st.rerun()


def page_compare():
    st.subheader("Revision comparison")
    docs = get_json("/documents") or []
    if len(docs) < 2:
        st.info("Process at least two document revisions (e.g. upload `sample_hld_v2.pdf`) to compare.")
        return
    by_id = {d["document_id"]: d for d in docs}
    ids = list(by_id)
    c1, c2 = st.columns(2)
    old = c1.selectbox("Baseline (old)", ids, index=min(1, len(ids) - 1),
                       format_func=lambda i: doc_label(by_id[i]))
    new = c2.selectbox("Revision (new)", ids, index=0, format_func=lambda i: doc_label(by_id[i]))
    if old == new:
        st.warning("Choose two different documents.")
        return
    data = get_json("/comparison", params={"old_document_id": old, "new_document_id": new})
    if not data:
        return

    summ = data["summary"]
    cols = st.columns(len(data["categories"]) + 1)
    cols[0].markdown(card(summ["total_changes"], "Total changes", "#7c3aed"), unsafe_allow_html=True)
    for col, (cat, v) in zip(cols[1:], ((k, summ[k]) for k in data["categories"])):
        col.markdown(
            f'<div class="card"><div class="lbl">{cat}</div>'
            f'<span style="color:#10b981">+{v["added"]}</span> '
            f'<span style="color:#ef4444">−{v["removed"]}</span> '
            f'<span style="color:#f59e0b">~{v["modified"]}</span></div>',
            unsafe_allow_html=True,
        )
    st.write("")
    for cat, ch in data["categories"].items():
        if not any(ch.values()):
            continue
        st.markdown(f"#### {cat.title()}")
        for item in ch["added"]:
            st.markdown(badge("added", "#10b981") + f"`{_label(item)}`", unsafe_allow_html=True)
        for item in ch["removed"]:
            st.markdown(badge("removed", "#ef4444") + f"`{_label(item)}`", unsafe_allow_html=True)
        for m in ch["modified"]:
            st.markdown(badge("modified", "#f59e0b") + f"`{m['name']}`", unsafe_allow_html=True)
            st.dataframe(
                pd.DataFrame(
                    [{"field": k, "old": str(v["old"]), "new": str(v["new"])}
                     for k, v in m["changes"].items()]
                ),
                hide_index=True, width="stretch",
            )
    st.markdown("#### Change impact")
    st.caption("Unchanged elements connected to something that changed.")
    st.dataframe(pd.DataFrame(data["impact"]), hide_index=True, width="stretch")
    report = api("GET", f"/reports/{new}", params={"compare_with": old})
    if report is not None:
        st.download_button("⬇ Download comparison report (Markdown)", report.text,
                           file_name="hld_comparison_report.md", type="primary")


def _label(item: dict) -> str:
    if "relationship" in item:
        return f"{item['source']} {item['relationship']} {item['target']}"
    return item.get("name") or item.get("interface") or str(item)


def page_report(doc):
    st.subheader("Engineering report")
    resp = api("GET", f"/reports/{doc}")
    if resp is not None:
        st.download_button("⬇ Download Markdown", resp.text, file_name="hld_report.md", type="primary")
        st.divider()
        st.markdown(resp.text)


# ---------------------------------------------------------------- shell

PAGES = ["🏠 Home", "📄 Documents", "🧩 Architecture", "💬 Ask", "✅ Validation",
         "🔀 Compare", "📑 Report"]
page = st.segmented_control("Navigate", PAGES, default=PAGES[0], key="nav",
                            label_visibility="collapsed") or PAGES[0]

if page == "🏠 Home":
    page_home()
elif page == "📄 Documents":
    page_documents()
elif page == "🔀 Compare":
    page_compare()
else:
    active = current_document()
    if active:
        {
            "🧩 Architecture": page_architecture,
            "💬 Ask": page_ask,
            "✅ Validation": page_validation,
            "📑 Report": page_report,
        }[page](active)
