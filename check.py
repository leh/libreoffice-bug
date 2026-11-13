#!/usr/bin/env python3
# Check the failing case, visible changes, and export without accepting changes.
from pathlib import Path
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parent
IMAGE = "libreoffice-redline-repro:26.8.3"
CASES = [("hidden-deletion", False, 0), ("visible-deletion", True, 0)] + [
    ("hidden-deletion", True, 124)
] * 3
results = []
for index, (fixture, accept, expected) in enumerate(CASES):
    executable = "/usr/local/bin/run-reproducer" if accept else "/usr/local/bin/lok-reproduce"
    name = f"diag-lo2683-minimal-{index}"
    command = [
        "docker", "run", "--rm", "--platform", "linux/arm64", "--name", name,
        "--cpus", "4", "--memory", "4g", "-v", str(ROOT / "fixtures") + ":/fixtures:ro",
        "--entrypoint", "timeout", IMAGE, "12s", executable,
        f"/fixtures/{fixture}.docx", "/tmp/out.pdf",
    ]
    started = time.monotonic()
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        raise
    record = {
        "fixture": fixture, "accept_changes": accept, "expected": expected,
        "exit": process.returncode, "seconds": round(time.monotonic() - started, 3),
        "stdout": process.stdout, "stderr": process.stderr,
    }
    results.append(record)
    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    (output / "verified.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(record), flush=True)
    assert process.returncode == expected, record
    assert "load.ok" in process.stderr, record
    if expected == 124:
        assert "accept-changes.begin" in process.stderr and "accept-changes.ok" not in process.stderr, record
    else:
        assert "save.ok" in process.stderr and "PDF:" in process.stderr, record
print(f"{len(results)} expectations confirmed.")
