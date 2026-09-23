"""HTML templates — stdlib string formatting, no Jinja, no SPA.

Every page is a complete document so it loads fast even on stale connections
and degrades gracefully without JS. The single ``<script>`` block on the
overview page hooks ``EventSource("/events")`` to render the live ticker.
"""
from __future__ import annotations

from html import escape


_BASE_CSS = """
  :root{--bg:#0a0f1a;--panel:rgba(20,28,44,.72);--line:rgba(140,165,200,.12);
    --text:#c9d4e3;--head:#eaf1fb;--muted:#6b7a90;--gold:#f4b942;--teal:#38e2c8;
    --blue:#5b9dff;--pink:#f472b6;--red:#f87171}
  *{box-sizing:border-box}
  body{font-family:ui-sans-serif,-apple-system,"Segoe UI",sans-serif;
    max-width:1000px;margin:0 auto;padding:0 1.1rem 3rem;color:var(--text);line-height:1.55;
    background:
      radial-gradient(ellipse at 22% 0%,rgba(96,128,255,.10),transparent 55%),
      radial-gradient(ellipse at 90% 10%,rgba(164,92,224,.09),transparent 55%),
      radial-gradient(ellipse at 50% 120%,rgba(40,204,184,.06),transparent 55%),
      linear-gradient(180deg,#0b1220,#070b14 60%,#04070e)}
  a{color:var(--teal);text-decoration:none}a:hover{color:var(--gold)}
  header{display:flex;align-items:center;gap:.6rem;padding:1.4rem 0 .3rem}
  header .brand{font-weight:700;letter-spacing:.5px;color:var(--head);font-size:1.15rem}
  header .brand b{color:var(--gold)}
  header .sub{color:var(--muted);font-size:.8rem;margin-left:.2rem}
  h1{font-size:1.5rem;color:var(--head);margin:.6rem 0 .2rem;font-weight:650}
  h2{font-size:.8rem;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);
    margin:1.6rem 0 .5rem;font-weight:600}
  nav{display:flex;flex-wrap:wrap;gap:.4rem;margin:.8rem 0 1.4rem}
  nav a{padding:.32rem .8rem;border-radius:999px;font-size:.82rem;font-weight:500;
    color:var(--text);background:rgba(255,255,255,.045);border:1px solid var(--line)}
  nav a:hover{background:rgba(244,185,66,.14);border-color:rgba(244,185,66,.35);color:var(--gold)}
  table{width:100%;border-collapse:separate;border-spacing:0;margin:.4rem 0;
    background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;
    backdrop-filter:blur(8px)}
  th,td{padding:.55rem .85rem;text-align:left;border-bottom:1px solid var(--line);font-size:.9rem}
  tr:last-child th,tr:last-child td{border-bottom:none}
  th{color:var(--muted);font-weight:600;width:40%}
  td{color:var(--head);font-variant-numeric:tabular-nums}
  pre{background:rgba(8,12,22,.7);padding:.8rem;border-radius:10px;border:1px solid var(--line);
    overflow-x:auto;font-size:.82rem;color:#dbe4f0}
  .tag{display:inline-block;padding:.12rem .5rem;border-radius:999px;font-size:.72rem;
    margin-left:.3rem;color:#08111a;font-weight:600;background:var(--gold)}
  .tag.soft{background:var(--teal)}.tag.hard{background:var(--red);color:#fff}
  .tag.stage{background:var(--blue);color:#fff}
  .muted{color:var(--muted)}
  .empty{color:var(--muted);font-style:italic;padding:1rem 0}
  #live{margin-top:1rem;padding:.6rem .85rem;background:rgba(8,12,22,.6);
    border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:10px;
    font-family:ui-monospace,"SF Mono",monospace;font-size:.82rem;color:#9fb0c6;
    min-height:2rem;max-height:15rem;overflow-y:auto}
  #live .row{padding:.15rem 0}
"""


def _layout(*, title: str, body: str) -> str:
    return (
        "<!doctype html><html><head>"
        f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} — Ormica</title>"
        f"<style>{_BASE_CSS}</style></head><body>"
        '<header><span class="brand">🐜 <b>ORMICA</b></span>'
        '<span class="sub">autonomous coordination engine</span></header>'
        '<nav><a href="/">overview</a>'
        '<a href="/graph">◆ live graph</a>'
        '<a href="/tree">tree</a>'
        '<a href="/rules">rules</a>'
        '<a href="/signals">signals</a>'
        '<a href="/traces">traces</a></nav>'
        f"<h1>{escape(title)}</h1>"
        f"{body}"
        "</body></html>"
    )


