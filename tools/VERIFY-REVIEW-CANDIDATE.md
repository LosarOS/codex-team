# Independently check retained Windows review artifacts

`verify_review_candidate.py` uses Python's standard library. It reads the two outer review ZIP artifacts and retained proof files. It never executes binaries or extracts archive paths onto disk. Inner archives are read through temporary files; no user profile or project data is changed. Only the explicitly requested new output JSON is written, using exclusive creation; existing output is refused.

```sh
python tools/verify_review_candidate.py \
  --portable-review /path/to/portable-review-artifact.zip \
  --installers-review /path/to/installers-review-artifact.zip \
  --evidence /path/to/candidate-evidence \
  --source 6e00643676dd9b2e701fdccf50fa8b75ff59fd00 \
  --build-run 43653777510 \
  --version 1.0.0-rc12 \
  --output /path/to/new-verification.json
```

Evidence layout: `candidate-review.json` at root; `candidate/` containing SHA256SUMS.txt, release-checksums.json, source-test-results.json, build-verification.json, portable-smoke.json and installed-smoke.json.

Checks: all three binary sizes/hashes agree across independently computed bytes/checksum sources, ZIP CRC and bounded safe names/no case collisions/symlinks/encryption, no named portable user-data/database paths, AMD64 PE32+ application, no PE certificate table in application/installer, installer ZIP's EXE matches standalone bytes, expected source/build/version, Windows test totals and retained native backend/no-model/preservation gates. Inno Setup's x86 installer stub is normal and is not rejected as a non-x64 application.

The report is **artifact-byte and retained-proof verification**, not a fresh Windows runtime run, cryptographic build attestation, Authenticode trust validation, antivirus/SmartScreen check or GUI acceptance. Expected source and run must be selected from trusted review context. The tool enforces one skipped source test for this RC's opt-in Docker policy; the skipped reason itself remains in original source-run evidence. It does not add repeated suite counts together.

GUI/WebView2 save flows, physical Windows/DPI, live SDK account calls and final publication require separate evidence and owner approval. No source ZIP is accepted in place of the expected distribution names.
