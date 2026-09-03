FROM python:3.11-slim

LABEL maintainer="vLLM CPU Performance Evaluation"
LABEL description="LM Evaluation Harness (lm-eval) for vLLM CPU and RHAIIS accuracy testing"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN pip install --upgrade pip==24.3.1 setuptools==75.6.0 wheel==0.45.1

# [api] extra pulls in the openai client required for --model local-completions
# Pin to a specific stable release; update this version after testing a newer release
RUN pip install "lm_eval[api]==0.4.7"

# lm_eval eagerly imports hf_vlms.py, which sets AUTO_MODEL_CLASS =
# transformers.AutoModelForVision2Seq at class-definition time.  Transformers'
# lazy loader guards that class behind torch availability; since this image is
# API-only (--model local-completions), HFMultimodalLM is never instantiated,
# so AUTO_MODEL_CLASS = None is safe.  Using getattr avoids the import-time
# AttributeError without requiring torch.  Tested with lm_eval 0.4.7.
RUN find /usr/local/lib -name 'hf_vlms.py' -path '*/lm_eval/*' \
    -exec sed -i \
        's/AUTO_MODEL_CLASS = transformers\.AutoModelForVision2Seq/AUTO_MODEL_CLASS = getattr(transformers, "AutoModelForVision2Seq", None)/' \
    {} \;

# hellaswag was migrated from a loading script to Parquet; the bundled task YAML
# still references `trust_remote_code: true` (unsupported since datasets ≥ 3.x)
# and the bare "hellaswag" path (which now requires the "Rowan/" namespace).
# Patch both fields in-place so the dataset loads without a loading script.
# Tested with lm_eval 0.4.7.
RUN find /usr/local/lib -path '*/lm_eval/tasks/hellaswag/*.yaml' | \
    xargs -I{} sed -i \
        -e 's|dataset_path: hellaswag|dataset_path: Rowan/hellaswag|g' \
        -e '/trust_remote_code:/d' \
    {}

# winogrande was also migrated from a loading script to Parquet; the bundled
# task YAML still uses the bare "winogrande" path (requires "allenai/" namespace)
# and sets trust_remote_code: true (unsupported since datasets ≥ 3.x).
# Tested with lm_eval 0.4.7.
RUN find /usr/local/lib -path '*/lm_eval/tasks/winogrande/*.yaml' | \
    xargs -I{} sed -i \
        -e 's|dataset_path: winogrande|dataset_path: allenai/winogrande|g' \
        -e '/trust_remote_code:/d' \
    {}

# gsm8k was migrated to the openai/gsm8k namespace on HuggingFace; the bundled
# task YAML still uses the bare "gsm8k" path, which breaks with recent
# huggingface_hub/datasets (HfUriError: Repository id must be 'namespace/name').
# Tested with lm_eval 0.4.7.
RUN find /usr/local/lib -path '*/lm_eval/tasks/gsm8k/*.yaml' | \
    xargs -I{} sed -i \
        -e 's|dataset_path: gsm8k|dataset_path: openai/gsm8k|g' \
        -e '/trust_remote_code:/d' \
    {}

# Build-time smoke test: verifies sed patches were applied and core tasks load.
RUN set -eux; \
    HELLASWAG_YAML="$(find /usr/local/lib -path '*/lm_eval/tasks/hellaswag/*.yaml' -print -quit)"; \
    WINOGRANDE_YAML="$(find /usr/local/lib -path '*/lm_eval/tasks/winogrande/*.yaml' -print -quit)"; \
    GSM8K_YAML="$(find /usr/local/lib -path '*/lm_eval/tasks/gsm8k/gsm8k.yaml' -print -quit)"; \
    test -n "${HELLASWAG_YAML}"; \
    test -n "${WINOGRANDE_YAML}"; \
    test -n "${GSM8K_YAML}"; \
    grep -q 'dataset_path: Rowan/hellaswag' "${HELLASWAG_YAML}"; \
    ! grep -q 'trust_remote_code:' "${HELLASWAG_YAML}"; \
    grep -q 'dataset_path: allenai/winogrande' "${WINOGRANDE_YAML}"; \
    ! grep -q 'trust_remote_code:' "${WINOGRANDE_YAML}"; \
    grep -q 'dataset_path: openai/gsm8k' "${GSM8K_YAML}"; \
    ! grep -q 'trust_remote_code:' "${GSM8K_YAML}"; \
    python - <<'PY'
from lm_eval.tasks import TaskManager

manager = TaskManager()
for task_name in ("hellaswag", "winogrande", "gsm8k", "truthfulqa_mc1"):
    assert task_name in manager.all_tasks, f"missing task: {task_name}"
PY

RUN lm_eval --help > /dev/null

RUN groupadd --gid 1000 lmeval \
    && useradd --uid 1000 --gid lmeval --create-home lmeval \
    && mkdir -p /results \
    && chown -R lmeval:lmeval /workspace /results

USER lmeval

ENTRYPOINT ["lm_eval"]
CMD ["--help"]
