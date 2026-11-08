# Archived raw artifacts

Large raw bundles that no script or test reads are kept outside the working tree so a clone stays small. They are published, unchanged, as a release asset and can be verified byte-for-byte against the checksums below.

Download and restore into place:

```bash
gh release download v1.0.0 --repo Jill-Vekariya/safeheal-ai --pattern 'safeheal-evidence-archive-v1.0.0.tar.gz'
tar -xzf safeheal-evidence-archive-v1.0.0.tar.gz   # recreates the paths listed below
sha256sum --check evidence/ARCHIVE-SHA256SUMS
```

The asset is produced by [`.github/workflows/release-archive.yml`](../.github/workflows/release-archive.yml), which restores the files from the last commit that held them, checks every one against `ARCHIVE-SHA256SUMS`, and only then attaches the archive to the release.

Everything that `scripts/reproduce.py`, the CI replay steps and the per-run `artifact-manifest.json` files depend on remains in the repository. The per-run manifests inside `evidence/final/ci-*/` and `evidence/demo/ci-*/` still record the hashes of the archived `artifacts.zip` files, so the archive can be checked against them as well.

| Archived file | Size | Why it was archived |
|---|---|---|
| `evidence/final/ci-40135721425/artifacts.zip` | 4.2 MB | Raw CI artifact bundle; `summary.json`, `run.json`, failed-step log and manifest stay in the tree. `ci-40142094894/artifacts.zip` is kept because `tests/test_demo_report.py` reads it |
| `evidence/final/ci-40140051368/artifacts.zip` | 4.2 MB | Same |
| `evidence/final/ci-40145364797/artifacts.zip` | 4.2 MB | Same |
| `evidence/demo/ci-40145365194/artifacts.zip` | 0.6 MB | Raw demo bundle; `summary.md`, `result.json`, `verification.json` stay in the tree |
| `evidence/demo/ci-40145170673/artifacts.zip` | 0.6 MB | Same |
| `evidence/day4/day4-pause-670cd6f0b91f.json` | 3.7 MB | Raw day-4 acceptance capture; findings are summarised in `docs/INCIDENT_DETECTION.md` |
| `evidence/day4/day4-live-463536f6246c.json` | 1.8 MB | Same |
| `evidence/day4/day4-live-b54f1ad56622.json` | 1.3 MB | Same |
