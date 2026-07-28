# Collabuild MAS — User Manual

**Version:** 1.0.0
**Author:** [Sai Karun Nandipati](https://karun99.github.io)

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [Using the Chat Interface](#4-using-the-chat-interface)
5. [Configuring Providers](#5-configuring-providers)
6. [Using the Pipeline](#6-using-the-pipeline)
7. [Research Tools](#7-research-tools)
8. [Command-Line Interface](#8-command-line-interface)
9. [Docker Deployment](#9-docker-deployment)
10. [Troubleshooting](#10-troubleshooting)
11. [FAQ](#11-faq)
12. [Keyboard Shortcuts](#12-keyboard-shortcuts)

---

## 1. Getting Started

Collabuild MAS is a Multi-Agent System that lets you:

- **Chat with AI models** running locally (Ollama, KoboldCPP) or via cloud APIs (OpenRouter, NVIDIA, Claude)
- **Run a 9-stage pipeline** that transforms research papers into production-ready software
- **Use research tools** including OCR, web content extraction, and autonomous research agents

### What You Need

- Python 3.10 or higher
- An API key for one cloud provider, OR a local LLM server running (Ollama/KoboldCPP)
- A modern web browser (Chrome, Firefox, Edge, Safari)

---

## 2. Installation

### Option A: Install from PyPI (Recommended)

```bash
pip install collabuild-mas[web]
```

### Option B: Install from Source

```bash
git clone https://github.com/collabuild-mas/collabuild-mas.git
cd collabuild-mas
pip install -e ".[web]"
```

### Option C: Install with Docker

```bash
git clone https://github.com/collabuild-mas/collabuild-mas.git
cd collabuild-mas
docker compose up -d
```

### Verify Installation

```bash
collabuild --version
# Should print: collabuild v1.0.0
```

---

## 3. Quick Start

### Start the Web UI

```bash
collabuild web
```

Open your browser and go to: **http://127.0.0.1:8080**

### Start with Dev Mode (No API Key Needed)

```bash
collabuild web --dev
```

This uses the DevProvider for offline testing. You can chat and run the pipeline without any API key.

### First Chat

1. Open the web UI
2. Select a provider in the sidebar (e.g., "openrouter")
3. Enter your API key in the settings
4. Select a model from the dropdown
5. Type a message and press Enter

---

## 4. Using the Chat Interface

### Layout

The chat interface has three main areas:

```
┌─────────────────────────────────────────────────┐
│  Top Bar: Provider badge, Model name, Actions   │
├──────────┬──────────────────────────────────────┤
│ Sidebar  │  Chat Messages                       │
│          │  ┌──────────────────────────────┐   │
│ Provider │  │  User: Hello!                 │   │
│ Model    │  └──────────────────────────────┘   │
│ Params   │  ┌──────────────────────────────┐   │
│ GGUF     │  │  AI: Hello! How can I help?   │   │
│          │  └──────────────────────────────┘   │
│          │                                      │
│          │  ┌──────────────────────────────┐   │
│          │  │  Type your message...    [Send]│  │
│          │  └──────────────────────────────┘   │
└──────────┴──────────────────────────────────────┘
```

### Sending Messages

- **Type your message** in the input bar at the bottom
- **Press Enter** to send
- **Press Shift+Enter** for a newline
- **Click the Stop button** to cancel a response mid-generation

### Message Features

- **Markdown rendering** — Bold, italic, code blocks, inline code
- **Streaming** — Tokens appear one by one as the AI generates them
- **Export** — Click the Export button to download the chat as Markdown

### Sidebar Controls

| Control | Description |
|---------|-------------|
| Provider | Select your LLM provider |
| Model | Choose from available models |
| Temperature | Creativity (0.0 = deterministic, 1.0 = creative) |
| Max Tokens | Maximum response length |
| Top P | Nucleus sampling threshold |
| Top K | Top-k sampling limit |
| Repeat Penalty | Penalize repeated tokens |
| System Prompt | Instructions for the AI |

---

## 5. Configuring Providers

### Cloud Providers

#### OpenRouter (Recommended for Beginners)

1. Go to [openrouter.ai](https://openrouter.ai)
2. Create an account and get an API key
3. In the web UI, select "openrouter" as provider
4. Paste your API key in the settings
5. Select a model (free tier models are marked)

#### NVIDIA Build

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Create an account and get an API key
3. Select "nvidia" as provider
4. Enter your API key

#### Anthropic Claude

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account and get an API key
3. Select "claude" as provider
4. Enter your API key

#### Bhashini AI (Indian Languages)

1. Go to [bhashini.gov.in](https://bhashini.gov.in/ulca/user/signup)
2. Sign up and get a ULCA API key
3. Select "bhashini" as provider
4. Enter your API key
5. Supports 22+ Indian languages: Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, Urdu, Sanskrit, and more

**Features:**
- Machine translation (any Indian language ↔ English)
- Transliteration (script conversion, e.g., Devanagari → Latin)
- Text-to-Speech (TTS) in multiple Indian languages
- Language detection (auto-detect input language)
- ASR (Automatic Speech Recognition)

### Local Providers

#### Ollama (Easiest Local Setup)

1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Pull a model:
   ```bash
   ollama pull llama3.1
   ollama pull codellama
   ```
3. Start the server (usually auto-starts):
   ```bash
   ollama serve
   ```
4. In the web UI, select "ollama" — it auto-detects the server

#### KoboldCPP

1. Download from [github.com/LostRuins/koboldcpp](https://github.com/LostRuins/koboldcpp)
2. Run with a GGUF model:
   ```bash
   ./koboldcpp --model ~/models/llama-3.1-8b-instruct.Q4_K_M.gguf --port 5001
   ```
3. Select "koboldcpp" in the web UI

#### text-generation-webui (oobabooga)

1. Install from [github.com/oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)
2. Start with API enabled:
   ```bash
   python server.py --api --listen --port 5000
   ```
3. Select "textgen" in the web UI

### Custom Provider

For any OpenAI-compatible endpoint (vLLM, llama.cpp, LocalAI, LM Studio):

1. Select "custom" as provider
2. Enter the endpoint URL (e.g., `http://localhost:8080/v1`)
3. Enter an API key if required

---

## 6. Using the Pipeline

The 9-stage pipeline transforms a research paper into a production-ready system.

### Access the Pipeline

Click **Pipeline** in the sidebar, or navigate to `/pipeline`.

### Run the Pipeline

1. **Enter paper text** — Paste your research paper or click "Load Sample"
2. **Select provider** — Choose which LLM to use
3. **Select model** — Pick a specific model
4. **Click "Run Pipeline"** — Watch the progress bar

### Pipeline Stages

| # | Stage | What It Does |
|---|-------|-------------|
| 1 | Paper Analysis | Extracts methodology, algorithms, architecture |
| 2 | SRS Generation | Creates IEEE 830 requirements specification |
| 3 | Module Design | Designs module architecture with interfaces |
| 4 | User Flow | Creates UX flows with sequence diagrams |
| 5 | SDLC Plan | Generates sprint breakdown and timeline |
| 6 | Code Generation | Produces production-ready implementation |
| 7 | Debug & Review | Identifies bugs, security issues, performance problems |
| 8 | Deployment Plan | Designs infrastructure and CI/CD pipeline |
| 9 | Final Review | QA validation of all outputs |

### View Results

- **Progress bar** shows current stage and percentage
- **Stage-by-stage results** appear as they complete
- **Mermaid diagrams** render inline (flowcharts, sequence diagrams, Gantt charts)
- **Full report** can be downloaded as Markdown

### Dev Mode Pipeline

Run the pipeline offline without any API key:

```bash
collabuild --dev
# Or in the web UI: click "Run Pipeline" with provider set to "dev"
```

This returns structured mock responses for each stage, useful for:
- Testing the pipeline UI
- Verifying Mermaid diagram rendering
- CI/CD pipeline validation

---

## 7. Research Tools

Access research tools at `/tools` or click **Tools** in the sidebar.

### OCR (Document Parsing)

1. Enter the file path of your document
2. Select mode:
   - **Document** — Full document parsing (PDF, DOC, images → Markdown)
   - **Image** — General OCR on a single image
3. Click "Run OCR"
4. View the extracted text

**Supported formats:** PDF, DOC, DOCX, PPT, JPG, PNG, BMP, TIFF

**Note:** Requires Baidu OCR API keys. Set `BAIDU_OCR_API_KEY` and `BAIDU_OCR_SECRET_KEY` in your environment.

### Web Fetcher

1. Enter a URL
2. Click "Fetch"
3. View the extracted text content

**Features:**
- Extracts clean text from any webpage
- Handles PDFs (detects and reports)
- Caches results for repeated fetches
- No external dependencies (stdlib-only)

### Agent Runner

1. Enter a research task (e.g., "Find information about Unlimited-OCR paper")
2. Click "Run Agent"
3. Watch the agent's reasoning steps
4. View the final answer

**Available Tools:**
- `web_fetch` — Fetch and extract text from URLs
- `ocr_file` — OCR a document file
- `ocr_image` — OCR an image file
- `python_exec` — Execute Python code in a sandbox
- `search` — Web search (placeholder)
- **OCR AgentRunner** — `create_ocr_agent_runner()` factory wires BaiduOCR into the agent for autonomous OCR workflows
- **DocumentAnalyzer** — AgentRunner-powered analysis of parsed document content
- **QualityChecker** — AgentRunner-based automated QA for OCR outputs

---

## 8. Command-Line Interface

### Web UI Commands

```bash
collabuild web                          # Start web UI on http://127.0.0.1:8080
collabuild web --port 3000              # Custom port
collabuild web --host 0.0.0.0           # Bind all interfaces
collabuild web --reload                 # Auto-reload on code changes
collabuild web --dev                    # Dev mode (offline)
```

### Pipeline Commands

```bash
# Run pipeline with a specific provider
collabuild --provider ollama --model llama3.1

# Run with custom paper
collabuild --paper "Your paper text here..."

# Run with paper from file
collabuild --paper-file paper.txt

# Custom output file
collabuild --output my_report.md

# Dev mode (offline, no API key)
collabuild --dev

# With custom config
collabuild --config /path/to/config.yaml
```

### All CLI Flags

| Flag | Description |
|------|-------------|
| `--provider` | LLM provider (openrouter, nvidia, claude, ollama, koboldcpp, textgen, bhashini, dev) |
| `--model` | Model name |
| `--api-key` | API key |
| `--endpoint` | Provider endpoint URL |
| `--paper` | Research paper text |
| `--paper-file` | Path to paper text file |
| `--output` | Output report file (default: pipeline_report.md) |
| `--config` | Path to config.yaml |
| `--dev` | Enable dev mode (offline, no API key) |

---

## 9. Docker Deployment

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/collabuild-mas/collabuild-mas.git
cd collabuild-mas

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env

# Start with docker-compose
docker compose up -d

# View logs
docker compose logs -f collabuild
```

### Docker Compose Configuration

The `docker-compose.yml` includes:
- Collabuild MAS service on port 8080
- GPU support (NVIDIA)
- Persistent settings volume
- Environment variable pass-through

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `NVIDIA_API_KEY` | NVIDIA Build API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `BAIDU_OCR_API_KEY` | Baidu OCR API key |
| `BAIDU_OCR_SECRET_KEY` | Baidu OCR secret key |
| `BHASHINI_API_KEY` | Bhashini AI API key |

### Custom Docker Build

```bash
# Build the image
docker build -t collabuild-mas .

# Run with GPU support
docker run --gpus all -p 8080:8080 \
  -e OPENROUTER_API_KEY=sk-or-... \
  collabuild-mas

# Run in dev mode
docker run -p 8080:8080 -e COLLABUILD_DEV_MODE=1 collabuild-mas
```

---

## 10. Troubleshooting

### Common Issues

#### "Web dependencies not installed"

```bash
pip install -e ".[web]"
```

#### "No provider configured"

Set an API key in the web UI Settings page, or use dev mode:

```bash
collabuild web --dev
```

#### "Provider is offline"

For local providers (Ollama, KoboldCPP), make sure the server is running:

```bash
# Ollama
ollama serve

# KoboldCPP
./koboldcpp --model your-model.gguf --port 5001
```

#### Pipeline stages show "Error: ..."

This means the LLM provider is unreachable. Solutions:
1. Check your API key is valid
2. Check your internet connection
3. For local providers, verify the server is running
4. Use `--dev` for offline testing

#### Port already in use

```bash
collabuild web --port 3000
```

#### Docker GPU not available

Ensure NVIDIA Container Toolkit is installed:

```bash
# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Logging

Enable debug logging:

```bash
COLLABUILD_LOG=DEBUG collabuild web
```

### Reset Settings

Delete the settings file:

```bash
rm collabuild/web/settings.json
```

---

## 11. FAQ

**Q: Do I need an API key to use Collabuild MAS?**

A: Not for dev mode. Run `collabuild web --dev` to use the DevProvider for offline testing. For real AI responses, you need an API key for at least one cloud provider, or a local LLM server running.

**Q: Which provider should I start with?**

A: OpenRouter has a free tier with many models. It's the easiest way to get started without paying anything.

**Q: Can I use multiple providers at once?**

A: Yes. Each chat session can use a different provider. The pipeline also lets you select a provider before running.

**Q: How do I add my own GGUF models?**

A: Place `.gguf` files in one of the scanned directories (`~/models`, `~/Downloads`, etc.) and they'll appear in the sidebar under "Local Models".

**Q: Is my data sent to external servers?**

A: Only when using cloud providers (OpenRouter, NVIDIA, Claude). Local providers (Ollama, KoboldCPP) keep all data on your machine.

**Q: Can I run the pipeline without the web UI?**

A: Yes. Use the CLI: `collabuild --provider ollama --model llama3.1 --paper-file paper.txt`

**Q: How do I update Collabuild MAS?**

A: `pip install --upgrade collabuild-mas[web]`

**Q: Does it work on Windows/Mac?**

A: Yes. Collabuild MAS is pure Python and works on any OS with Python 3.10+.

---

## 12. Keyboard Shortcuts

### Chat Interface

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line in input |
| Escape | Stop generation |

### Navigation

| Shortcut | Action |
|----------|--------|
| `/` | Go to Chat |
| `/settings` | Go to Settings |
| `/pipeline` | Go to Pipeline |
| `/tools` | Go to Tools |

---

## Support

- **Issues:** [https://github.com/collabuild-mas/collabuild-mas/issues](https://github.com/collabuild-mas/collabuild-mas/issues)
- **Author:** [Sai Karun Nandipati](https://karun99.github.io)
- **Repository:** [https://github.com/collabuild-mas/collabuild-mas](https://github.com/collabuild-mas/collabuild-mas)
