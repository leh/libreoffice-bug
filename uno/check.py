#!/usr/bin/env python3
"""Run isolated standalone-UNO cases and verify every produced PDF with Poppler."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile

IMAGE = "libreoffice-redline-repro:26.8.3"


def sha256(filename):
    return hashlib.sha256(filename.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    harness = Path(__file__).resolve().parent
    output = (args.output or root / "results" / "uno").resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, text=True, check=True)
    (output / "image-inspect.json").write_text(image.stdout)
    inputs = {}
    for label in ("hidden-deletion", "visible-deletion"):
        fixture = root / "fixtures" / f"{label}.docx"
        with zipfile.ZipFile(fixture) as archive:
            settings = archive.read("word/settings.xml").decode()
        inputs[label] = {"sha256": sha256(fixture), "bytes": fixture.stat().st_size, "settings_xml": settings}
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    cases = []
    for display in ("preserve", "false"):
        for mode in ("accept", "macro"):
            for repeat in range(1, 4):
                cases.append((f"{display}-{mode}-hidden-{repeat}", "hidden-deletion", "true", mode, display))
            cases.append((f"{display}-{mode}-visible", "visible-deletion", "true", mode, display))
    for display in ("preserve", "false"):
        for fixture_label, fixture_name in (("hidden", "hidden-deletion"), ("visible", "visible-deletion")):
            cases.append((f"{display}-export-only-{fixture_label}", fixture_name, "true", "export-only", display))
    for display in ("preserve", "false"):
        for mode in ("accept", "macro"):
            cases.append((f"{display}-{mode}-hidden-window-visible", "hidden-deletion", "false", mode, display))
    summary = output / "verified.json"
    records = json.loads(summary.read_text()) if args.resume and summary.exists() else []
    completed = {record["label"] for record in records}
    for index, (label, fixture, hidden, mode, display) in enumerate(cases):
        if label in completed:
            continue
        destination = output / label
        destination.mkdir(exist_ok=True)
        if any(destination.iterdir()):
            raise RuntimeError(f"Refusing to reuse nonempty output directory: {destination}")
        name = f"diag-uno-{index}-{label}"
        command = ["docker", "run", "--rm", "--platform", "linux/arm64", "--name", name,
                   "--cpus", "4", "--memory", "4g",
                   "-v", f"{harness}:/harness:ro", "-v", f"{root}:/source:ro", "-v", f"{destination}:/output",
                   "--entrypoint", "timeout", IMAGE, "30s", "/bin/sh", "/harness/run-case.sh",
                   f"/source/fixtures/{fixture}.docx", hidden, mode, display]
        (destination / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        started = time.monotonic()
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=40)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            raise
        finally:
            # Only this case's own container is eligible for cleanup.
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        (destination / "docker.stdout").write_text(process.stdout)
        (destination / "docker.stderr").write_text(process.stderr)
        log_path = destination / "client.jsonl"
        events = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
        phases = [event["phase"] for event in events]
        pdf = destination / "output.pdf"
        record = {"label": label, "fixture": fixture, "hidden": hidden, "mode": mode, "show_changes_request": display,
                  "exit": process.returncode, "seconds": round(time.monotonic() - started, 3),
                  "last_phase": phases[-1] if phases else None, "events": events, "pdf_exists": pdf.exists()}
        if pdf.exists():
            info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
            text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
            (destination / "pdfinfo.txt").write_text(info.stdout + info.stderr)
            (destination / "pdftext.txt").write_text(text.stdout + text.stderr)
            record["pdf"] = {"bytes": pdf.stat().st_size, "sha256": sha256(pdf), "pdfinfo_exit": info.returncode,
                             "pdftotext_exit": text.returncode, "text": text.stdout,
                             "valid_header": pdf.read_bytes().startswith(b"%PDF-")}
            assert info.returncode == 0 and text.returncode == 0 and record["pdf"]["valid_header"], record
            assert "Sample text." in text.stdout, record
            if mode != "export-only":
                assert "Old" not in text.stdout, record
            elif fixture == "visible-deletion":
                # ShowChanges=False returned but did not hide this source's PDF layout.
                assert "Old" in text.stdout, record
            else:
                assert "Old" not in text.stdout, record
        if process.returncode == 0:
            assert "done" in phases and "export.ok" in phases and pdf.exists(), record
            if mode != "export-only":
                accepted = next(event for event in events if event["phase"] == "accept-changes.ok")
                assert accepted["redlines"] == 0, record
        elif process.returncode == 124:
            assert "accept-changes.begin" in phases and "accept-changes.ok" not in phases and not pdf.exists(), record
        else:
            raise RuntimeError(json.dumps(record, indent=2))
        records.append(record)
        (output / "verified.json").write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps({key: record[key] for key in ("label", "exit", "seconds", "last_phase", "pdf_exists")}), flush=True)
    assert len(records) == len(cases), "The comparison matrix is incomplete"
    assert all(record["exit"] == 0 for record in records), "An external UNO control failed or timed out"
    print(f"{len(records)} isolated UNO cases completed and checked.", flush=True)


if __name__ == "__main__":
    main()
