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
RUN pip install --upgrade pip==24.3.1 setuptools==75.6.0 wheel==0.45.1

# Install PyTorch CPU version first (pinned for reproducibility)
RUN pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

# Install MTEB and other dependencies from PyPI (pinned versions)
# OpenAIAPIEncodeWrapper for HTTP vLLM endpoints landed in MTEB 2.19.0
# (embeddings-benchmark/mteb#4834).
RUN pip install \
    mteb==2.20.10 \
    numpy==2.1.3 \
    pandas==2.2.3 \
    requests==2.32.3 \
    sentence-transformers==3.3.1

# Copy benchmark runner script
COPY scripts/ /opt/mteb/scripts/
RUN chmod +x /opt/mteb/scripts/*.py

# Create results directory
RUN mkdir -p /results

# Default command
CMD ["python", "-c", "import mteb; from mteb.models import OpenAIAPIEncodeWrapper; print(f'MTEB version: {mteb.__version__}')"]
