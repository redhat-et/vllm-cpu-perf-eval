FROM registry.access.redhat.com/ubi10/python-312-minimal:10.2-1779803286

LABEL maintainer="vllm-cpu-perf-eval"
LABEL description="HuggingFace model downloader for vLLM CPU performance evaluation"
LABEL version="1.0"

# Install huggingface_hub
RUN pip install --no-cache-dir huggingface_hub

# Copy download script with executable permissions
COPY --chmod=755 download_model.py /usr/local/bin/download_model.py

# Default entrypoint for direct model downloads
ENTRYPOINT ["python3"]
CMD ["/usr/local/bin/download_model.py", "--help"]
