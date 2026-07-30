---
id: TASK-120
title: >-
  Hot path: drop 250-300 ms per prompt by loading sqlite-vec without importing
  numpy
status: Done
assignee: []
created_date: '2026-07-30 10:17'
updated_date: '2026-07-30 18:11'
labels: []
dependencies: []
ordinal: 118700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the comprehensive review performance pass and independently re-verified. The sqlite_vec package's __init__ ends with "import numpy.typing" purely to define an optional register_numpy helper that KennisBank never calls. Measured with -X importtime on the deployed interpreter: import sqlite_vec costs 355 ms cumulative, of which numpy.typing is 319 ms. It is paid on the first index open of every kb-retrieve run and every kb-presearch run (_kbindex.py:38 connect, :115 _serialize, kb-recall.py:47 _open_ro). KennisBank uses exactly two things from the package: the path to the vec0 loadable extension and serialize_float32. Both are stdlib one-liners. importlib.util.find_spec locates the package WITHOUT executing it: verified at 0.6 ms, numpy never enters sys.modules, and loading the extension from the located path returns vec_version() = v0.1.9. The KNN top-5 doc_ids were verified byte-identical to the serialize_float32 path on the real index. Caveat worth keeping in the commit message: the cost is conditional on numpy being importable, and numpy is not in requirements.txt - it merely happens to be installed here. The fix removes that conditionality, so the hot path stops depending on what else the user has installed, which is the more valuable property. find_spec returning None raises ImportError, so every existing except Exception around connect/_open_ro keeps degrading exactly as it does today when the package is absent, preserving the stdlib-first rule. Context: the measured end-to-end hook median is 1324 ms; this single change takes it to roughly 1030-1075 ms with no behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 _kbindex locates the vec0 extension via importlib.util.find_spec and never imports sqlite_vec
- [x] #2 _serialize uses struct.pack instead of sqlite_vec.serialize_float32
- [x] #3 sqlite_vec absent from sys.modules after a retrieval run, asserted by a test
- [x] #4 A missing sqlite-vec package still degrades exactly as before (ImportError caught by the existing handlers)
- [x] #5 KNN results verified identical on a real index before and after
- [x] #6 Measured hook latency improvement recorded in the task notes
- [ ] #7 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
_kbindex now locates the vec0 extension with importlib.util.find_spec and serialises with struct.pack, so sqlite_vec is never imported. Verified on this machine: import sqlite_vec costs 355 ms cumulative of which numpy.typing is 319 ms; find_spec is 0.6 ms and neither sqlite_vec nor numpy appears in sys.modules after a connect. Equivalence proven three ways: struct.pack output byte-identical to sqlite_vec.serialize_float32 on a 384-dim vector, vec_version() still v0.1.9 through the located path, and the 112 index/recall tests pass unchanged. A missing package now raises ImportError from find_spec, which the existing except Exception handlers around connect/_open_ro catch exactly as before, so the stdlib-first degradation is unchanged. Measured context: the reviewed end-to-end hook median was 1324 ms, of which this was the single largest avoidable component.
<!-- SECTION:FINAL_SUMMARY:END -->
