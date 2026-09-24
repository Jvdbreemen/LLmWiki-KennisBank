#!/usr/bin/env python3
"""kb-mcp.py - lokale stdio MCP-server over de KennisBank (memory + wiki).

Het universele, ecosysteem-onafhankelijke oppervlak van de KennisBank (TASK-22):
elke compatibele MCP-client die op DEZELFDE machine draait (Claude Code, Codex,
GitHub Copilot in VS Code, Cline, Windsurf, LM Studio, Claude Desktop) kan de
vault gebruiken zonder platform-specifieke hook. MCP is het enige protocol dat
al die omgevingen al spreken, dus dit is het brede-bereik-oppervlak.

Primitieven:
  - recall (tool)        : doorzoek geheugen+wiki (PULL-retrieval). Read-only.
  - capture (tool)       : leg een nieuwe memory vast (PULL-write). Landt als
                           unverified/agent zodat de sweep-judge of de mens 'm
                           later promoot (mens = update-autoriteit).
  - what_did_i_do/timeline/weeklog/topic_timeline (tools): temporal activity
                           recall over de lokale activity index.
  - instructions: de pull-nudge die een client zonder push-hook toch naar recall
                           stuurt. Drie dragers, want clients verschillen: de
                           `instructions=`-constructorparameter (protocolniveau),
                           de `kennisbank://instructions`-resource, en de
                           managed block in .github/copilot-instructions.md.
                           Beide Copilot-oppervlakken roepen resources/list en
                           resources/read wel aan; VS Code biedt resources aan
                           als door de gebruiker aan te hangen context in plaats
                           van model-aanroepbaar, dus de copilot-instructions
                           blijft nodig.

Soevereiniteitsgrens (HARD): local-only. stdio-transport, geen netwerk-bind. De
vault verlaat de machine nooit. Remote/gehoste agents (cloud-ChatGPT) kunnen een
lokale stdio-server per definitie niet bereiken; daarvoor is er de manuele
export-bridge (kb-ask.py), niet een tunnel. Zie README / TASK-22.

De waarde zit in recall_tool()/capture_tool() (puur, testbaar zonder mcp/model);
de MCP-transport is een dunne, optioneel-gegate schil. Vereist `pip install mcp`
om de server te DRAAIEN; ontbreekt het pakket, dan blijven de *_tool-functies
bruikbaar. Stdlib + optioneel mcp.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Optionele MCP-SDK. Twee uitkomsten die NIET hetzelfde zijn en dus apart
# vastgelegd worden: het pakket ontbreekt (de gebruiker koos ervoor de server
# niet te draaien -> stil, exit 0), of het pakket is er maar de server-API is
# onbruikbaar (kapotte installatie -> luid, exit non-zero). Sinds SDK 2.0.0 is
# mcp.server.fastmcp verdwenen; die situatie samenvouwen tot "afwezig" gaf een
# stil dode MCP-server die van succes niet te onderscheiden was.
MCPServer = None
SDK_ABSENT = False          # pakket niet geinstalleerd
SDK_ERROR = ""              # niet-leeg: pakket aanwezig, API onbruikbaar
try:
    import mcp as _mcp_pkg  # noqa: F401  - alleen aanwezigheidscheck
except ImportError as exc:
    SDK_ABSENT = True
    SDK_ERROR = f"{type(exc).__name__}: {exc}"
else:
    try:
        from mcp.server.mcpserver import MCPServer as MCPServer  # type: ignore
    except Exception as exc_v2:
        try:
            from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
        except Exception as exc_v1:
            MCPServer = None
            SDK_ERROR = (f"mcp.server.mcpserver -> {type(exc_v2).__name__}: {exc_v2}; "
                         f"mcp.server.fastmcp -> {type(exc_v1).__name__}: {exc_v1}")

# Tool-annotaties. Clients leiden hier gedrag uit af: Claude Code berekent
# isReadOnly() EN isConcurrencySafe() uit annotations.readOnlyHint en zet beide
# op false als annotaties ontbreken. Zonder deze hints vragen onze read-only
# tools dus onnodig bevestiging en draaien ze serieel. Los importeren en
# fail-open, zodat de module bruikbaar blijft zonder het pakket.
try:
    from mcp.types import ToolAnnotations  # type: ignore
except Exception:
    ToolAnnotations = None


def _ann(**kw):
    """ToolAnnotations of None. Het label gaat in annotations.title en niet in de
    title=-kwarg: oudere SDK's kennen die kwarg niet en zouden een TypeError
    geven, terwijl annotations.title overal wordt gehonoreerd."""
    return ToolAnnotations(**kw) if ToolAnnotations is not None else None

# kb-recall via importlib (hyphen); module-globaal zodat tests het kunnen patchen.
kb_recall = None
kb_recall_error = ""
try:
    _spec = importlib.util.spec_from_file_location(
        "kb_recall", os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb-recall.py"))
    kb_recall = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(kb_recall)
except Exception as exc:
    kb_recall_error = f"{type(exc).__name__}: {exc}"
kb_recall_original = getattr(kb_recall, "recall_hits", None) if kb_recall is not None else None

activity = None
try:
    import _activity as activity  # type: ignore
except Exception:
    activity = None


def _load_optional_gateway(filename: str, name: str):
    try:
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(os.path.dirname(os.path.abspath(__file__)), filename))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


source_recall = _load_optional_gateway("kb-source-recall.py", "kb_source_recall")
experience_recall = _load_optional_gateway("kb-experience-recall.py", "kb_experience_recall")


def _compact_output_enabled() -> bool:
    """Whether this client should receive short human-readable MCP output."""
    return os.environ.get("KENNISBANK_MCP_COMPACT_OUTPUT", "").strip().lower() in {
        "1", "true", "yes",
    }


def _short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[:limit - 3].rstrip()}..."


def _compact_activity_result(result: dict[str, Any]) -> str:
    """Render activity data for interactive clients that display tool content."""
    warnings = result.get("warnings") or []
    if not result.get("ok", False):
        detail = _short_text("; ".join(map(str, warnings)), 240) or "unknown error"
        return f"KennisBank activity lookup failed: {detail}"

    period = result.get("period") or {}
    label = _short_text(period.get("label"), 80) or "requested period"
    events = result.get("events") or []
    summary = result.get("summary") or {}
    event_count = summary.get("event_count", len(events))
    lines = [f"KennisBank activity for {label}: {event_count} event(s)."]
    if not events:
        return "\n".join(lines + ["No matching activity events."])

    for event in events[:3]:
        title = _short_text(event.get("title") or event.get("activity_kind"), 100)
        detail = _short_text(event.get("summary"), 260)
        source = _short_text(event.get("source_ref"), 160)
        line = f"- {title}"
        if detail:
            line += f": {detail}"
        if source:
            line += f" ({source})"
        lines.append(line)
    if len(events) > 3:
        lines.append(f"- {len(events) - 3} additional event(s) omitted.")
    if warnings:
        lines.append(f"Warning: {_short_text('; '.join(map(str, warnings)), 240)}")
    return "\n".join(lines)


def _index_unavailable_line(code: str = "search_error", message: str = "") -> str:
    detail = str(message or "").strip()
    if code == "missing_index":
        return "KennisBank-index onbruikbaar: indexbestand ontbreekt."
    if code == "embed_mismatch":
        return f"KennisBank-index onbruikbaar: embedding-model wijkt af ({detail})."
    if code == "index_stamp_missing":
        return "KennisBank-index onbruikbaar: embed_id-stempel ontbreekt."
    if code == "sqlite_vec_missing":
        return "KennisBank-index onbruikbaar: sqlite-vec ontbreekt."
    if code == "extension_loading_unsupported":
        return "KennisBank-index onbruikbaar: Python sqlite3 heeft geen load_extension."
    if code == "vec0_unavailable":
        return f"KennisBank-index onbruikbaar: vec0 kon niet worden geladen ({detail or 'sqlite-vec'})"
    if code == "schema_error":
        return f"KennisBank-index onbruikbaar: indexschema klopt niet ({detail})."
    return f"KennisBank-index onbruikbaar: zoekfout ({detail or type(message).__name__})."


def recall_tool(query: str, k: int = 5, *, compact: bool = False) -> str:
    """Doorzoek de KennisBank en geef een onderscheid tussen leeg en onbruikbaar."""
    q = (query or "").strip()
    if not q:
        return ""
    try:
        import _embeddings as emb
        qvec = emb.embed_query(q)
    except Exception as exc:
        return f"Geen treffers (embedding-modelfout: {type(exc).__name__})."
    if not qvec:
        return "Geen treffers (embedding-model onbereikbaar)."
    if kb_recall is None:
        detail = kb_recall_error or "recall-module kon niet worden geladen"
        return f"KennisBank-index onbruikbaar: {detail}."
    try:
        if (hasattr(kb_recall, "recall_hits_with_status") and
                getattr(kb_recall, "recall_hits", None) is kb_recall_original):
            result = kb_recall.recall_hits_with_status(
                qvec, query_text=q, k=int(k), layers=("wiki", "memory"))
        else:
            legacy_hits = kb_recall.recall_hits(
                qvec, query_text=q, k=int(k), layers=("wiki", "memory"))
            result = {
                "status": "ok" if legacy_hits else "no_hit",
                "hits": legacy_hits,
                "code": "",
                "message": "",
            }
    except Exception as exc:
        code, message = getattr(kb_recall, "_index_error", lambda _e: ("search_error", str(_e)))(exc)
        return _index_unavailable_line(code, message)
    if result.get("status") == "unusable":
        return _index_unavailable_line(result.get("code", ""), result.get("message", ""))
    hits = result.get("hits") or []
    if not hits:
        return "Geen treffers in de KennisBank."
    lines = []
    for h in hits:
        tag = "geheugen" if h.get("layer") == "memory" else "wiki"
        stem = Path(h.get("path", "")).stem
        title = h.get("title", "")
        snippet = h.get("snippet", "")
        if compact:
            snippet = _short_text(snippet, 260)
        lines.append(f"- [{tag}] [[{stem}|{title}]] ({h.get('score', 0.0):.2f}): "
                     f"{snippet}")
    return "KennisBank-treffers:\n" + "\n".join(lines)


def source_recall_tool(query: str = "", mode: str = "explicit", k: int = 5,
                       source_ref: dict | None = None) -> str:
    """Explicit provenance-first source recall; never part of normal injection."""
    mode = str(mode or "normal").lower()
    if mode in {"fallback", "automatic", "advisory", "ranking", "promotion",
                "hook", "injection"}:
        return json.dumps({"status": "policy_disabled", "hits": [], "mode": mode})
    if source_recall is None:
        return '{"status": "unavailable", "hits": []}'
    try:
        if source_ref is not None and len(json.dumps(source_ref)) > 16384:
            return json.dumps({"status": "invalid", "hits": [], "mode": mode})
        request = {"mode": mode, "prompt": str(query or "")[:4000],
                   "k": min(max(int(k), 1), 20)}
        if source_ref is not None:
            request["source_ref"] = source_ref
        result = source_recall.run(request)
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    except Exception:
        return '{"status": "unavailable", "hits": []}'


def experience_recall_tool(query: str, mode: str = "explicit", k: int = 5) -> str:
    """Gated explicit recall of reviewed experience lessons."""
    mode = str(mode or "normal").lower()
    if mode in {"failure", "advisory", "automatic", "fallback", "ranking",
                "promotion", "hook", "injection"}:
        return json.dumps({"status": "policy_disabled", "hits": [], "mode": mode})
    if experience_recall is None:
        return '{"status": "unavailable", "hits": []}'
    try:
        result = experience_recall.run({
            "mode": mode, "prompt": str(query or "")[:4000],
            "k": min(max(int(k), 1), 3),
        })
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    except Exception:
        return '{"status": "unavailable", "hits": []}'


def capture_tool(title: str, body: str, memory_type: str = "feit",
                 importance: int = 3) -> str:
    """Leg een nieuwe memory vast in de KennisBank (PULL-write).

    Voor agents die geen KennisBank-hooks hebben en toch
    kennis willen bijdragen. De memory landt bewust als status=unverified,
    evidence_basis=agent: de sweep-judge of de mens promoot 'm later naar
    current (mens = update-autoriteit). Geen write-time reconcile hier — dat
    doet de eerstvolgende sweep, die embeddings heeft. Fail-soft: bij een lege
    titel/body of schrijffout een nette melding, nooit een crash.
    """
    t = (title or "").strip()
    b = (body or "").strip()
    if not t or not b:
        return "Niets vastgelegd: titel en inhoud zijn beide vereist."
    try:
        import _memory
        mt = _memory.coerce_memory_type(memory_type) if hasattr(_memory, "coerce_memory_type") else memory_type
        path, bestond_al = _memory.write_capture(
            t, b,
            status="unverified",
            evidence_basis="agent",
            memory_type=mt,
            importance=_memory.coerce_importance(importance) if hasattr(_memory, "coerce_importance") else importance,
        )
        if bestond_al:
            return (f"Stond er al, ongewijzigd gelaten: {Path(path).name}. "
                    f"Identieke inhoud, dus niets overschreven.")
        return (f"Vastgelegd als unverified memory: {Path(path).name}. "
                f"De volgende sweep of jij bevestigt 'm (mens = autoriteit).")
    except Exception as e:
        return f"Kon de memory niet vastleggen ({type(e).__name__}). Niets geschreven."


def review_pending_tool(k: int = 10) -> str:
    """Toon de unverified-memory-reviewwachtrij (TASK-89). Puur lezen."""
    try:
        import _memory
        items = _memory.pending_reviews(limit=int(k))
    except Exception:
        return "Review-queue niet leesbaar (fout bij scannen)."
    if not items:
        return "Review-queue leeg: geen unverified memories."
    lines = [f"Unverified memories ({len(items)} getoond, oudste eerst):"]
    for it in items:
        age = f"{it['age_days']}d" if it["age_days"] is not None else "?"
        lines.append(f"- [[{it['stem']}]] [{it['memory_type']}/{it['importance']}] "
                     f"({age}, {it['evidence_basis']}) {it['title']}: {it['snippet'][:120]}")
    return "\n".join(lines)


def review_decide_tool(stem: str, decision: str) -> str:
    """Voer één menselijke reviewbeslissing uit: approve|reject|skip.

    ALLEEN aanroepen nadat de gebruiker in het gesprek EXPLICIET per item
    heeft beslist — de agent beslist nooit zelf ("mens beslist", TASK-89).
    Crash-veilig: bij elke fout blijft het item unverified in de queue en
    komt de foutmelding terug; er wordt nooit stil "afgehandeld" gemeld.
    """
    try:
        import _memory
        r = _memory.decide((stem or "").strip(), (decision or "").strip(), via="mcp")
    except Exception as e:
        code = getattr(e, "code", None)
        tail = f" (code {code})" if code else ""
        return f"Niet doorgevoerd: {e}{tail}. Het item blijft in de queue."
    if r["status"] == "skipped":
        return f"Overgeslagen: [[{r['stem']}]] blijft unverified in de queue."
    return f"Beslist: [[{r['stem']}]] -> {r['new_status']}."


def _activity_unavailable() -> dict[str, Any]:
    return {
        "ok": False,
        "warnings": ["Temporal Activity Recall module is niet beschikbaar."],
        "events": [],
    }


def _activity_call(fn_name: str, *args, **kwargs) -> "dict[str, Any] | str":
    """Shared dispatcher for the four activity tools (TASK-190): the
    unavailable-guard, exception-to-warnings translation and compact
    rendering existed four times and were already free to drift. Reads
    module-global `activity` at call time so tests can keep patching it.
    The int() coercion stays INSIDE the try: an unparseable max_events must
    yield the warnings dict, never a raised ValueError."""
    if activity is None:
        result = _activity_unavailable()
    else:
        try:
            kwargs["max_events"] = int(kwargs["max_events"])
            result = getattr(activity, fn_name)(*args, **kwargs)
        except Exception as e:
            result = {"ok": False,
                      "warnings": [f"{fn_name} failed: {type(e).__name__}"],
                      "events": []}
    return _compact_activity_result(result) if _compact_output_enabled() else result


def what_did_i_do_tool(date_or_period: str, topic: str = "", project: str = "",
                       max_events: int = 25) -> "dict[str, Any] | str":
    """Temporal activity recall voor een datum/periode."""
    return _activity_call("what_did_i_do", date_or_period or "today",
                          topic=topic or "", project=project or "",
                          max_events=max_events)


def timeline_tool(period: str, topic: str = "", project: str = "",
                  max_events: int = 50) -> "dict[str, Any] | str":
    """Chronologische temporal activity timeline."""
    return _activity_call("timeline", period or "today",
                          topic=topic or "", project=project or "",
                          max_events=max_events)


def weeklog_tool(period: str = "vorige week", topic: str = "", project: str = "",
                 max_events: int = 100) -> "dict[str, Any] | str":
    """Weekoverzicht met rollup en source_refs."""
    return _activity_call("weeklog", period or "vorige week",
                          topic=topic or "", project=project or "",
                          max_events=max_events)


def topic_timeline_tool(topic: str, period: str = "afgelopen 90 dagen",
                        project: str = "", max_events: int = 80) -> "dict[str, Any] | str":
    """Volg een onderwerp of entity door de tijd."""
    return _activity_call("topic_timeline", topic or "",
                          period_text=period or "afgelopen 90 dagen",
                          project=project or "", max_events=max_events)


# Pull-nudge voor MCP-clients zonder push-hook (zie module-docstring). Drie
# dragers naast elkaar, omdat geen enkele op zichzelf elke client bereikt: de
# instructions=-parameter van de constructor, deze tekst als resource, en de
# managed block in .github/copilot-instructions.md.
INSTRUCTIONS_TEXT = (
    "You have a local KennisBank (personal memory + curated wiki) available "
    "through the MCP tools `recall`, `source_recall`, `experience_recall` and `capture`.\n\n"
    "- Call `recall` BEFORE searching externally or making an assumption: your "
    "own earlier lessons, decisions and bug fixes may already be in there.\n"
    "- Call `capture` whenever a reusable fact, preference, procedure or "
    "decision appears that you want back in a later session.\n"
    "- For an explicit question about what worked before, call `experience_recall` "
    "first. Call `source_recall` only on demand when the user needs underlying "
    "evidence, reconstruction, or verification. Neither route is automatic.\n"
    "- Call `what_did_i_do`, `timeline`, `weeklog` or `topic_timeline` for "
    "questions about what happened on a date, in a week, or around a topic.\n"
    "- `review_pending` lists unverified memories awaiting human review; "
    "`review_decide` applies a decision - ONLY after the user explicitly "
    "decided per item (approve/reject/skip). Never decide on their behalf.\n"
    "- The KennisBank is local and sovereign: nothing goes to the cloud."
)


def build_server():
    """Bouw de MCP-server met recall + capture + instructions. None als mcp ontbreekt."""
    if MCPServer is None:
        return None
    # instructions= is de protocol-drager van de pull-nudge. Guarded, want een
    # SDK die de kwarg niet kent mag de server niet onderuit halen.
    try:
        srv = MCPServer("kennisbank-geheugen", instructions=INSTRUCTIONS_TEXT)
    except TypeError:
        srv = MCPServer("kennisbank-geheugen")

    @srv.tool(annotations=_ann(title="Recall knowledge", readOnlyHint=True, openWorldHint=False))
    def recall(query: str, k: int = 5) -> str:
        """Search your own KennisBank (personal memory + curated wiki) BEFORE
        searching externally or making an assumption. Give a short query; get the
        best-matching entries back."""
        compact = _compact_output_enabled()
        return recall_tool(query, k=min(int(k), 3) if compact else k, compact=compact)

    @srv.tool(annotations=_ann(title="Recall source evidence", readOnlyHint=True, openWorldHint=False))
    def source_recall(query: str = "", mode: str = "explicit", k: int = 5,
                      source_ref: dict | None = None) -> str:
        """On demand, retrieve hash- and offset-bound source passages for
        explicit reconstruction or verification. Never automatic or normal injection."""
        return source_recall_tool(query, mode=mode, k=k, source_ref=source_ref)

    @srv.tool(annotations=_ann(title="Recall validated experience", readOnlyHint=True, openWorldHint=False))
    def experience_recall(query: str, mode: str = "explicit", k: int = 3) -> str:
        """For explicit prior-experience questions, retrieve at most three
        validated outcome-bound lessons first; use source_recall afterward only
        when deeper evidence is requested. Candidates, unknown outcomes, and
        automatic advisories remain excluded."""
        return experience_recall_tool(query, mode=mode, k=k)

    @srv.tool(annotations=_ann(title="Capture a memory", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
    def capture(title: str, body: str, memory_type: str = "feit",
                importance: int = 3) -> str:
        """Record a reusable fact, preference, procedure or decision in the
        KennisBank. It lands as unverified: the sweep or the user promotes it
        later. The user stays the update authority."""
        return capture_tool(title, body, memory_type=memory_type, importance=importance)

    @srv.tool(annotations=_ann(title="List memories awaiting review", readOnlyHint=True, openWorldHint=False))
    def review_pending(k: int = 10) -> str:
        """List unverified memories waiting for human review, oldest first.
        Read-only: it decides nothing."""
        return review_pending_tool(k=k)

    @srv.tool(annotations=_ann(title="Decide one review item", readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False))
    def review_decide(stem: str, decision: str) -> str:
        """Apply one review decision (approve|reject|skip) - ONLY after the user
        explicitly decided about this specific item in the conversation. Never
        decide on their behalf: show review_pending first and ask per item."""
        return review_decide_tool(stem, decision)

    @srv.tool(annotations=_ann(title="What happened on a date", readOnlyHint=True, openWorldHint=False))
    def what_did_i_do(date_or_period: str, topic: str = "", project: str = "",
                      max_events: int = 25) -> "dict[str, Any] | str":
        """Answer what happened locally on a given date or in a period. Returns
        the events with their source references, any warnings, and a summary."""
        return what_did_i_do_tool(date_or_period, topic=topic, project=project,
                                  max_events=max_events)

    @srv.tool(annotations=_ann(title="Activity timeline", readOnlyHint=True, openWorldHint=False))
    def timeline(period: str, topic: str = "", project: str = "",
                 max_events: int = 50) -> "dict[str, Any] | str":
        """List the INDIVIDUAL activity events in chronological order for a
        period, optionally filtered by topic or project. Prefer weeklog when an
        aggregated summary is wanted instead of every single event."""
        return timeline_tool(period, topic=topic, project=project,
                             max_events=max_events)

    @srv.tool(annotations=_ann(title="Week overview", readOnlyHint=True, openWorldHint=False))
    def weeklog(period: str = "vorige week", topic: str = "", project: str = "",
                max_events: int = 100) -> "dict[str, Any] | str":
        """Summarise a week into an AGGREGATED rollup per day, with source
        references. Prefer timeline when the individual events are wanted."""
        return weeklog_tool(period=period, topic=topic, project=project,
                            max_events=max_events)

    @srv.tool(annotations=_ann(title="Topic through time", readOnlyHint=True, openWorldHint=False))
    def topic_timeline(topic: str, period: str = "afgelopen 90 dagen",
                       project: str = "", max_events: int = 80) -> "dict[str, Any] | str":
        """Follow one topic or entity through time across activity events, to see
        how it developed."""
        return topic_timeline_tool(topic, period=period, project=project,
                                   max_events=max_events)

    # Instructions-resource (best-effort: niet elke MCP-SDK-versie kent .resource()).
    try:
        @srv.resource("kennisbank://instructions")
        def instructions() -> str:
            """Hoe je de KennisBank-tools inzet (pull-nudge)."""
            return INSTRUCTIONS_TEXT
    except Exception:
        pass

    return srv


def main() -> int:
    srv = build_server()
    if srv is None:
        if SDK_ABSENT:
            # Legitieme keuze: geen MCP-pakket, dus geen MCP-server. Stil en 0.
            sys.stderr.write(
                "kb-mcp: the 'mcp' package is not installed, so the MCP server is "
                "not available. Install it with 'pip install \"mcp>=2.0.0,<3\"'.\n")
            return 0
        # Pakket aanwezig maar onbruikbaar: dat is een defect, geen keuze.
        sys.stderr.write(
            "kb-mcp: the 'mcp' package is installed but its server API could not be "
            f"imported, so the MCP server did NOT start.\n  {SDK_ERROR}\n"
            "  Expected 'mcp>=2.0.0,<3'. Reinstall with "
            "'pip install --upgrade \"mcp>=2.0.0,<3\"'.\n")
        return 1
    srv.run()  # stdio-transport (default)
    return 0


if __name__ == "__main__":
    # Geen blanket 'except Exception: exit(0)': dat maakte elke startfout
    # onzichtbaar. Een gesloten pipe of Ctrl-C is normale beeindiging; al het
    # andere hoort met een traceback en een non-zero exit naar buiten te komen.
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError):
        sys.exit(0)
