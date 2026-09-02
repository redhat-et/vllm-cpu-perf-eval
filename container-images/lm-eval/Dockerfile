FROM python:3.11-slim

LABEL maintainer="vLLM CPU Performance Evaluation"
LABEL description="LM Evaluation Harness (lm-eval) for vLLM CPU and RHAIIS accuracy testing"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN pip install --upgrade pip==24.3.1 setuptools==75.6.0 wheel==0.45.1

# [api] extra pulls in the openai client required for --model local-completions
# Pin to a specific stable release; update this version after testing a newer release
RUN pip install "lm_eval[api]==0.4.6"

RUN mkdir -p /results

ENTRYPOINT ["lm_eval"]
CMD ["--help"]
