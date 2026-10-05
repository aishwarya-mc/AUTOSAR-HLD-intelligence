import os

import httpx
import pandas as pd
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="AUTOSAR HLD Intelligence", page_icon="🚗", layout="wide")


def api(method: str, path: str, **kwargs):
    try:
        resp = httpx.request(method, f"{API_URL}{path}", timeout=120, **kwargs)
    except httpx.HTTPError as exc:
        st.error(f"Cannot reach the API at {API_URL}: {exc}")
        st.stop()
    if resp.status_code >= 400:
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
    return f"{d['filename']} · {d['version']} · {d['document_id'][:12]}"


def pick_document(key: str, label: str = "Document"):
    docs = get_json("/documents") or []
    if not docs:
        st.info("No documents yet. Upload one on the **Documents** page.")
        return None
    chosen = st.selectbox(label, docs, format_func=doc_label, key=key)
    return chosen["document_id"] if chosen else None


# ---------------------------------------------------------------- pages


def page_home():
    st.title("AUTOSAR HLD Intelligence & Traceability Platform")
    st.markdown(
        "Evidence-grounded analysis of AUTOSAR High-Level Design documents: extraction, "
        "traceability, natural-language Q&A with citations, consistency validation, revision "
        "comparison and engineering reports."
    )
    st.caption("AI-generated findings remain subject to human engineering review.")
    docs = get_json("/documents") or []
    c1, c2, c3 = st.columns(3)
    c1.metric("Documents", len(docs))
    c2.metric("Architecture entities", sum(d.get("entity_count", 0) for d in docs))
    c3.metric("Validation findings", sum(d.get("finding_count", 0) for d in docs))
    if not docs:
        st.info("Start on the **Documents** page: upload an HLD PDF or load the bundled sample.")


def page_documents():
    st.header("Documents")
    left, right = st.columns(2)
    with left:
        st.subheader("Upload an HLD (PDF)")
        upload = st.file_uploader("PDF file", type=["pdf"])
        version = st.text_input("Revision label", value="v1")
        if st.button("Process document", disabled=upload is None, type="primary"):
            with st.spinner("Parsing, chunking, extracting and validating…"):
                resp = api("POST", "/documents",
                           files={"file": (upload.name, upload.getvalue(), "application/pdf")},
                           data={"version": version})
            if resp is not None:
                m = resp.json()
                st.success(f"Processed {m['filename']}: {m['entity_count']} entities, "
                           f"{m['finding_count']} findings.")
    with right:
        st.subheader("Try the sample")
        st.write("Synthetic Body Control System HLD bundled with the project.")
        if st.button("Load sample HLD"):
            with st.spinner("Processing sample…"):
                resp = api("POST", "/documents/sample")
            if resp is not None:
                st.success("Sample processed.")

    docs = get_json("/documents") or []
    if docs:
        st.subheader("Processed documents")
        st.dataframe(
            pd.DataFrame(docs)[["filename", "version", "page_count", "entity_count",
                                "finding_count", "created_at", "document_id"]],
            width="stretch", hide_index=True)
        victim = st.selectbox("Delete a document", [None] + docs,
                              format_func=lambda d: "—" if d is None else doc_label(d))
        if victim and st.button("Delete", type="secondary"):
            api("DELETE", f"/documents/{victim['document_id']}")
            st.rerun()


def page_architecture():
    st.header("Architecture explorer")
    doc = pick_document("arch_doc")
    if not doc:
        return
    model = get_json(f"/architecture/{doc}/model")
    tabs = st.tabs(["Components", "Interfaces", "Ports", "Signals", "Dependencies",
                    "Flows", "Graph / Impact"])
    for tab, key in zip(tabs[:5], ["components", "interfaces", "ports", "signals", "dependencies"]):
        with tab:
            st.dataframe(pd.DataFrame(model[key]), width="stretch", hide_index=True)
    with tabs[5]:
        for f in get_json(f"/architecture/{doc}/entities", params={"entity_type": "functional_flow"}):
            with st.expander(f["name"]):
                st.write(f["description"])
                ev = f["evidence"][0]
                st.caption(f"Evidence: {ev['section']}, page {ev['page_number']}")
    with tabs[6]:
        graph = get_json(f"/architecture/{doc}/graph")
        names = sorted(n["id"] for n in graph["nodes"])
        element = st.selectbox("Element for traceability / change-impact", names)
        depth = st.slider("Depth", 1, 4, 2)
        if element:
            data = get_json(f"/architecture/{doc}/impact/{element}", params={"depth": depth})
            st.markdown(f"**{element}** ({data['type']})")
            st.dataframe(pd.DataFrame(data["impacted"]), width="stretch", hide_index=True)
        with st.expander("Raw relationships"):
            st.dataframe(pd.DataFrame(graph["edges"]), width="stretch", hide_index=True)
        dot = ["digraph G { rankdir=LR; node [shape=box, style=rounded];"]
        for n in graph["nodes"]:
            dot.append(f'"{n["id"]}" [label="{n["id"]}\\n({n["type"]})"];')
        for e in graph["edges"]:
            dot.append(f'"{e["source"]}" -> "{e["target"]}" [label="{e["relation"]}"];')
        dot.append("}")
        st.graphviz_chart("\n".join(dot))


