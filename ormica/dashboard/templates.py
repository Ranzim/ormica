"""HTML templates — stdlib string formatting, no Jinja, no SPA.

Every page is a complete document so it loads fast even on stale connections
and degrades gracefully without JS. The single ``<script>`` block on the
overview page hooks ``EventSource("/events")`` to render the live ticker.
"""
from __future__ import annotations

from html import escape


_BASE_CSS = """
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 980px; margin: 1.5rem auto; padding: 0 1rem;
         color: #1a1a1a; background: #fcfbf7; line-height: 1.5; }
  h1, h2 { margin-bottom: .25rem; color: #2c1810; }
  h1 { border-bottom: 2px solid #d4a368; padding-bottom: .4rem; }
  nav { margin: 1rem 0 1.5rem; padding: .5rem .75rem;
        background: #f3eee2; border-radius: 6px; }
  nav a { margin-right: 1rem; text-decoration: none; color: #2c1810;
          font-weight: 500; }
  nav a:hover { color: #d4a368; }
  pre { background: #f3eee2; padding: .75rem; border-radius: 6px;
        overflow-x: auto; font-size: .85rem; }
  table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
  th, td { padding: .4rem .6rem; text-align: left;
           border-bottom: 1px solid #e5dec9; }
  th { background: #f3eee2; }
  .tag { display: inline-block; padding: .1rem .4rem; border-radius: 4px;
         background: #d4a368; color: white; font-size: .75rem; margin-left: .25rem; }
  .tag.soft { background: #6c8b7a; }
  .tag.hard { background: #c97257; }
  .tag.stage { background: #5a7a9e; }
  .muted { color: #888; }
  .empty { color: #888; font-style: italic; padding: 1rem 0; }
  #live { margin-top: 1rem; padding: .5rem .75rem; background: #f8f4e8;
          border-left: 3px solid #d4a368; border-radius: 4px;
          font-family: ui-monospace, "SF Mono", monospace; font-size: .85rem;
          min-height: 2rem; max-height: 14rem; overflow-y: auto; }
  #live .row { padding: .15rem 0; }
"""


def _layout(*, title: str, body: str) -> str:
    return (
        "<!doctype html><html><head>"
        f'<meta charset="utf-8"><title>{escape(title)} — Ormica</title>'
        f"<style>{_BASE_CSS}</style></head><body>"
        f"<h1>{escape(title)}</h1>"
        '<nav><a href="/">overview</a>'
        '<a href="/tree">tree</a>'
        '<a href="/rules">rules</a>'
        '<a href="/signals">signals</a>'
        '<a href="/traces">traces</a></nav>'
        f"{body}"
        "</body></html>"
    )


def overview(org) -> str:
    tree_size = len(org)
    rules = list(org.constitution) if org.constitution is not None else []
    per_node = sum(1 for n in org if n.rules)
    trails = org.signals.trails()
    traces = [e for e in org.memory.all() if e.key.startswith("traces/")]

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
