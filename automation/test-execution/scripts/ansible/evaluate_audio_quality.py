#!/usr/bin/env python3
"""Evaluate transcription quality (WER/CER) against a vLLM endpoint.

Sends audio clips to /v1/audio/transcriptions, compares hypotheses to
ground-truth text, and writes quality-results.json.

Prerequisites (on the machine running this script):
    pip install jiwer datasets soundfile requests

Usage:
    # Automated (called by playbook for transcription-quality scenario):
    python3 evaluate_audio_quality.py \\
        --endpoint http://dut:8000 \\
        --output-dir results/audio-models/openai__whisper-small/transcription-quality-<run-id>/ \\
        --model openai/whisper-small \\
        --test-run-id <run-id> --cores 32

    # Manual standalone:
    python3 evaluate_audio_quality.py \\
        --endpoint http://dut:8000 \\
        --output-dir results/audio-models/openai__whisper-small/transcription-quality-<run-id>/ \\
        --model openai/whisper-small

    # Use a local audio directory instead of HuggingFace:
    python3 evaluate_audio_quality.py \\
        --endpoint http://dut:8000 \\
        --output-dir results/ \\
        --audio-dir /path/to/clips/ \\
        --model openai/whisper-small

    The --audio-dir must contain .wav/.mp3/.flac files and a references.json:
      {"file1.mp3": "the ground truth text", ...}

Note: --audio-format applies only to local files (--audio-dir).  When loading
from HuggingFace, clips are always uploaded as WAV (soundfile default).
"""

import argparse
import io
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def _load_hf_dataset(dataset_name, config, split, audio_column, num_clips):
    """Load clips + references from HuggingFace datasets."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Error: 'datasets' package required.  pip install datasets",
              file=sys.stderr)
        sys.exit(1)

    ds = load_dataset(dataset_name, config, split=split, streaming=True)

    clips = []
    for i, sample in enumerate(ds):
        if i >= num_clips:
            break
        audio = sample[audio_column]
        reference = sample.get("text", "")
        clips.append({
            "audio_array": audio["array"],
            "sampling_rate": audio["sampling_rate"],
            "reference": reference,
            "clip_id": f"clip-{i:04d}",
        })

    return clips


def _load_local_clips(audio_dir):
    """Load clips from a local directory with references.json."""
    audio_path = Path(audio_dir)
    refs_file = audio_path / "references.json"
    if not refs_file.exists():
        print(f"Error: {refs_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(refs_file) as fh:
        refs = json.load(fh)

    clips = []
    for filename, reference in refs.items():
        fp = audio_path / filename
        if fp.exists():
            clips.append({
                "file_path": fp,
                "reference": reference,
                "clip_id": fp.stem,
            })
    return clips


def _encode_audio(clip, audio_format="mp3", sample_rate=16000):
    """Encode an audio clip to bytes for upload."""
    try:
        import soundfile as sf
    except ImportError:
        print("Error: 'soundfile' package required.  pip install soundfile",
              file=sys.stderr)
        sys.exit(1)

    if "file_path" in clip:
        with open(clip["file_path"], "rb") as fh:
            return fh.read(), clip["file_path"].suffix.lstrip(".")

    buf = io.BytesIO()
    sf.write(buf, clip["audio_array"], clip["sampling_rate"], format="WAV")
    return buf.getvalue(), "wav"


def _transcribe(endpoint, audio_bytes, audio_ext, model):
    """Send audio to /v1/audio/transcriptions."""
    import requests as req

    url = f"{endpoint.rstrip('/')}/v1/audio/transcriptions"
    files = {"file": (f"audio.{audio_ext}", audio_bytes, f"audio/{audio_ext}")}
    data = {"model": model}
    resp = req.post(url, files=files, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json().get("text", "")


def _compute_metrics(references, hypotheses):
    """Compute WER and CER."""
    try:
        import jiwer
    except ImportError:
        print("Error: 'jiwer' package required.  pip install jiwer",
              file=sys.stderr)
        sys.exit(1)

    wer = jiwer.wer(references, hypotheses)
    cer = jiwer.cer(references, hypotheses)
    return wer, cer


def main():
    p = argparse.ArgumentParser(
        description="Evaluate audio transcription quality (WER/CER)",
    )
    p.add_argument("--endpoint", required=True, help="vLLM server URL")
    p.add_argument("--output-dir", required=True, help="Directory for quality-results.json")
    p.add_argument("--model", default="openai/whisper-small", help="Model name")
    p.add_argument("--num-clips", type=int, default=50)
    p.add_argument("--dataset", default="openslr/librispeech_asr")
    p.add_argument("--dataset-config", default="clean")
    p.add_argument("--dataset-split", default="test")
    p.add_argument("--audio-column", default="audio")
    p.add_argument("--audio-dir", default=None,
                   help="Local dir with audio files + references.json")
    p.add_argument("--audio-format", default="mp3",
                   help="Audio format for local files (HF path always uploads WAV)")
    p.add_argument("--test-run-id", default=None,
                   help="Test run ID to embed in quality-results.json")
    p.add_argument("--cores", type=int, default=None,
                   help="Core count to embed in quality-results.json")

    args = p.parse_args()

    if args.audio_dir:
        clips = _load_local_clips(args.audio_dir)
    else:
        clips = _load_hf_dataset(
            args.dataset, args.dataset_config, args.dataset_split,
            args.audio_column, args.num_clips,
        )

    if not clips:
        print("No clips loaded.", file=sys.stderr)
        return 1

    print(f"Evaluating {len(clips)} clips against {args.endpoint} ...")

    per_clip = []
    references = []
    hypotheses = []

    for i, clip in enumerate(clips):
        audio_bytes, ext = _encode_audio(clip, args.audio_format)
        try:
            hypothesis = _transcribe(args.endpoint, audio_bytes, ext, args.model)
        except Exception as e:
            print(f"  clip {i}: FAILED ({e})")
            continue

        ref = clip["reference"]
        references.append(ref)
        hypotheses.append(hypothesis)

        try:
            import jiwer
            clip_wer = jiwer.wer(ref, hypothesis) if ref else None
            clip_cer = jiwer.cer(ref, hypothesis) if ref else None
        except ImportError:
            clip_wer = clip_cer = None

        per_clip.append({
            "clip_id": clip.get("clip_id", f"clip-{i}"),
            "reference": ref,
            "hypothesis": hypothesis,
            "wer": clip_wer,
            "cer": clip_cer,
        })

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(clips)} done")

    if not references:
        print("No successful transcriptions.", file=sys.stderr)
        return 1

    wer, cer = _compute_metrics(references, hypotheses)
    print(f"\nResults: WER={wer * 100:.1f}%, CER={cer * 100:.1f}% "
          f"(n={len(references)})")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "wer": wer,
        "cer": cer,
        "num_clips": len(clips),
        "num_successful": len(references),
        "model": args.model,
        "dataset": args.dataset,
        "dataset_config": args.dataset_config,
        "audio_format": args.audio_format,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "per_clip": per_clip,
    }
    if args.test_run_id:
        result["test_run_id"] = args.test_run_id
    if args.cores is not None:
        result["cores"] = args.cores

    out_path = output_dir / "quality-results.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