def overview(org) -> str:
    tree_size = len(org)
    rules = list(org.constitution) if org.constitution is not None else []
    per_node = sum(1 for n in org if n.rules)
    trails = org.signals.trails()
    traces = [e for e in org.memory.all() if e.key.startswith("traces/")]
    m = org.metrics()

    body = (
        '<div id="live"><div class="muted">live events stream here when the colony is running…</div></div>'
        f'<h2>colony: {escape(org.name)}</h2>'
        '<table>'
        f'<tr><th>nodes</th><td>{tree_size}</td></tr>'
        f'<tr><th>org-wide rules</th><td>{len(rules)}</td></tr>'
        f'<tr><th>nodes with per-node rules</th><td>{per_node}</td></tr>'
        f'<tr><th>active signals</th><td>{len(trails)}</td></tr>'
        f'<tr><th>stored traces</th><td>{len(traces)}</td></tr>'
        '</table>'
        '<h2>metrics</h2>'
        '<table>'
        f'<tr><th>tasks done</th><td>{m["tasks_done"]}</td></tr>'
        f'<tr><th>tasks failed</th><td>{m["tasks_failed"]}</td></tr>'
        f'<tr><th>dead-lettered</th><td>{m["colony"]["dead_letter"]}</td></tr>'
        f'<tr><th>failure rate</th><td>{m["failure_rate"]:.0%}</td></tr>'
        f'<tr><th>verify retries</th><td>{m["verify_retries"]}</td></tr>'
        f'<tr><th>tokens</th><td>{m["tokens"]:,}</td></tr>'
        '</table>'
        '<script>'
        '(function(){'
        ' var live=document.getElementById("live");'
        ' if(!window.EventSource){live.innerHTML="(EventSource not supported by this browser)";return;}'
        ' var es=new EventSource("/events");'
        ' live.innerHTML="";'
        ' es.onmessage=function(e){'
        '  var data=JSON.parse(e.data);'
        '  var row=document.createElement("div"); row.className="row";'
        '  var t=new Date(data.ts*1000).toISOString().slice(11,19);'
        '  row.textContent=t+"  "+data.type+"  "+JSON.stringify(data.payload);'
        '  live.insertBefore(row,live.firstChild);'
        '  while(live.children.length>200) live.removeChild(live.lastChild);'
        ' };'
        ' es.onerror=function(){};'
        '})();'
        '</script>'
    )
    return _layout(title="Overview", body=body)


def tree(org) -> str:
    rows: list[str] = []
    for node in org:
        indent = "&nbsp;" * (node.depth * 4)
        role = escape(node.role or "-")
        state = escape(node.state.value)
        rule_tag = (
            f' <span class="tag">{len(node.rules)} rule(s)</span>' if node.rules else ""
        )
        rows.append(
            f'<div>{indent}• <strong>{escape(node.name)}</strong> '
            f'<span class="muted">[{role}]</span> '
            f'<span class="tag stage">{state}</span>{rule_tag}</div>'
        )
    body = '<h2>tree</h2><pre>' + "".join(rows) + "</pre>"
    return _layout(title="Tree", body=body)


def rules(org) -> str:
    parts: list[str] = ['<h2>org-wide</h2>']
    org_rules = list(org.constitution) if org.constitution is not None else []
    if org_rules:
        parts.append('<table><tr><th>stage</th><th>severity</th><th>name</th><th>description</th></tr>')
        for r in org_rules:
            parts.append(
                f"<tr><td><span class='tag stage'>{escape(r.stage)}</span></td>"
                f"<td><span class='tag {escape(r.severity)}'>{escape(r.severity)}</span></td>"
                f"<td><code>{escape(r.name)}</code></td>"
                f"<td>{escape(r.description)}</td></tr>"
            )
        parts.append("</table>")
    else:
        parts.append('<div class="empty">no org-wide rules.</div>')

    parts.append('<h2>per-node</h2>')
    nodes = [n for n in org if n.rules]
    if not nodes:
        parts.append('<div class="empty">no per-node rules.</div>')
    for node in nodes:
        parts.append(f"<h3>{escape(node.name)} <span class='muted'>[{escape(node.role or '-')}]</span></h3>")
        parts.append('<table><tr><th>stage</th><th>severity</th><th>name</th><th>description</th></tr>')
        for r in node.rules:
            parts.append(
                f"<tr><td><span class='tag stage'>{escape(r.stage)}</span></td>"
                f"<td><span class='tag {escape(r.severity)}'>{escape(r.severity)}</span></td>"
                f"<td><code>{escape(r.name)}</code></td>"
                f"<td>{escape(r.description)}</td></tr>"
            )
        parts.append("</table>")
    return _layout(title="Rules", body="".join(parts))


def signals(org) -> str:
    trails = org.signals.trails()
    if not trails:
        body = '<div class="empty">no active signals.</div>'
        return _layout(title="Signals", body=body)
    rows: list[str] = []
    rows.append('<table><tr><th>topic</th><th>strength</th><th>sources</th></tr>')
    for s in trails:
        srcs = ", ".join(sorted(s.sources)) if s.sources else "-"
        rows.append(
            f"<tr><td><strong>{escape(s.topic)}</strong></td>"
            f"<td>{s.strength:.3f}</td>"
            f"<td>{escape(srcs)}</td></tr>"
        )
    rows.append("</table>")
    return _layout(title="Signals", body="".join(rows))


