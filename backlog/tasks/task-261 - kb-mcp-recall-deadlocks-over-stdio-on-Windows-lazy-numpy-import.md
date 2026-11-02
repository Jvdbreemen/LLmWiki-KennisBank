---
id: TASK-261
title: 'kb-mcp: recall deadlocks over stdio on Windows (lazy numpy import)'
status: In Progress
assignee: []
created_date: '2026-11-02T18:46:00Z'
labels:
  - bug
  - mcp
  - windows
dependencies: []
ordinal: 195600
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On Windows the MCP stdio server keeps a synchronous ReadFile pending on stdin in a worker thread. recall lazily imports sqlite_vec (kb-recall._open_ro_checked), whose __init__ imports numpy; loading numpy's native DLL during that pending read blocks until the client sends another message, which it never does before the response. Observed: recall in-process 3.8 s, over stdio >120 s (Hermes) and >45 s (bare mcp SDK client); faulthandler stack shows the server thread stuck in numpy._core.multiarray create_module. Root cause: TASK-120 moved _kbindex.connect() to vec0_extension() (find_spec, no package execution) but kb-recall's read-only opens (_open_ro, _open_ro_checked) still did `import sqlite_vec` + `sqlite_vec.load()`. Fix: use _kbindex.vec0_extension() there too. This removes numpy from every recall/hook read path, so the deadlock cannot occur and the ~320 ms numpy import per prompt is gone as TASK-120 intended.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Regression test drives recall over real stdio (fake embed endpoint, placeholder index) and fails on Windows without the fix
- [x] #2 kb-recall read-only opens load vec0 via _kbindex.vec0_extension(); missing sqlite-vec still maps to sqlite_vec_missing
- [x] #3 Portable test (runs in CI) proves the read path imports neither sqlite_vec nor numpy
- [x] #4 Full test suite stays green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Red before the fix (Windows 11, Python 3.14, mcp 1.28.1): read-path test failed on sqlite_vec in sys.modules; stdio test hit the 30 s watchdog on the recall call. Green after: 3/3 in the new file (stdio recall 14.9 s incl. cold server start). Real vault over stdio with the fixed kb-mcp.py: recall 1.2 s. Full suite on Windows: 22 failed / 2101 passed; the same 22 fail on a clean origin/main checkout in the same environment (symlink privilege WinError 1314 in test_hermes_install, plus test_vaultpath, test_opruimen_skill, test_proc_bounded), so none are caused by this change. Not re-measured: the TASK-120 per-prompt saving (~320 ms).
<!-- SECTION:NOTES:END -->
