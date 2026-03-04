# vLLM CPU Performance Evaluation Container
# Based on Red Hat Universal Base Image 9

# Use UBI 9 with Python 3.11 (pinned by digest for reproducibility)
# Image: registry.redhat.io/ubi9/python-311:latest as of 2026-03-03
FROM registry.redhat.io/ubi9/python-311@sha256:56193de31c185cebfb8a9f0a7624407f49b1cdf923403d5d777027b285701d78

# Metadata
LABEL name="vllm-cpu-perf-eval" \
      version="1.0" \
      description="vLLM CPU Performance Evaluation Test Suite" \
      maintainer="Red Hat OCTO Edge Team" \
      io.k8s.description="Container for running vLLM CPU performance benchmarks" \
      io.k8s.display-name="vLLM CPU Performance Evaluator"

# Set working directory
WORKDIR /opt/vllm-perf

# Install system dependencies and create directories
USER root
RUN dnf install -y \
    gcc \
    gcc-c++ \
    git \
    numactl \
    && dnf clean all

# Create directories and set ownership for non-root user
RUN mkdir -p /opt/vllm-perf/models \
             /opt/vllm-perf/results \
             /opt/vllm-perf/scripts \
    && chown -R 1001:0 /opt/vllm-perf \
    && chmod -R g=u /opt/vllm-perf

# Switch to non-root user for pip installations
USER 1001

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install vLLM with CPU support (pinned version for reproducibility)
RUN pip install --no-cache-dir \
    'vllm>=0.16.0,<0.17.0'

# Install GuideLLM for benchmarking (pinned version for reproducibility)
RUN pip install --no-cache-dir \
    'guidellm>=0.5.0,<0.6.0'

# Install additional performance tools (pinned versions for reproducibility)
RUN pip install --no-cache-dir \
    'numpy>=2.0.0,<3.0.0' \
    'pandas>=3.0.0,<4.0.0' \
    'psutil>=7.0.0,<8.0.0'

# Install Ansible for test automation
RUN pip install --no-cache-dir \
    'ansible>=9.0.0,<13.0.0'

# Copy repository files into the container
COPY --chown=1001:0 automation/ /opt/vllm-perf/automation/
COPY --chown=1001:0 models/ /opt/vllm-perf/models/
COPY --chown=1001:0 tests/ /opt/vllm-perf/tests/
COPY --chown=1001:0 docs/ /opt/vllm-perf/docs/
COPY --chown=1001:0 README.md /opt/vllm-perf/

# Set environment variables for optimal CPU performance
# Note: OMP_NUM_THREADS should be set at runtime based on available cores
ENV VLLM_CPU_KVCACHE_SPACE=40

# Default command (can be overridden)
CMD ["/bin/bash"]

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import vllm; import guidellm" || exit 1
