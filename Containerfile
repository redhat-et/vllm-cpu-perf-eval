# vLLM CPU Performance Evaluation Container
# Based on Red Hat Universal Base Image 9

# Use UBI 9 with Python 3.11 (good balance of compatibility and features)
FROM registry.redhat.io/ubi9/python-311:latest

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

# Install vLLM with CPU support
# Note: Adjust version as needed, use --extra-index-url for CPU-optimized builds if available
RUN pip install --no-cache-dir \
    vllm

# Install GuideLLM for benchmarking
# Note: Using Maryam's fork if it has the saturation detection / embedding support
RUN pip install --no-cache-dir \
    guidellm

# Install additional performance tools
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    psutil

# Set environment variables for optimal CPU performance
# Note: OMP_NUM_THREADS should be set at runtime based on available cores
ENV VLLM_CPU_KVCACHE_SPACE=40

# Default command (can be overridden)
CMD ["/bin/bash"]

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import vllm; import guidellm" || exit 1
