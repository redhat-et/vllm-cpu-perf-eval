# LM Eval Container Image

Container image for running
[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
against vLLM CPU (or RHAIIS) OpenAI-compatible API endpoints.

Used by the `lm-eval` cpueval suite and `lm-eval-benchmark.yml` Ansible playbook.

## Image Details

| Property | Value |
| --- | --- |
| Base | `python:3.11-slim` |
| Package | `lm_eval[api]==0.4.7` |
| Default tag | `quay.io/vllm-cpu-perf-eval/lm-eval:latest` |
| Entrypoint | `lm_eval` |
| User | `lmeval` (uid 1000) |

The `[api]` extra installs the OpenAI client required for `--model local-completions`
and `--model local-chat-completions` backends.

## Build

```bash
cd container-images/lm-eval
./build.sh
```

Options (see `./build.sh --help`):

```bash
./build.sh --tag my-registry/lm-eval:dev
./build.sh --no-cache
```

## Usage

The image is invoked by Ansible — you typically do not run it manually. For
debugging:

```bash
podman run --rm quay.io/vllm-cpu-perf-eval/lm-eval:latest --help

podman run --rm quay.io/vllm-cpu-perf-eval/lm-eval:latest \
  --model local-completions \
  --model_args "model=Qwen/Qwen3-0.6B,base_url=http://dut-host:8000/v1/completions,tokenizer=Qwen/Qwen3-0.6B" \
  --tasks hellaswag \
  --limit 10 \
  --batch_size 16
```

Set a custom image for the suite:

```bash
export LM_EVAL_IMAGE=my-registry/lm-eval:latest
./cpueval --suite lm-eval --models quick --cores 8 --limit 50
```

## Image Patches

The Dockerfile applies small in-image patches tested with lm_eval 0.4.7:

1. **hf_vlms.py** — Avoids transformers lazy-import error without torch (API-only image)
2. **hellaswag / winogrande tasks** — Updates dataset paths and removes
   `trust_remote_code` for `datasets` ≥ 3.x compatibility

A build-time smoke test verifies task registration for hellaswag, winogrande,
gsm8k, and truthfulqa_mc1.

## Upgrading lm_eval Version

1. Update the pin in `Dockerfile` (`lm_eval[api]==X.Y.Z`)
2. Re-run `./build.sh` and verify the smoke test passes
3. Run a quick benchmark: `./cpueval --suite lm-eval --models quick --cores 8 --limit 50`

Note: lm_eval 0.4.6 was yanked from PyPI; 0.4.7 is the current minimum.

## Related Documentation

- [LM Eval Benchmarking Guide](../../docs/lm-eval-benchmarking.md)
- [Scripts Reference](../../docs/scripts-reference.md#run-lm-eval-suitesh)
- [LM Eval Test Suite](../../tests/lm-eval/lm-eval.md)