def traces_list(org) -> str:
    entries = [e for e in org.memory.all() if e.key.startswith("traces/")]
    if not entries:
        return _layout(
            title="Traces",
            body=(
                '<div class="empty">no stored traces. Run <code>ormica run</code> '
                "(with a configured <code>memory_db</code>) to populate them.</div>"
            ),
        )
    rows: list[str] = ['<table><tr><th>task id</th><th>target</th><th>status</th><th>description</th></tr>']
    for e in entries:
        task_id = e.key.split("/", 1)[1]
        data = e.value or {}
        rows.append(
            f"<tr><td><a href='/traces/{escape(task_id)}'><code>{escape(task_id)}</code></a></td>"
            f"<td>{escape(str(data.get('target') or '(root)'))}</td>"
            f"<td>{escape(str(data.get('status') or '?'))}</td>"
            f"<td>{escape(str(data.get('description') or ''))[:80]}</td></tr>"
        )
    rows.append("</table>")
    return _layout(title="Traces", body="".join(rows))


def trace_detail(org, task_id: str) -> str:
    trace = org.trace_for(task_id)
    if trace is None:
        return _layout(
            title=f"Trace {task_id}",
            body=(
                f'<div class="empty">no trace stored under task_id={escape(task_id)!r}.</div>'
            ),
        )
    parts: list[str] = [
        '<table>'
        f'<tr><th>task id</th><td><code>{escape(trace.task_id)}</code></td></tr>'
        f'<tr><th>target</th><td>{escape(trace.target or "(root)")}</td></tr>'
        f'<tr><th>status</th><td><span class="tag stage">{escape(trace.status)}</span></td></tr>'
        f'<tr><th>description</th><td>{escape(trace.description)}</td></tr>'
        '</table>'
    ]
    if trace.error:
        parts.append(f"<h2>error</h2><pre>{escape(trace.error)}</pre>")
    if trace.result:
        parts.append(f"<h2>result</h2><pre>{escape(trace.result)}</pre>")
    parts.append(f"<h2>think calls ({len(trace.entries)})</h2>")
    for i, entry in enumerate(trace.entries, start=1):
        parts.append(
            f'<h3>[{i}] tokens={entry.tokens_used} '
            f'tools={entry.tool_names or "-"}</h3>'
        )
        if entry.system:
            parts.append(f"<p><em>system:</em> {escape(entry.system)}</p>")
        if entry.messages:
            parts.append("<pre>")
            for msg in entry.messages:
                role = escape(str(msg.get("role", "?")))
                content = escape(str(msg.get("content", "")))
                parts.append(f"<strong>{role}:</strong> {content}\n")
            parts.append("</pre>")
        if entry.response_content:
            parts.append(f"<p><strong>→</strong> {escape(entry.response_content)}</p>")
    return _layout(title=f"Trace {task_id[:8]}", body="".join(parts))


# --- live graph ---------------------------------------------------------------

_INTERNAL_KEY_PREFIXES = ("stigma/", "mailbox/", "tasks/", "traces/")


def graph_state(org) -> dict:
    """Snapshot the current colony as a node/edge graph for the live view.

    Nodes: agents (root / dept / agent by depth) and knowledge (agent-authored
    mycelium entries — the internal signal/mailbox/task/trace keys are skipped).
    Edges: spawn lineage (parent→child) and memory authorship (agent→knowledge).
    """
    nodes = []
    edges = []
    agent_ids = set()
    for node in org:  # walks the tree
        depth = node.depth
        kind = "root" if node.is_root else ("dept" if depth == 1 else "agent")
        nodes.append(
            {"id": node.id, "label": node.name, "kind": kind,
             "role": node.role, "depth": depth}
        )
        agent_ids.add(node.id)
        if node.parent is not None:
            edges.append({"s": node.parent.id, "t": node.id, "kind": "spawn"})
    for entry in org.memory.all():
        if any(entry.key.startswith(p) for p in _INTERNAL_KEY_PREFIXES):
            continue
        kid = "k:" + entry.key
        nodes.append({"id": kid, "label": entry.key, "kind": "knowledge"})
        if entry.author in agent_ids:
            edges.append({"s": entry.author, "t": kid, "kind": "memory"})
    return {"nodes": nodes, "edges": edges}


def graph_page() -> str:
    """The live 3D colony graph + log view.

    Implemented in :mod:`ormica.dashboard.graph_view` (a self-contained,
    dependency-free page seeded from ``/graph/state`` and updated from
    ``/events``).
    """
    from . import graph_view

    return graph_view.page()


