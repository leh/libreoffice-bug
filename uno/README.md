# Standalone external UNO comparison

This experiment uses the official TDF LibreOffice **26.8.3.1** build
`861effc5289d539f15c4c18d1ba8579ffd78728b` in the existing
`libreoffice-redline-repro:26.8.3` image on `linux/arm64`.
No LibreOfficeKit client or Gotenberg process is started.

## Run

Prerequisites on the host: Docker, Python 3, and Poppler's `pdfinfo` and `pdftotext`.
The base image is built with the repository's existing Dockerfile:

```sh
docker build --platform linux/arm64 -t libreoffice-redline-repro:26.8.3 .
python3 uno/check.py --output results/uno-confirmation
```

Run from the repository root. Choose a new output directory for each matrix;
nonempty case directories are rejected. `--resume` continues a partially completed
matrix using its existing `verified.json`.

To run only one direct hidden-fixture case:

```sh
mkdir -p results/uno-single
docker run --rm --platform linux/arm64 --name diag-uno-single \
  --cpus 4 --memory 4g \
  -v "$PWD/uno:/harness:ro" \
  -v "$PWD:/source:ro" \
  -v "$PWD/results/uno-single:/output" \
  --entrypoint timeout libreoffice-redline-repro:26.8.3 \
  30s /bin/sh /harness/run-case.sh \
  /source/fixtures/hidden-deletion.docx true accept preserve
pdfinfo results/uno-single/output.pdf
pdftotext results/uno-single/output.pdf -
```

`run-case.sh` takes `fixture`, `Hidden`, `mode`, and `ShowChanges request`.
Modes are `accept` (direct dispatch), `macro` (the same Basic module), and
`export-only`. The final argument is `preserve` or `false`.

## Exact separation and operation

Each case uses a new container, a fresh profile, and a private copy of the input.
The profile is initialized, then the exact repository `Repro.xba` is installed in
its Standard library. The installed module's SHA-256 matches the source:
`602c44d4134b2b12defbd5de082675cf9a839f94ca432dd2fb857fd323f517bb`.
The macro is present in direct and export-only cases too, keeping profile setup
constant. No fixture settings are rewritten and no `ShowChanges=True` call is made.

`run-case.sh` starts this standalone listener:

```sh
soffice --headless --nologo --nodefault --norestore --nofirststartwizard \
  "-env:UserInstallation=file://$profile" \
  '--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ServiceManager'
```

A different process runs `/opt/libreoffice26.8/program/python` and connects over
that UNO socket. This wrapper uses `python.bin` 3.13.18 and `uno.py`/`pyuno.so`
from `/opt/libreoffice26.8/program`, matching the listener installation. The
listener's CLI version, build ID, remote configuration version, process IDs,
executable paths, and command lines are recorded.

The direct route calls exactly:

```python
dispatcher.executeDispatch(document.getCurrentController().getFrame(),
                           ".uno:AcceptAllTrackedChanges", "", 0, ())
```

The macro route uses the remote application script provider to invoke
`vnd.sun.star.script:Standard.Repro.AcceptChanges?language=Basic&location=application`.
The unchanged Basic source performs the same dispatch. Its invocation entry point
is external UNO, whereas the LOK reproducer enters through `runMacro`.

The client checks that the redline count changes from one to zero, exports with
`writer_pdf_Export`, verifies the PDF header and size, closes the document, and
terminates the listener. The host additionally parses every PDF with both
`pdfinfo` and `pdftotext`. Success is never inferred solely from an exit code.

## Verified results

The committed `uno/verification-summary.json` records an independent repeat of
the full matrix and the separate LOK notification control. Full generated evidence
is in `results/uno/verified.json`, with per-case JSONL phases,
listener logs, exact Docker arguments, input copies, macro hashes, PDFs, PDF
metadata, and extracted text. All **24 cases returned 0 and produced valid,
one-page PDFs**. None reached the 20-second client timeout.

