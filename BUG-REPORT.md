# Hang when accepting all tracked changes through LibreOfficeKit with a hidden deletion in a table cell

- **Product:** LibreOffice
- **Component:** Writer
- **Version:** 26.8.3.1
- **Platform:** Linux / ARM64
- **Reproducibility:** Always in the tested configuration (3/3 runs)

## Description

Using LibreOffice 26.8.3.1 through LibreOfficeKit, a small DOCX containing a tracked deletion inside a table cell loads successfully. If tracked changes are hidden, invoking a Basic macro through LibreOfficeKit's `runMacro` to execute `.uno:AcceptAllTrackedChanges` then hangs. The subsequent PDF export is not reached within the 12-second test limit.

The attached synthetic DOCX is only 1,448 bytes. It contains one table with one cell, whose only text is marked as deleted, followed by a normal paragraph outside the table. `word/settings.xml` contains:

```xml
<w:revisionView w:insDel="0"/>
```

Changing only this attribute to `1` makes the same operation succeed. Simply loading and exporting the original fixture, without accepting changes, also succeeds.

The reproducer uses an independent C program and a small LibreOffice Basic macro. It does not use Gotenberg or its `lok` executable. Each run uses a fresh profile and a private input copy to exclude interference from document lock files.

## Steps to reproduce

From the reproduction repository, with Docker installed:

```sh
docker build --platform linux/arm64 -t libreoffice-redline-repro:26.8.3 .
docker run --rm --platform linux/arm64 --cpus 4 --memory 4g \
  -v "$PWD/fixtures:/fixtures:ro" \
  libreoffice-redline-repro:26.8.3 /fixtures/hidden-deletion.docx /tmp/out.pdf
```

The C program loads the document through LibreOfficeKit, then invokes a Basic macro containing:

```basic
docs = StarDesktop.Components.createEnumeration()
doc = docs.nextElement()
dispatcher = createUnoService("com.sun.star.frame.DispatchHelper")
dispatcher.executeDispatch(doc.getCurrentController().getFrame(), ".uno:AcceptAllTrackedChanges", "", 0, Array())
```

## Actual result

Each of three runs reaches:

```text
[LOK-REPRO] … init.ok
[LOK-REPRO] … load.ok
[LOK-REPRO] … accept-changes.begin
```

The operation does not return before the built-in 12-second timeout terminates the process with exit code 124. Neither `accept-changes.ok` nor `save.ok` is reached.

## Expected result

Accepting the tracked deletion completes promptly, leaving an empty table cell, and PDF export succeeds.

## Successful controls

- Replace `hidden-deletion.docx` with `visible-deletion.docx`: only `insDel="0"` changes to `insDel="1"`. Accepting all changes and PDF export succeed, exit code 0. Both fixtures have the same size.
- Load `hidden-deletion.docx` and export it without executing `.uno:AcceptAllTrackedChanges`: succeeds, exit code 0.

Run both controls and three repetitions of the failing case with:

```sh
python3 check.py
```

## External UNO and macro controls

The same operation was also tested through a standalone `soffice` listener and a separate Python/pyuno client, both from the identical official LibreOffice 26.8.3.1 installation. No LibreOfficeKit client was started in these controls.

- Direct external UNO dispatch of `.uno:AcceptAllTrackedChanges` succeeds repeatedly with the original hidden fixture.
- Invoking the **unchanged Basic macro** through the external UNO application script provider also succeeds repeatedly with that fixture.
- Every acceptance case reduces the redline count from one to zero and produces a PDF parsed successfully by `pdfinfo` and `pdftotext`.
- The matrix covers unchanged source display settings, a separate `ShowChanges=False` request, both fixtures, and both `Hidden=True` and `Hidden=False` frame settings. All 20 acceptance cases and four export-only controls succeed.

The export-only controls establish genuine hidden rendering: the original `insDel="0"` fixture omits `Old` before acceptance, while the `insDel="1"` control includes it. The document's `ShowChanges` getter returns `True` for both fixtures and must not be interpreted as proof that deletions are rendered visibly. See [the external UNO harness and complete results](uno/README.md).

These results show that the macro's Basic code alone is insufficient to trigger the failure. The failing tested context remains LibreOfficeKit's `runMacro` invocation. An alternative, non-macro accept-all invocation inside LibreOfficeKit and interaction through the Writer graphical interface have not been tested; this is not a claim that every other entry point is unaffected.

Earlier ordinary command-line and UNO-based PDF conversions did not execute the accept-all command. The external UNO controls above do execute that same command and therefore provide the relevant comparison.

## Redline-notification diagnostic control

With the same LibreOfficeKit reproducer, original hidden fixture, and unchanged Basic macro, setting only `DISABLE_REDLINE=1` makes acceptance and PDF export succeed in **3/3 runs**. The default environment still times out at `accept-changes.begin`.

```sh
docker run --rm --platform linux/arm64 --cpus 4 --memory 4g \
  -e DISABLE_REDLINE=1 -v "$PWD/fixtures:/fixtures:ro" \
  libreoffice-redline-repro:26.8.3 /fixtures/hidden-deletion.docx /tmp/out.pdf
```

In the [26.8.3.1 source](https://github.com/LibreOffice/core/blob/libreoffice-26.8.3.1/sw/source/core/doc/docredln.cxx#L337), this environment variable bypasses LOK-specific redline notifications. That notification function [calls `aCursor.FillRects()`](https://github.com/LibreOffice/core/blob/libreoffice-26.8.3.1/sw/source/core/doc/docredln.cxx#L375), consistent with the captured layout stack. This narrows the failure to the LOK redline-notification/layout path; it does not identify the exact faulty layout condition or constitute a patch.

## Environment

- Official TDF LibreOffice release **26.8.3**, internal version **26.8.3.1**.
- Build ID: `861effc5289d539f15c4c18d1ba8579ffd78728b`.
- Debian trixie-slim container, `linux/arm64`, running on Docker Desktop / Apple Silicon.
- Official Linux ARM64 DEB packages, verified against the published SHA-256 checksum.
- Container limits: 4 CPUs and 4 GiB RAM.
- Also reproduced with Debian LibreOffice **26.8.2.2**. Other versions and amd64 have not been tested.

## Additional diagnostic information

A stack trace captured with the same reproduction on **26.8.2.2** points to Writer layout recalculation during the acceptance of changes:

```text
sw::DocumentRedlineManager::AcceptAllRedline
sw::DocumentRedlineManager::AcceptRedline
SwRedlineTable::Remove
SwRedlineTable::LOKRedlineNotification
SwRootFrame::CalcFrameRects
SwTextFrame::Format / FormatImpl / Format_ / FormatLine
```

This stack trace has not been separately captured on 26.8.3.1. On that version, stage logging independently confirms successful loading followed by the hang inside the accept-changes operation.

Possibly related: [bug 166485](https://bugs.documentfoundation.org/show_bug.cgi?id=166485), which reports increased memory usage when accepting or rejecting changes and attributes it to undo recording. It has not been established that this is the same issue.

## Reproduction files

- `fixtures/hidden-deletion.docx`: synthetic failing fixture.
- `fixtures/visible-deletion.docx`: control differing only in the change-display setting.
- `reproduce.c`, `Repro.xba`, `run-reproducer.sh`, `Dockerfile`, and `include/`: independent runnable reproduction.
- `check.py`: automated controls and repeated failure checks; writes logs to `results/verified.json`.

All fixture content is synthetic and may be shared publicly.
