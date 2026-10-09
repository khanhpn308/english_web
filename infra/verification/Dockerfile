# syntax=docker/dockerfile:1.7
# T090 CANDIDATE ONLY: immutable FROM references MUST be injected by host.
# This image is NOT an approved verification executor until provenance,
# dependency hashes, offline database digests, and live isolation tests pass.
ARG PYTHON_BASE_IMAGE
ARG NODE_BASE_IMAGE
FROM $NODE_BASE_IMAGE AS node_toolchain
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
    PATH=/opt/toolchain/node_modules/.bin:/usr/local/bin:/usr/bin:/bin

# Candidate-only package install. Apt snapshot/version provenance is NOT yet locked.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node_toolchain /usr/local/bin/node /usr/local/bin/node
COPY --from=node_toolchain /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

WORKDIR /opt/toolchain
COPY package.json package-lock.json /opt/toolchain/
# Script execution is forbidden during trusted dependency provisioning.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && ln -s /opt/toolchain/node_modules /node_modules

COPY requirements-dev.lock /opt/locks/requirements-dev.lock
# Versions are pinned but wheel hashes are NOT present: approval must remain false.
RUN python3 -m pip install -r /opt/locks/requirements-dev.lock \
    && python3 -m venv /opt/semgrep-venv \
    && /opt/semgrep-venv/bin/pip install 'semgrep==1.178.0'

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

# Offline DB download happens during trusted image BUILD, never during Worker tests.
# Exact ZIP digests must be approved and pinned before the image is trusted.
RUN for ecosystem in npm PyPI; do \
      mkdir -p "/opt/osv-db/osv-scanner/$ecosystem"; \
      curl --fail --location --silent --show-error \
        "https://osv-vulnerabilities.storage.googleapis.com/$ecosystem/all.zip" \
        --output "/opt/osv-db/osv-scanner/$ecosystem/all.zip"; \
    done \
    && sha256sum /opt/osv-db/osv-scanner/npm/all.zip \
                 /opt/osv-db/osv-scanner/PyPI/all.zip \
        > /opt/osv-db/archive.sha256

RUN python3 --version && node --version && npm --version \
    && git --version && gitleaks version \
    && osv-scanner --version \
    && /opt/semgrep-venv/bin/semgrep --version \
    && test -s /opt/osv-db/archive.sha256

WORKDIR /workspace
USER 65534:65534
