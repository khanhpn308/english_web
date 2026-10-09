# syntax=docker/dockerfile:1.7
# T090 CANDIDATE ONLY: immutable FROM references MUST be injected by host.
# This image is NOT an approved verification executor until provenance,
# dependency hashes, offline database digests, and live isolation tests pass.
ARG PYTHON_BASE_IMAGE
ARG NODE_BASE_IMAGE
ARG OSV_SNAPSHOT_IMAGE
FROM $NODE_BASE_IMAGE AS node_toolchain
# Snapshot source must be an immutable, separately attested OCI digest.
FROM $OSV_SNAPSHOT_IMAGE AS osv_snapshot
FROM $PYTHON_BASE_IMAGE AS verifier

SHELL ["/bin/sh", "-eu", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CI=true \
    T090_OSV_OFFLINE=1 \
    OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY=/opt/osv-db \
    SEMGREP_SEND_METRICS=off \
    SEMGREP_ENABLE_VERSION_CHECK=0 \
    GITLEAKS_BIN=/usr/local/bin/gitleaks \
    OSV_SCANNER_BIN=/usr/local/bin/osv-scanner \
    SEMGREP_BIN=/opt/semgrep-venv/bin/semgrep \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers \
    PATH=/opt/toolchain/node_modules/.bin:/usr/local/bin:/usr/bin:/bin

# Debian snapshot is date-locked. APT must authenticate the signed Debian
# InRelease metadata using its pinned base-image archive keyring; additional
# SHA-256 pins fix the exact signed Release bytes and package index chain.
# Candidate-only: this is NOT independent operator release approval.
COPY debian-inrelease.sha256 /opt/locks/debian-inrelease.sha256
RUN printf '%s\n' \
      'Types: deb' \
      'URIs: https://snapshot.debian.org/archive/debian/20261008T000000Z/' \
      'Suites: bookworm bookworm-updates' \
      'Components: main' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
      'Check-Valid-Until: no' \
      '' \
      'Types: deb' \
      'URIs: https://snapshot.debian.org/archive/debian-security/20261008T000000Z/' \
      'Suites: bookworm-security' \
      'Components: main' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
      'Check-Valid-Until: no' \
      > /etc/apt/sources.list.d/debian.sources \
    && rm -f /etc/apt/sources.list /etc/apt/sources.list.d/*.list \
    && apt-get update \
    && sha256sum --check /opt/locks/debian-inrelease.sha256 \
    && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node_toolchain /usr/local/bin/node /usr/local/bin/node
COPY --from=node_toolchain /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && test -f /usr/local/lib/node_modules/npm/bin/npx-cli.js

WORKDIR /opt/toolchain
COPY package.json package-lock.json /opt/toolchain/
# Script execution is forbidden during trusted dependency provisioning.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && ln -s /opt/toolchain/node_modules /node_modules

# Playwright native OS dependencies use the same signed, byte-locked Debian
# snapshot. Browser binaries come from the signed immutable OCI snapshot,
# never a mutable CDN download during this Docker build.
RUN node /opt/toolchain/node_modules/playwright/cli.js install-deps chromium \
    && sha256sum --check /opt/locks/debian-inrelease.sha256 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=osv_snapshot /opt/playwright-browsers /opt/playwright-browsers
RUN node -e 'const b=require("/opt/toolchain/node_modules/playwright-core/browsers.json").browsers.find(x=>x.name==="chromium-headless-shell"); if(!b) process.exit(3); const p="/opt/playwright-browsers/chromium_headless_shell-"+b.revision; if(!require("fs").existsSync(p))process.exit(4);' \
    && chmod -R a+rX /opt/playwright-browsers

# The original lock is retained only for OSV's requirements.txt parser.
# It is NEVER used to install Python dependencies into the image.
COPY requirements-dev.lock /opt/locks/requirements-dev.lock
# Byte-verified Linux/Python 3.12 candidate wheel locks; never resolve an
# unpinned dependency or build from a Python sdist during image construction.
COPY requirements-dev-hashed.lock /opt/locks/requirements-dev-hashed.lock
COPY semgrep-hashed.lock /opt/locks/semgrep-hashed.lock
RUN --mount=type=bind,source=wheels,target=/opt/wheels,readonly \
    python3 -m pip install --no-index --only-binary=:all: --require-hashes \
      --find-links=/opt/wheels/dev -r /opt/locks/requirements-dev-hashed.lock \
    && python3 -m venv /opt/semgrep-venv \
    && /opt/semgrep-venv/bin/pip install --no-index --only-binary=:all: --require-hashes \
      --find-links=/opt/wheels/semgrep -r /opt/locks/semgrep-hashed.lock \
    && python3 -m pip check \
    && /opt/semgrep-venv/bin/pip check

# Fixed release checksums originate from existing T089 host CI.
RUN curl --fail --location --silent --show-error \
      'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz' \
      --output /tmp/gitleaks.tar.gz \
    && echo '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  /tmp/gitleaks.tar.gz' | sha256sum -c - \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && rm /tmp/gitleaks.tar.gz \
    && curl --fail --location --silent --show-error \
      'https://github.com/google/osv-scanner/releases/download/v2.6.0/osv-scanner_linux_amd64' \
      --output /usr/local/bin/osv-scanner \
    && echo 'ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108  /usr/local/bin/osv-scanner' | sha256sum -c - \
    && chmod 0755 /usr/local/bin/osv-scanner

# Immutable, content-addressed candidate snapshot: no mutable network download.
# Host CI verifies signature/source identity, then Docker verifies exact ZIP bytes.
# Neither the snapshot nor these hashes represents operator approval.
ARG OSV_NPM_SHA256
ARG OSV_PYPI_SHA256
COPY --from=osv_snapshot /opt/osv-db/osv-scanner/npm/all.zip /opt/osv-db/osv-scanner/npm/all.zip
COPY --from=osv_snapshot /opt/osv-db/osv-scanner/PyPI/all.zip /opt/osv-db/osv-scanner/PyPI/all.zip
RUN test -n "$OSV_NPM_SHA256" \
    && test -n "$OSV_PYPI_SHA256" \
    && printf '%s  %s\n' "$OSV_NPM_SHA256" /opt/osv-db/osv-scanner/npm/all.zip | sha256sum -c - \
    && printf '%s  %s\n' "$OSV_PYPI_SHA256" /opt/osv-db/osv-scanner/PyPI/all.zip | sha256sum -c - \
    && sha256sum /opt/osv-db/osv-scanner/npm/all.zip \
                 /opt/osv-db/osv-scanner/PyPI/all.zip \
        > /opt/osv-db/archive.sha256
# OSV-Scanner >=2.5 uses the osv-scalibr directory for local matching.
# The official legacy osv-scanner directory alone does NOT satisfy v2.6.
# Present both layouts via read-only in-image symlinks. No mutable DB mount.
RUN for ecosystem in npm PyPI; do \
      mkdir -p "/opt/osv-db/osv-scalibr/$ecosystem"; \
      ln -s "/opt/osv-db/osv-scanner/$ecosystem/all.zip" \
        "/opt/osv-db/osv-scalibr/$ecosystem/all.zip"; \
      test -s "/opt/osv-db/osv-scalibr/$ecosystem/all.zip"; \
    done

RUN python3 --version && node --version && npm --version \
    && git --version && gitleaks version \
    && osv-scanner --version \
    && /opt/semgrep-venv/bin/semgrep --version \
    && test -s /opt/osv-db/archive.sha256

WORKDIR /workspace
USER 65534:65534
