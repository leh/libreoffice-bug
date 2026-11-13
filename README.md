# Minimal reproduction: accepting hidden deletions through LibreOfficeKit hangs (LibreOffice 26.8.3)

As of November 13, 2026. Confirmed with the official TDF build **26.8.3.1**, build ID `861effc5289d539f15c4c18d1ba8579ffd78728b`, on **linux/arm64**. amd64 has not been tested.

The 1,448-byte DOCX contains a table with one cell whose only text is marked as deleted. A normal paragraph appears outside the table. Tracked changes are hidden using `w:revisionView w:insDel="0"`.

**Loading and direct PDF export through LibreOfficeKit succeed. Invoking “Accept All Tracked Changes” through a Basic macro called by LibreOfficeKit's `runMacro` hangs in Writer's layout code.** This reproduction uses neither Gotenberg nor its Go program `lok`.

Executing the same accept-all operation through an external UNO client or the Writer graphical interface has not been tested. The macro uses UNO objects internally, but that does not make this an external UNO-client test. The current evidence does not establish that only LibreOfficeKit is affected.

## Build once

From this reproduction directory:

```sh
docker build --platform linux/arm64 -t libreoffice-redline-repro:26.8.3 .
```

The build starts from Debian trixie-slim and downloads LibreOffice directly from the official TDF server. The package checksum is pinned in the Dockerfile. The image contains a small C reproducer and a custom Basic macro.

Check the version:

```sh
docker run --rm --platform linux/arm64 --entrypoint soffice libreoffice-redline-repro:26.8.3 --version
```

Expected: `LibreOffice 26.8.3.1 861effc5289d539f15c4c18d1ba8579ffd78728b`.

## Reproduce the failure

```sh
docker run --rm --platform linux/arm64 --cpus 4 --memory 4g \
  -v "$PWD/fixtures:/fixtures:ro" \
  libreoffice-redline-repro:26.8.3 /fixtures/hidden-deletion.docx /tmp/out.pdf
```

The output reaches:

```text
[LOK-REPRO] … init.ok
[LOK-REPRO] … load.ok
[LOK-REPRO] … accept-changes.begin
```

The process then runs until the built-in 12-second timeout, exiting with code **124**. PDF export is never reached. The timeout bounds the test; it does not establish that the call would never return.

## Positive control

Only `revisionView/@insDel` changes from `0` to `1`. Both DOCX files are exactly 1,448 bytes.

```sh
docker run --rm --platform linux/arm64 --cpus 4 --memory 4g \
  -v "$PWD/fixtures:/fixtures:ro" \
  libreoffice-redline-repro:26.8.3 /fixtures/visible-deletion.docx /tmp/out.pdf
```

Expected: `accept-changes.ok`, `save.ok`, a generated PDF, and exit code **0**.

Run the automated check, including three repetitions of the failure:

```sh
python3 check.py
```

## Execution steps

1. Create a fresh LibreOffice profile and install the custom Basic macro.
2. Create a private input copy so existing document lock files cannot affect the test.
3. Initialize LibreOfficeKit and load the DOCX in the C program.
4. Use `runMacro` to execute only `.uno:AcceptAllTrackedChanges`.
5. If that call returns, save the document as PDF and verify the output file.

Without step 4, the failing fixture also succeeds:

```sh
docker run --rm --platform linux/arm64 --cpus 4 --memory 4g \
  -v "$PWD/fixtures:/fixtures:ro" --entrypoint timeout \
  libreoffice-redline-repro:26.8.3 12s /usr/local/bin/lok-reproduce \
  /fixtures/hidden-deletion.docx /tmp/out.pdf
```

## Contents and sharing

This directory contains only custom reproduction programs, official LibreOfficeKit headers, and synthetic DOCX fixtures. It does not read any customer files. The headers in `include/LibreOfficeKit/` come from the official `libreoffice-26.8.3.1` source tag and retain their MPL-2.0 license notices.

A ready-to-use report is available in `BUG-REPORT.md`; the short repository description is in `DESCRIPTION.txt`. The search for existing reports and comparison with related issues are documented in `BUG-REPORT-SEARCH.md`. No bug report or comment has been published.

## Verification results

Confirmed on November 13, 2026 with an image built from this directory:

- Failing fixture without accepting changes: PDF generated successfully, exit code 0.
- Visible changes followed by accepting all changes: PDF generated successfully, exit code 0.
- Hidden deletion followed by accepting all changes: all three runs exceed the 12-second limit and exit with code 124. Each run reaches `load.ok` and `accept-changes.begin`, but not `accept-changes.ok`.

After `python3 check.py`, machine-readable output is available in `results/verified.json`. All runtime containers are removed automatically. The built image remains available locally for repeated tests.
