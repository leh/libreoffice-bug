FROM debian:trixie-slim
ARG LO_VERSION=26.8.3
ARG LO_SHA256=378a0766e4a815a5a96fb7473f346d072e23e3cc28606bdc8cd6f834cfaa14db
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl gcc libc6-dev fonts-liberation \
    && curl -fL --retry 2 "https://download.documentfoundation.org/libreoffice/stable/${LO_VERSION}/deb/aarch64/LibreOffice_${LO_VERSION}_Linux_aarch64_deb.tar.gz" -o /tmp/release.tar.gz \
    && printf '%s  %s\n' "$LO_SHA256" /tmp/release.tar.gz | sha256sum -c - \
    && mkdir /tmp/lo-release \
    && tar -xzf /tmp/release.tar.gz -C /tmp/lo-release \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends /tmp/lo-release/*/DEBS/*.deb \
    && rm -rf /tmp/lo-release /tmp/release.tar.gz /var/lib/apt/lists/*
# The official TDF packages require these system libraries.
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       libxinerama1 libx11-6 libx11-xcb1 libxext6 libnss3 libnspr4 \
       libdbus-1-3 libcairo2 libglib2.0-0t64 libcups2t64 libfontconfig1 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*
COPY include/ /src/include/
COPY reproduce.c /src/reproduce.c
RUN gcc -std=c11 -O0 -g -Wall -Wextra -I/src/include /src/reproduce.c -ldl -pthread -o /usr/local/bin/lok-reproduce \
    && useradd --create-home --uid 1000 repro
COPY Repro.xba /usr/local/share/lok-repro/Repro.xba
COPY --chmod=755 run-reproducer.sh /usr/local/bin/run-reproducer
ENV LANG=C.UTF-8
ENV LOK_PROGRAM_PATH=/opt/libreoffice26.8/program
ENV PATH="/opt/libreoffice26.8/program:${PATH}"
USER repro
ENTRYPOINT ["timeout", "12s", "/usr/local/bin/run-reproducer"]
