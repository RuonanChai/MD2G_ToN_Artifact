# Anonymity audit

Record of checks performed on this artifact. Redacted identity strings are not listed.

| Check | Status | Notes |
|-------|--------|-------|
| Fresh Git history (no inherited `.git`) | PASS | New `git init` only; no nested `.git` |
| Not a fork of any named public author repo | PASS | New repository, empty history |
| Author display-name / email / affiliation scan | PASS | Word-boundary scan of text files |
| Local filesystem path scan | PASS | Portable `ARTIFACT_ROOT` / `SIGCOMM_MOQ_BIN_DIR` |
| Secret pattern scan | PASS | `token=` hits are scientific pause-event kwargs, not credentials |
| Large-file scan | PASS | Largest file ~8.1 MB; none ≥ 100 MB |
| PDF author metadata | PASS | Matplotlib-generated figure PDFs; no author/affiliation fields |
| README / docs author identity | PASS | Neutral wording only |
| Compile of exported Python | PASS | `py_compile` on all `.py` files |

Findings corrected in the export (not in the live working tree):

- Host-absolute paths rewritten to `artifact_root()` / `ton_root()` / environment variables
- Hard-coded MoQ binary fallbacks removed; `SIGCOMM_MOQ_BIN_DIR` is required unless a local release tree exists
- Foreign-workspace deny-list strings generalized
- Compile caches (`__pycache__/`) deleted before the first commit

Do not treat this document as a list of the original host names.
