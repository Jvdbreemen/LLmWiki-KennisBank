---
id: TASK-26.7
title: KennisBank Copilot wrapper/launcher naar Headroom-patroon bouwen
status: Done
assignee: []
created_date: '2026-07-08 18:07'
updated_date: '2026-07-11 20:44'
labels:
  - copilot
  - wrapper
  - headroom
  - cli
dependencies:
  - TASK-26.3
  - TASK-26.5
  - TASK-26.6
modified_files:
  - scripts/kennisbank-copilot.py
  - tests/test_copilot_wrapper.py
  - scripts/kb-copilot-capture.py
  - tests/test_copilot_capture.py
parent_task_id: TASK-26
priority: high
ordinal: 28070
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw een wrapper/launcher, bijvoorbeeld kennisbank-copilot, die dezelfde rol vervult als het Headroom-wrapperpatroon maar local-first en KennisBank-specifiek blijft: detecteer vault/repo/runtime/MCP/Copilot, zet KENNISBANK_VAULT en instructie-env, valideer light-mode, start daarna echte copilot CLI met oorspronkelijke args, en bied --doctor, --dry-run, --print-env en --no-capture.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Er is een wrapper-script voor Windows en POSIX of een cross-platform Python entrypoint met shell shims.
- [x] #2 Wrapper passt args transparant door naar copilot en behoudt exit code.
- [x] #3 Wrapper valideert minimale KennisBank prerequisites snel en fail-open waar dat veilig is.
- [x] #4 Wrapper kan zonder Copilot-login in dry-run/doctor mode gebruikt worden.
- [x] #5 Tests dekken env setup, arg passthrough, exit-code passthrough, missing binary, vault override en no-capture mode.
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
scripts/kennisbank-copilot.py: triviale-exec launcher (ADR D4), GEEN proxy/rerouting/signal-machinerie (contrast met Headroom). Cross-platform Python entrypoint (subprocess.run + returncode-passthrough, uniform + testbaar). Vault gepind (KENNISBANK_VAULT altijd overschreven, posix-genormaliseerd); KB_LLM_* set-if-absent (do-not-clobber). Modi (login-vrij): --kb-doctor (JSON probe+config, exit 0 iff status in ok/version_old/not_logged_in), --kb-dry-run (JSON, geen launch), --kb-print-env (KEY=VALUE, secret-masked), --no-capture (zet KENNISBANK_COPILOT_NO_CAPTURE=1, geconsumeerd). Overige args verbatim doorgegeven, exit-code behouden. Missende binary = fataal alleen bij echte launch (rc 127 + nvm4w-install-hint), niet in doctor/dry-run. launch() = monkeypatchbare seam. Secret-masking defensief (DoD#3). 

kb-copilot-capture.py honoreert nu KENNISBANK_COPILOT_NO_CAPTURE (--no-capture werkt end-to-end). setup.sh deployt de wrapper via scripts/*.py-glob naar vault/.claude/scripts (DoD#1 installed; documentatie → 26.11). Geverifieerd tegen echte copilot v1.0.70: alle 4 modi + echte launch + exit-code. 15 wrapper-tests + no-capture-test groen.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 setup installeert of documenteert de wrapper als optionele launch route.
- [x] #2 Wrapper output is menselijk leesbaar en heeft JSON-mode voor doctor.
- [x] #3 Geen secrets of tokens verschijnen in logs of test snapshots.
<!-- DOD:END -->
