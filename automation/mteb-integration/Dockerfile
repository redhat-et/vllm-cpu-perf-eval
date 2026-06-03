FROM python:3.11-slim

LABEL maintainer="vLLM CPU Performance Evaluation"
LABEL description="MTEB (Massive Text Embedding Benchmark) for vLLM CPU and RHAIIS"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /workspace

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel

# Install PyTorch CPU version first
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install MTEB and other dependencies from PyPI
RUN pip install \
    mteb \
    numpy \
    pandas \
    requests \
    sentence-transformers

# Copy custom vLLM CPU wrapper
COPY wrappers/vllm_cpu_wrapper.py /opt/mteb/vllm_cpu_wrapper.py
ENV PYTHONPATH="/opt/mteb:${PYTHONPATH}"

# Copy scripts
COPY scripts/ /opt/mteb/scripts/
RUN chmod +x /opt/mteb/scripts/*.py

# Create results directory
RUN mkdir -p /results

# Default command
CMD ["python", "-c", "import mteb; print(f'MTEB version: {mteb.__version__}')"]