def page_ask():
    st.header("Ask the HLD")
    doc = pick_document("ask_doc")
    if not doc:
        return
    question = st.text_input("Question", placeholder="Which component provides IDoorStatus?")
    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("Retrieving evidence…"):
            resp = api("POST", "/queries", json={"question": question, "document_id": doc})
        if resp is None:
            return
        r = resp.json()
        st.markdown("### Answer")
        (st.success if r["grounded"] else st.warning)(r["answer"])
        st.caption(f"Confidence {r['confidence']:.0%} · grounded: {r['grounded']}")
        for c in r["citations"]:
            with st.expander(f"[{c['citation_id']}] {c['section']} — page {c['page_number']}"):
                st.write(c["excerpt"])
        for lim in r["limitations"]:
            st.caption(f"⚠ {lim}")


def page_validation():
    st.header("Validation findings")
    doc = pick_document("val_doc")
    if not doc:
        return
    data = get_json(f"/validation/{doc}")
    s = data["summary"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Critical", s.get("critical", 0))
    c2.metric("Warning", s.get("warning", 0))
    c3.metric("Info", s.get("info", 0))
    if not data["findings"]:
        st.success("No inconsistencies detected by the rule set.")
    reviewer = st.text_input("Reviewer name", value="reviewer")
    for f in data["findings"]:
        status = (f["review"] or {}).get("status", "pending")
        icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}[f["severity"]]
        with st.expander(f"{icon} {f['rule_id']} · {f['title']} — {status}"):
            st.write(f["description"])
            ev = f["evidence"][0] if f["evidence"] else None
            if ev:
                st.caption(f"Evidence: {ev['section']}, page {ev['page_number']}")
                st.code(ev["excerpt"] or "", language=None)
            cols = st.columns(3)
            for col, action in zip(cols, ["accepted", "rejected", "needs_review"]):
                if col.button(action.replace("_", " ").title(), key=f"{f['finding_id']}_{action}"):
                    api("POST", f"/validation/{doc}/review",
                        json={"finding_id": f["finding_id"], "status": action, "reviewer": reviewer})
                    st.rerun()


def page_compare():
    st.header("Revision comparison")
    docs = get_json("/documents") or []
    if len(docs) < 2:
        st.info("Process at least two document revisions to compare them.")
        return
    c1, c2 = st.columns(2)
    old = c1.selectbox("Baseline (old)", docs, index=1, format_func=doc_label, key="cmp_old")
    new = c2.selectbox("Revision (new)", docs, index=0, format_func=doc_label, key="cmp_new")
    if st.button("Compare", type="primary"):
        data = get_json("/comparison", params={"old_document_id": old["document_id"],
                                               "new_document_id": new["document_id"]})
        if not data:
            return
        st.metric("Total changes", data["summary"]["total_changes"])
        for cat, changes in data["categories"].items():
            if not any(changes.values()):
                continue
            st.subheader(cat.title())
            for kind in ("added", "removed"):
                if changes[kind]:
                    st.markdown(f"**{kind.title()}**")
                    st.dataframe(pd.DataFrame(changes[kind]), hide_index=True, width="stretch")
            for m in changes["modified"]:
                st.markdown(f"**Modified** `{m['name']}`")
                st.json(m["changes"])
        st.subheader("Change impact")
        st.caption("Unchanged elements connected to something that changed.")
        st.dataframe(pd.DataFrame(data["impact"]), hide_index=True, width="stretch")
        report = api("GET", f"/reports/{new['document_id']}",
                     params={"compare_with": old["document_id"]})
        if report is not None:
            st.download_button("Download report (Markdown)", report.text,
                               file_name="hld_comparison_report.md")


def page_reports():
    st.header("Engineering report")
    doc = pick_document("rep_doc")
    if not doc:
        return
    resp = api("GET", f"/reports/{doc}")
    if resp is not None:
        st.download_button("Download Markdown", resp.text, file_name="hld_report.md")
        st.markdown(resp.text)


PAGES = {
    "Home": page_home,
    "Documents": page_documents,
    "Architecture": page_architecture,
    "Ask the HLD": page_ask,
    "Validation": page_validation,
    "Compare revisions": page_compare,
    "Report": page_reports,
}

choice = st.sidebar.radio("Navigate", list(PAGES))
st.sidebar.caption(f"API: {API_URL}")
PAGES[choice]()
