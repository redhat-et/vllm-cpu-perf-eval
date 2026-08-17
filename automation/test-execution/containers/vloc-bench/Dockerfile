# VLoc Bench CLI Harness
# Runs the Cisco VLoc Bench evaluation CLI in a container.
# Sandbox containers are spawned on the host via Docker socket passthrough.
#
# Build:
#   podman build -t vloc-bench-harness .
#
# Run (after sandbox image + dataset are ready):
#   podman run --rm --network host \
#     -v /run/user/$(id -u)/podman/podman.sock:/var/run/docker.sock:z \
#     -v /tmp/vloc-data:/opt/vloc-bench/data/ghsa-vulns:z \
#     -v /tmp/vloc-results:/results:z \
#     vloc-bench-harness \
#     python3 -m vulnerability_localization_benchmark.cli \
#       --config configs/default.yaml \
#       --api-base http://localhost:8200/v1 \
#       --model-name <model> --runner <runner> \
#       --phases a --workers 1 --n-limit 5 \
#       --output-dir /results

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI only — for spawning sandbox containers via host socket
ARG DOCKER_VERSION=27.5.1
RUN ARCH="$(uname -m)" && \
    curl -fsSL \
      "https://download.docker.com/linux/static/stable/${ARCH}/docker-${DOCKER_VERSION}.tgz" \
    | tar xz -C /usr/local/bin --strip-components=1 docker/docker && \
    chmod +x /usr/local/bin/docker

# Pin to a VLoc Bench commit (not floating main) so rebuilds are reproducible.
# Bump this SHA deliberately after reviewing upstream changes.
ARG VLOC_REF=000c19cda9ba027e1d241216768b2b6358685000
RUN git clone https://github.com/cisco-foundation-ai/vulnerability-localization-benchmark.git \
        /opt/vloc-bench \
    && git -C /opt/vloc-bench checkout --detach "${VLOC_REF}" \
    && test "$(git -C /opt/vloc-bench rev-parse HEAD)" = "${VLOC_REF}"

WORKDIR /opt/vloc-bench

# The CLI, agent, model runners, and scoring modules only import
# requests/yaml/tqdm — they talk to vLLM over HTTP, not via torch/vllm.
# Install --no-deps to skip the heavy ML packages listed in pyproject.toml.
RUN pip install --no-cache-dir --no-deps -e . && \
    pip install --no-cache-dir \
        'requests>=2.31' \
        'pyyaml>=6.0' \
        'tqdm>=4.66' \
        'openai>=2.0'

ENV PYTHONPATH=/opt/vloc-bench/src
