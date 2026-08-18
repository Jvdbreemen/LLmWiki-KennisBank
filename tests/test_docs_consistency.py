"""Documentatie-guards: tweetalige feitpariteit en code-afgeleide feiten.

Aanleiding (TASK-59). De doc-drift in deze repo had één mechanisme: documentatie
wordt per opsomming bijgewerkt, en wat niet op de lijst staat blijft staan. Eén
commit raakte beide README's maar corrigeerde alleen de Engelse alinea, waardoor
de Nederlandse de superseded ADR-005-tekst behield. De `.nl`-varianten zijn geen
forks maar mee-geredigeerde vertalingen, dus vertaling propageert fouten in
plaats van ze te vangen.

Twee lagen:

1. **Feitpariteit tussen taalvarianten.** Voor elk `X.md` met een `X.nl.md`-zus
   moeten de backticked identifiers -- padnamen, scriptnamen, env-vars, tools --
   aan beide kanten hetzelfde zijn. Prozaverschillen zijn prima; een pad dat
   maar in één taal gecorrigeerd wordt niet.

2. **Code-afgeleide feiten.** Claims die uit de broncode te herleiden zijn
   (aantal MCP-primitieven, de embed-timeout) worden tegen de code getoetst, en
   gedocumenteerde omgevingsvariabelen die nergens gelezen worden vallen op.

Scope is SUBTRACTIEF: alle getrackte markdown minus changelog, ADR's, backlog,
atlas en research. Een handonderhouden lijst van "te controleren bestanden"
wordt zelf de volgende verouderde doc.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

# Mappen die geen productclaims dragen of bewust historisch zijn.
EXCLUDED_DIRS = {"backlog", "atlas", "node_modules", ".git", "pip", ".superpowers",
                 # Lokale, gitignorede uitvoer van /comprehensive-review. Die
                 # documenten BESCHRIJVEN bevindingen over env-vars (inclusief
                 # verouderde), en zijn geen gebruikersdocumentatie waarop deze
                 # guard uitspraken hoort te doen.
                 ".full-review"}
EXCLUDED_FILES = {"CHANGELOG.md"}

CODE_SPAN = re.compile(r"`([^`\n]+)`")
# Alleen identifier-achtige spans: paden, scripts, env-vars, tool-namen. Gewone
# prozawoorden tussen backticks (bv. `klein`) zouden anders ruis geven.
IDENTIFIERISH = re.compile(r"^[A-Za-z0-9_./~$-]+$")


def _markdown_files():
    for path in sorted(REPO_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT)
        if rel.parts[0] in EXCLUDED_DIRS or path.name in EXCLUDED_FILES:
            continue
        if "research" in rel.parts or "docs" in rel.parts and "adr" in rel.parts:
            continue
        # Specs en plannen zijn gedateerde besluitrecords, zelfde klasse als
        # research en ADRs: ze beschrijven wat er toen was, niet wat er nu is.
        # ADR-008 verwijderde een feature waarvan de spec de env-vars noemt;
        # het record hoort te blijven zonder dat de spookvar-guard erop afgaat.
        if "superpowers" in rel.parts:
            continue
        yield path


def _identifiers(text: str) -> set[str]:
    return {
        span for span in CODE_SPAN.findall(text)
        if IDENTIFIERISH.match(span) and any(c in span for c in "._/$-")
    }


class BilingualFactParityTest(unittest.TestCase):
    def test_language_variants_agree_on_identifiers(self):
        problems = []
        for path in _markdown_files():
            if path.name.endswith(".nl.md"):
                continue
            sibling = path.with_name(path.name[:-3] + ".nl.md")
            if not sibling.is_file():
                continue
            en = _identifiers(path.read_text(encoding="utf-8"))
            nl = _identifiers(sibling.read_text(encoding="utf-8"))
            only_en, only_nl = sorted(en - nl), sorted(nl - en)
            if only_en or only_nl:
                problems.append(
                    f"{path.name} vs {sibling.name}\n"
                    f"    alleen in {path.name}: {only_en}\n"
                    f"    alleen in {sibling.name}: {only_nl}")
        self.assertEqual(
            problems, [],
            "taalvarianten noemen verschillende identifiers; een correctie is in "
            "maar één taal geland:\n  " + "\n  ".join(problems))


class CodeDerivedFactTest(unittest.TestCase):
    def test_mcp_primitive_count_matches_the_server(self):
        source = (SCRIPTS / "kb-mcp.py").read_text(encoding="utf-8")
        tools = {name for name in
                 ("recall", "capture", "what_did_i_do", "timeline", "weeklog", "topic_timeline")
                 if f"def {name}_tool(" in source}
        self.assertEqual(len(tools), 6, f"tool-set veranderd: {sorted(tools)}")
        for readme, word in (("README.md", "three primitives"),
                             ("README.nl.md", "drie primitieven")):
            text = (REPO_ROOT / readme).read_text(encoding="utf-8")
            self.assertNotIn(
                word, text,
                f"{readme} noemt drie MCP-primitieven; het zijn er "
                f"{len(tools)} tools plus een resource")

    def test_no_document_claims_a_sub_second_hot_path_embed(self):
        """De concrete claim is verboden, het woord niet.

        'sub-second' staat legitiem in CLAUDE.md, PRINCIPLES.md en VALUES.md als
        noordster. Wat niet mag is de bewering dat de hot-path-embed sub-seconde
        begrensd is: het plafond staat in code op 2,0 s.
        """
        timeout = re.search(r"^EMBED_TIMEOUT\s*=\s*([0-9.]+)",
                            (SCRIPTS / "kb-retrieve.py").read_text(encoding="utf-8"), re.M)
        if timeout:
            self.assertGreaterEqual(
                float(timeout.group(1)), 1.0,
                "embed-timeout is onder 1s gezakt; de sub-seconde-claims in de "
                "documentatie mogen dan terug")
        claim = re.compile(r"(hot-path[- ]embed[^.\n]{0,60}sub-second"
                           r"|sub-second[^.\n]{0,40}hot-path[- ]embed"
                           r"|hot-path-embed[^.\n]{0,60}sub-seconde)", re.I)
        offenders = [str(p.relative_to(REPO_ROOT)) for p in _markdown_files()
                     if claim.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [],
                         f"documenten beloven een sub-seconde hot-path-embed: {offenders}")

    def test_documented_tool_output_uses_real_markers(self):
        """Geciteerde tool-uitvoer moet uit de tool komen, niet verzonnen zijn.

        POST-INSTALL.md drukte een doctor-transcript af met `[ok]`-regels en een
        footer `Done. 0 errors, 2 warnings.` -- doctor.sh emit die niet en heeft
        ze nooit geëmit. Een lezer die zijn eigen uitvoer ernaast legt kan niet
        zien of iets misgaat.
        """
        doctor = (SCRIPTS / "doctor.sh").read_text(encoding="utf-8")
        real_tiers = {t for t in ("[PASS]", "[WARN]", "[FAIL]", "[INFO]")
                      if t in doctor}
        self.assertEqual(len(real_tiers), 4, "doctor.sh emit niet meer vier tiers")

        # Scope: a lowercase tier marker only lies when it is presented AS
        # doctor output, i.e. inside a fenced block that shows a doctor run.
        # The old check fired on any document mentioning doctor.sh anywhere
        # that also contained "[warn]" anywhere -- which flagged truthful
        # documentation of build-karpathy-index.py, a script that really does
        # print [warn]/[error] to stderr. The fabricated footer is different:
        # "Done. 0 errors" is doctor-shaped wherever it appears.
        offenders = []
        for path in _markdown_files():
            text = path.read_text(encoding="utf-8")
            if "Done. 0 errors" in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: 'Done. 0 errors'")
            for block in re.findall(r"```.*?```", text, re.S):
                if "doctor.sh" not in block:
                    continue
                for invented in ("[ok]", "[warn]", "[error]"):
                    if invented in block:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {invented!r}")
        self.assertEqual(
            offenders, [],
            "documentatie citeert doctor-uitvoer die het script niet emit; "
            "gebruik echt gevangen output:\n  " + "\n  ".join(offenders))

    def test_documented_env_vars_are_read_somewhere(self):
        """Een gedocumenteerde env-var die geen enkele regel code leest is een leugen.

        Uitzondering: variabelen die een extern hulpprogramma leest (de `ollama`
        CLI) mogen in shell-voorbeelden staan; die worden hier expliciet
        benoemd zodat de uitzondering zichtbaar blijft in plaats van impliciet.
        """
        # Gelezen door een EXTERN programma, niet door onze code. Ze horen in de
        # documentatie thuis; ze horen alleen niet als "onze knop" te lezen.
        external = {
            "OLLAMA_HOST",                  # de ollama CLI
            "COPILOT_GITHUB_TOKEN",         # de GitHub Copilot CLI
            "COPILOT_PROVIDER_TYPE",
            "COPILOT_PROVIDER_BASE_URL",
            "COPILOT_PROVIDER_API_KEY",
            "COPILOT_PROVIDER_WIRE_API",
            "COPILOT_CUSTOM_INSTRUCTIONS_DIRS",   # standalone Copilot CLI, ADR-0003
            "COPILOT_OFFLINE",                    # idem: disables its network access
        }
        # "Code" is hier breder dan Python: de skills en slash-commands zijn
        # uitvoerbare instructies en lezen env-vars in hun shell-blokken.
        sources = list(SCRIPTS.glob("*.py")) + list(SCRIPTS.glob("*.sh"))
        sources += sorted((REPO_ROOT / "skills").rglob("*.md"))
        sources += sorted((REPO_ROOT / "commands").rglob("*.md"))
        # Tests are code too. Opt-in tier knobs (KB_INTEGRATION,
        # KB_COPILOT_LIVE) are read only by the suite, so leaving tests/ out
        # made the guard call a documented, working knob a ghost.
        sources += sorted((REPO_ROOT / "tests").glob("*.py"))
        code = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
        code += (REPO_ROOT / "setup.sh").read_text(encoding="utf-8")
        documented = set()
        for path in _markdown_files():
            for span in CODE_SPAN.findall(path.read_text(encoding="utf-8")):
                if re.fullmatch(r"(KB|KENNISBANK|OLLAMA|COPILOT|CODEX|OPENCODE)_[A-Z0-9_]+", span):
                    documented.add(span)
        ghosts = sorted(v for v in documented - external if v not in code)
        self.assertEqual(
            ghosts, [],
            f"gedocumenteerde omgevingsvariabelen die nergens gelezen worden: {ghosts}")


if __name__ == "__main__":
    unittest.main()
