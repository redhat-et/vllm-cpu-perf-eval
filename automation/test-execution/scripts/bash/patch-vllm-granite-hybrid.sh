#!/bin/bash
# ==============================================================================
# Patch vLLM v0.25.1 for Granite-4.0 hybrid model support
# ==============================================================================
# vLLM v0.25.1 does not recognize the 'full_attention' and 'linear_attention'
# layer types used by Granite-4.0 models with HuggingFace Transformers >= 5.13.0.
# This was fixed upstream in vLLM PR #47867 but has not yet been released.
#
# This script extracts granitemoehybrid.py from the container image, applies
# the fix, and writes it to a local path for volume-mounting into the container.
#
# TODO: Remove this patch once vLLM > v0.25.1 is released with PR #47867.
#
# Usage:
#   ./patch-vllm-granite-hybrid.sh [options]
#
# Options:
#   --output-dir DIR         Directory for patched file (default: /tmp/vllm-patch)
#   --container-image IMAGE  vLLM container image (default: docker.io/vllm/vllm-openai-cpu:v0.25.1)
#   --check                  Check if patch is needed; also removes any stale overlay.
#                            Exit 0 if patch needed, 1 if not.
#   -h, --help               Show this help
#
# The patched file should be mounted into the container:
#   podman run ... \
#     -v /tmp/vllm-patch/granitemoehybrid.py:/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/granitemoehybrid.py:z \
#     ...
# ==============================================================================

set -euo pipefail

OUTPUT_DIR="/tmp/vllm-patch"
CONTAINER_IMAGE="${VLLM_CONTAINER_IMAGE:-docker.io/vllm/vllm-openai-cpu:v0.25.1}"
CHECK_ONLY=false
CONTAINER_PATH="/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/granitemoehybrid.py"

usage() {
    echo "Usage: $0 [--output-dir DIR] [--container-image IMAGE] [--check]"
    echo ""
    echo "Patches vLLM v0.25.1 to support Granite-4.0 hybrid models."
    echo "TODO: Remove once vLLM > v0.25.1 ships with PR #47867."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --container-image) CONTAINER_IMAGE="$2"; shift 2 ;;
        --check) CHECK_ONLY=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

ENGINE="${CONTAINER_ENGINE:-$(command -v podman 2>/dev/null || command -v docker 2>/dev/null)}"
if [[ -z "${ENGINE}" ]]; then
    echo "ERROR: No container engine (podman/docker) found" >&2
    exit 1
fi

# Returns the image content ID (sha256:...) so the stamp survives retags.
# Falls back to the image reference if inspect is unavailable.
resolve_image_id() {
    "${ENGINE}" image inspect --format '{{.Id}}' "$1" 2>/dev/null || echo "$1"
}

assert_output_dir_safe() {
    local dir="$1"
    if [[ ! -e "${dir}" ]]; then
        return 0
    fi
    if [[ ! -d "${dir}" ]]; then
        echo "ERROR: OUTPUT_DIR is not a directory: ${dir}" >&2
        exit 1
    fi
    if [[ ! -O "${dir}" ]]; then
        echo "ERROR: OUTPUT_DIR is not owned by the current user: ${dir}" >&2
        exit 1
    fi
    if find "${dir}" -maxdepth 0 \( -perm -g=w -o -perm -o=w \) | grep -q .; then
        echo "ERROR: OUTPUT_DIR is writable by group or others: ${dir}" >&2
        exit 1
    fi
}

check_needed() {
    local content
    if ! content=$("${ENGINE}" run --rm --entrypoint cat "${CONTAINER_IMAGE}" "${CONTAINER_PATH}"); then
        echo "ERROR: Failed to inspect ${CONTAINER_PATH} in ${CONTAINER_IMAGE}" >&2
        return 2
    fi
    if echo "${content}" | grep -q '"full_attention"'; then
        return 1
    fi
    return 0
}

if [[ "${CHECK_ONLY}" == "true" ]]; then
    rc=0
    check_needed || rc=$?
    case "${rc}" in
        0)
            echo "Patch needed: ${CONTAINER_IMAGE} missing full_attention support"
            exit 0
            ;;
        1)
            echo "Patch not needed: ${CONTAINER_IMAGE} already has full_attention support"
            assert_output_dir_safe "${OUTPUT_DIR}"
            if [[ -f "${OUTPUT_DIR}/granitemoehybrid.py" ]]; then
                rm -f "${OUTPUT_DIR}/granitemoehybrid.py" "${OUTPUT_DIR}/.image-id"
                echo "Removed stale overlay: ${OUTPUT_DIR}/granitemoehybrid.py"
            fi
            exit 1
            ;;
        *)
            exit "${rc}"
            ;;
    esac
fi

rc=0
check_needed || rc=$?
if [[ "${rc}" -eq 1 ]]; then
    echo "Patch not needed — container already has full_attention support"
    echo "Skipping patch (vLLM version likely > v0.25.1)"
    assert_output_dir_safe "${OUTPUT_DIR}"
    if [[ -f "${OUTPUT_DIR}/granitemoehybrid.py" ]]; then
        rm -f "${OUTPUT_DIR}/granitemoehybrid.py" "${OUTPUT_DIR}/.image-id"
        echo "Removed stale overlay: ${OUTPUT_DIR}/granitemoehybrid.py"
    fi
    exit 0
elif [[ "${rc}" -ne 0 ]]; then
    exit "${rc}"
fi

assert_output_dir_safe "${OUTPUT_DIR}"

STAMP_FILE="${OUTPUT_DIR}/.image-id"
if [[ -f "${OUTPUT_DIR}/granitemoehybrid.py" ]] && \
   grep -q '"full_attention"' "${OUTPUT_DIR}/granitemoehybrid.py" 2>/dev/null && \
   [[ -f "${STAMP_FILE}" ]] && \
   [[ "$(cat "${STAMP_FILE}")" == "$(resolve_image_id "${CONTAINER_IMAGE}")" ]]; then
    echo "Patch already applied at ${OUTPUT_DIR}/granitemoehybrid.py (image: ${CONTAINER_IMAGE})"
    exit 0
fi

mkdir -p "${OUTPUT_DIR}"
chmod 700 "${OUTPUT_DIR}"
assert_output_dir_safe "${OUTPUT_DIR}"

echo "Extracting granitemoehybrid.py from ${CONTAINER_IMAGE}..."
"${ENGINE}" run --rm --entrypoint cat "${CONTAINER_IMAGE}" "${CONTAINER_PATH}" \
    > "${OUTPUT_DIR}/granitemoehybrid.py"

echo "Applying full_attention / linear_attention patch..."
sed -i \
    '/"mamba": GraniteMoeHybridMambaDecoderLayer,/a\    # Transformers >= 5.13.0 (vLLM PR #47867 backport — remove when vLLM > v0.25.1)\n    "full_attention": GraniteMoeHybridAttentionDecoderLayer,\n    "linear_attention": GraniteMoeHybridMambaDecoderLayer,' \
    "${OUTPUT_DIR}/granitemoehybrid.py"

if grep -q '"full_attention"' "${OUTPUT_DIR}/granitemoehybrid.py"; then
    echo "$(resolve_image_id "${CONTAINER_IMAGE}")" > "${STAMP_FILE}"
    echo "Patch applied successfully: ${OUTPUT_DIR}/granitemoehybrid.py"
    echo ""
    echo "Mount into container with:"
    echo "  -v ${OUTPUT_DIR}/granitemoehybrid.py:${CONTAINER_PATH}:z"
else
    echo "ERROR: Patch failed — full_attention not found in output" >&2
    exit 1
fi
