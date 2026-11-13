#!/bin/sh
set -eu
# A fresh profile and a private input copy prevent interference from lock files.
profile=$(mktemp -d /tmp/independent-lok-XXXXXX)
soffice --headless --invisible --nologo --norestore --terminate_after_init \
  "-env:UserInstallation=file://$profile"
cp /usr/local/share/lok-repro/Repro.xba "$profile/user/basic/Standard/Repro.xba"
sed -i 's@</library:library>@<library:element library:name="Repro"/></library:library>@' \
  "$profile/user/basic/Standard/script.xlb"
export LOK_PROFILE_PATH="$profile"
export LOK_REGISTER_CALLBACK=1
export LOK_RUN_MACRO="macro:///Standard.Repro.AcceptChanges"
exec /usr/local/bin/lok-reproduce "$@"