| Conditions | Direct dispatch | Same Basic macro |
| --- | --- | --- |
| `Hidden=True`, original hidden fixture, unchanged display | 3/3 PDF | 3/3 PDF |
| `Hidden=True`, visible fixture, unchanged display | 1/1 PDF | 1/1 PDF |
| `Hidden=True`, original hidden fixture, `ShowChanges=False` requested | 3/3 PDF | 3/3 PDF |
| `Hidden=True`, visible fixture, `ShowChanges=False` requested | 1/1 PDF | 1/1 PDF |
| `Hidden=False`, original hidden fixture, unchanged display | 1/1 PDF | 1/1 PDF |
| `Hidden=False`, original hidden fixture, `ShowChanges=False` requested | 1/1 PDF | 1/1 PDF |

The remaining four cases export without accepting changes, for both fixtures and
both display requests. These establish the rendered state before acceptance.

For the 16 acceptance cases with `Hidden=True`, direct dispatch took
**0.000927–0.002965 seconds** and the macro route took
**0.013934–0.027162 seconds** including script-provider setup. All accepted PDFs
contain `Sample text.` and omit `Old`. The complete per-case Docker durations
were **0.934–4.555 seconds**, including startup and cleanup.

`Hidden=True` produced a frame container whose `isVisible()` was false.
`Hidden=False` produced one whose `isVisible()` was true; all four acceptance
controls still succeeded. `Hidden` describes frame visibility, not the tracked
change display setting.

The loaded document has a `SwXTextView` controller, a
`com.sun.star.comp.framework.Frame`, and `SwXViewSettings`. Controller view-setting
introspection found `ShowChangesInMargin=False`; it found no separate
`ShowChanges` or `RedlineDisplayType` view setting. No LOK rendering initialization
or explicit pre-accept rendering call is performed. The separate export-only
controls verify that the original document view can actually render.

## Display-state caveat and correction

For **both source fixtures**, the document getters return `ShowChanges=True` and
`RedlineDisplayType=2`, even though their rendered deletion visibility differs.
The initial observation of `ShowChanges=True` therefore **did not demonstrate
visible tracked changes**.

Pre-accept PDF text verifies the actual layout:

| Source | Request | PDF text |
| --- | --- | --- |
| `revisionView insDel=0` | preserve | `Sample text.`; no `Old` |
| `revisionView insDel=1` | preserve | `Old`, then `Sample text.` |
| `revisionView insDel=0` | `ShowChanges=False` | `Sample text.`; no `Old` |
| `revisionView insDel=1` | `ShowChanges=False` | `Old`, then `Sample text.` |

`document.setPropertyValue("ShowChanges", False)` returned without exception;
its before/after getters still showed `True` and `2`. The exact release source
explains why these getters cannot establish hidden layout: the
[setter calls `SetHideRedlines(true)` while retaining the show flags](https://github.com/LibreOffice/core/blob/libreoffice-26.8.3.1/sw/source/uibase/uno/unotxdoc.cxx#L2016),
and the [getter tests the flags](https://github.com/LibreOffice/core/blob/libreoffice-26.8.3.1/sw/source/uibase/uno/unotxdoc.cxx#L2238).
In this harness the assignment also did not turn the visible-source PDF into a
hidden rendering. Do not use this assignment alone as proof of a visible-to-hidden
transition. The original `insDel=0` fixture, independently verified by its
export-only PDF, supplies the genuinely hidden-layout comparison.

## Supported conclusion

The external standalone UNO path successfully accepts this original hidden-view
fixture through both direct dispatch and the exact same Basic macro, repeatedly,
and produces parsed PDFs. The macro's Basic code alone is therefore insufficient
to reproduce the LOK hang in this tested context. This experiment does not test an alternative accept-all invocation inside LOK
without a Basic macro and does not prove that every UNO configuration is unaffected.
