#!/bin/sh
set -eu
# A separate process, a fresh profile and a private input prevent LOK/lock interference.
fixture="$1"
hidden="$2"
mode="$3"
show_changes="${4:-preserve}"
workdir=$(mktemp -d /tmp/external-uno-XXXXXX)
profile="$workdir/profile"
mkdir -p "$profile"
cp "$fixture" "$workdir/input.docx"
if find "$workdir" -name '.~lock.*' | read -r existing_lock; then
    printf 'Unexpected input lock: %s\n' "$existing_lock" >&2
    exit 1
fi
# Install the exact same Basic macro for every route so profile setup is constant.
soffice --headless --invisible --nologo --norestore --terminate_after_init \
    "-env:UserInstallation=file://$profile" > /output/profile-init.stdout 2> /output/profile-init.stderr
cp /source/Repro.xba "$profile/user/basic/Standard/Repro.xba"
sed -i 's@</library:library>@<library:element library:name="Repro"/></library:library>@' \
    "$profile/user/basic/Standard/script.xlb"
sha256sum /source/Repro.xba "$profile/user/basic/Standard/Repro.xba" > /output/macro-sha256.txt
soffice --version > /output/listener-version.txt
printf 'program=%s\nprofile=%s\ninput=%s\nhidden=%s\nmode=%s\n' \
    "$(command -v soffice)" "$profile" "$workdir/input.docx" "$hidden" "$mode" > /output/environment.txt
cp /opt/libreoffice26.8/program/versionrc /output/listener-versionrc.txt
soffice --headless --nologo --nodefault --norestore --nofirststartwizard \
    "-env:UserInstallation=file://$profile" \
    '--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ServiceManager' \
    > /output/listener.stdout 2> /output/listener.stderr &
listener_pid=$!
printf 'listener_wrapper_pid=%s\n' "$listener_pid" >> /output/environment.txt
cleanup() {
    kill "$listener_pid" 2>/dev/null || true
    wait "$listener_pid" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
set +e
timeout 20s /opt/libreoffice26.8/program/python /harness/client.py \
    "$workdir/input.docx" /output/output.pdf --hidden "$hidden" --mode "$mode" --show-changes "$show_changes" \
    > /output/client.jsonl 2> /output/client.stderr
client_exit=$?
set -e
printf '%s\n' "$client_exit" > /output/client-exit.txt
# Copy evidence after the client returns or times out; never reuse this profile/input.
if command -v ps >/dev/null 2>&1; then ps -ef > /output/processes.txt; fi
if test -f "$workdir/input.docx"; then cp "$workdir/input.docx" /output/input.docx; fi
exit "$client_exit"
