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

## Scope and untested entry points

The failure is demonstrated when accepting changes through **LibreOfficeKit**, using `runMacro` to invoke the command. Loading and PDF export alone through LibreOfficeKit succeed.

The Basic macro uses UNO objects internally. However, executing the same accept-all command through an **external UNO client** or the **Writer graphical interface** has not been tested. This report therefore does not establish that the failure is exclusive to LibreOfficeKit.

Earlier tests with LibreOffice 26.8.2.2 succeeded when converting the document to PDF using `soffice --headless --convert-to pdf` or Gotenberg 8's UNO-based conversion. Those tests did not execute the accept-all command, so they are not equivalent controls for the failing operation.

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
