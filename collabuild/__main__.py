#!/usr/bin/env python3
"""
Collabuild MAS — Research Paper → Production Pipeline
CLI entry point: `python -m collabuild` or `collabuild` (after pip install).

Usage:
  collabuild                                    # OpenRouter free tier
  collabuild --dev                              # Offline dev mode (no API key needed)
  collabuild --provider ollama                  # local Llama via Ollama
  collabuild --provider koboldcpp --model l3.1  # local via KoboldCPP
  collabuild --provider textgen                 # local via text-generation-webui
  collabuild --paper "My paper text..."         # custom paper
  collabuild --paper-file paper.txt             # read from file
  collabuild --output report.md                 # custom output path
  collabuild web                                # launch web UI
  collabuild web --dev                          # web UI with dev fallback
"""
import os, sys, argparse, logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

from .pipeline import CollabuildPipeline
from . import config as cfgmod

def start_web(args):
    """Start the Collabuild Web UI server."""
    try:
        import uvicorn
    except ImportError:
        print("Web dependencies not installed. Run: pip install collabuild-mas[web]")
        sys.exit(1)
    host = args.host or "127.0.0.1"
    port = int(args.port or 8080)
    if getattr(args, "dev", False):
        os.environ["COLLABUILD_DEV_MODE"] = "1"
        print("[DEV] Offline mode enabled — using DevProvider (no API key required)")
    print(f"Collabuild Web UI: http://{host}:{port}")
    print("   Press Ctrl+C to stop.")
    uvicorn.run("collabuild.web.app:app", host=host, port=port, reload=args.reload)

SAMPLE_PAPER = """Unlimited OCR Works: Welcome the Era of One-shot Long-horizon Parsing

Authors: Youyang Yin, Huanhuan Liu, et al. — Baidu Inc.

Abstract: This paper introduces Unlimited-OCR, a novel approach to document parsing that
handles long-form documents in a single forward pass. Unlike traditional OCR systems that
process pages sequentially or chunk documents, Unlimited-OCR uses a vision-language model
with a 32K context window to parse entire documents end-to-end. The model supports two
inference modes: 'gundam' (base_size=1024, image_size=640, crop_mode=True) for detailed
single-page parsing, and 'base' (base_size=1024, image_size=1024, crop_mode=False) for
multi-page documents. Key innovations include: (1) a no-repeat n-gram constraint to prevent
hallucinated repetitions in long outputs, (2) adaptive cropping that preserves document
structure across page boundaries, and (3) a custom logit processor for controlled generation.
The model achieves state-of-the-art results on document parsing benchmarks, reducing
character error rate by 40% compared to prior methods while maintaining throughput.
It supports multiple inference backends: HuggingFace Transformers, vLLM, and SGLang,
making it suitable for both research and production deployments. The model is released
open-source under MIT license on HuggingFace and ModelScope.

Methodology:
The system architecture includes: (1) A Vision Encoder based on ViT-L/14 that processes
document images at variable resolutions, (2) A Language Decoder based on Qwen2.5-7B that
generates structured text output, (3) An adaptive cropping module that handles documents of
arbitrary length by splitting into overlapping tiles, (4) A no-repeat n-gram processor that
tracks generated tokens across the full context window to prevent repetition.

The training pipeline uses a two-stage approach: (1) Pre-training on synthetic document data
generated from PDF-to-image pipelines with ground-truth text, (2) Fine-tuning on curated
real-world documents spanning invoices, receipts, academic papers, forms, and books."""

def main():
    # Check for subcommand
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        wparser = argparse.ArgumentParser(description="Collabuild Web UI")
        wparser.add_argument("--host", type=str, default="127.0.0.1", help="Bind address")
        wparser.add_argument("--port", type=str, default="8080", help="Port number")
        wparser.add_argument("--reload", action="store_true", help="Auto-reload on file changes")
        wparser.add_argument("--dev", action="store_true", help="Dev mode: use DevProvider (offline, no API key)")
        start_web(wparser.parse_args(sys.argv[2:]))
        return

    parser = argparse.ArgumentParser(description="Collabuild MAS Pipeline")
    parser.add_argument("--paper", type=str, default="", help="Research paper text")
    parser.add_argument("--paper-file", type=str, default="", help="Path to paper txt file")
    parser.add_argument("--provider", type=str, default="", choices=["", "openrouter", "nvidia", "ollama", "koboldcpp", "textgen", "claude", "dev"],
                        help="LLM provider to use (default: from config.yaml or openrouter)")
    parser.add_argument("--dev", action="store_true", help="Dev mode: use DevProvider (offline, no API key needed)")
    parser.add_argument("--model", type=str, default="", help="Model name (provider-dependent)")
    parser.add_argument("--api-key", type=str, default="", help="API key (for openrouter/nvidia/claude)")
    parser.add_argument("--endpoint", type=str, default="", help="Provider endpoint URL")
    parser.add_argument("--config", type=str, default="", help="Path to config.yaml")
    parser.add_argument("--output", type=str, default="pipeline_report.md", help="Output report file")
    args = parser.parse_args()

    # Dev mode override
    if args.dev:
        args.provider = "dev"
        print("[DEV] Offline mode — using DevProvider (no API key required)")
        print("[DEV] Responses are structured mock outputs for pipeline verification")

    # Load paper
    paper = args.paper
    if args.paper_file and os.path.exists(args.paper_file):
        with open(args.paper_file, "r", encoding="utf-8") as f:
            paper = f.read()
    if not paper:
        paper = SAMPLE_PAPER
        print("Using sample paper (Unlimited-OCR). Use --paper or --paper-file for custom input.")

    # Build pipeline using new get_ai_config helper
    try:
        cfg = cfgmod.load(args.config)
        ai_cfg = cfgmod.get_ai_config(cfg)
    except Exception:
        ai_cfg = {"provider": args.provider or "openrouter"}

    # CLI overrides
    if args.provider:
        ai_cfg["provider"] = args.provider
    if args.api_key:
        ai_cfg["api_key"] = args.api_key
    if args.endpoint:
        ai_cfg["endpoint"] = args.endpoint
    if args.model:
        ai_cfg["model"] = args.model

    pipeline = CollabuildPipeline.from_config_dict(ai_cfg)

    # Run
    results = pipeline.run(paper)

    # Save report
    report = pipeline.report()
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to {args.output}")

    # Summary
    print("\n" + "=" * 60)
    print("Generated Mermaid Diagrams:")
    print("=" * 60)
    for name, r in results.items():
        if r.mermaid:
            print(f"\n  [{r.stage}] ({len(r.mermaid)} chars)")
            print(f"  {r.mermaid[:120].split(chr(10))[0]}...")

    print("\n" + "=" * 60)
    print("Pipeline stages complete:")
    for name, r in results.items():
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.stage}")

if __name__ == "__main__":
    main()
