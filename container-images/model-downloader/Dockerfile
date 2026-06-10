FROM registry.access.redhat.com/ubi10/python-312-minimal:10.2-1779803286

LABEL maintainer="vllm-cpu-perf-eval"
LABEL description="HuggingFace model and dataset downloader for vLLM CPU performance evaluation"
LABEL version="3.0"

# Install dependencies
# - huggingface_hub: for model downloads
# - datasets: for HuggingFace dataset downloads
RUN pip install --no-cache-dir huggingface_hub datasets

# Copy unified download script
COPY --chmod=755 download.py /usr/local/bin/download.py

# Default entrypoint
ENTRYPOINT ["python3", "/usr/local/bin/download.py"]
CMD ["--help"]
