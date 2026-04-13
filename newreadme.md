# README.md

---

# 🤖 AI Launcher

> The missing package manager for local LLMs. Stop memorizing paths and fighting with flags—just `ai start qwen` or `ai start gemma` etc.

AI Launcher is a command-line tool that turns your scattered GGUF models into a manageable, launchable collection. No GUI bloat, no Docker required, no internet needed after setup.

---

## ✨ Current Features 

**Zero-config model launching**
```bash
ai start qwen                    # Start your model
ai start gemma 4096 8084        # Custom context + port
```

**Smart registry** - Knows where your models live so you don't have to type `/Users/onoi/.cache/huggingface/hub/models--HauhauCS--...` ever again.

**Offline-first** - Once cached, runs without internet. No phone-home, no update checks.

**Process management**
```bash
ai start qwen      # Background mode
ai stop            # Kill server
ai ps              # See what's running
ai logs            # Tail logs
```

**Quick introspection**
```bash
ai list            # All available models
ai path qwen       # Where is this file?
ai status          # Health check
```

---

## 🚀 Quick Start

```bash
# Install
curl -fsSL https://ai-launcher.dev/install.sh | sh

# Or manually
git clone https://github.com/yourname/ai-launcher.git
cd ai-launcher
make install  # Symlinks to ~/bin/ai

# First run (optional wizard)
ai init

# Add your existing models
ai scan ~/Downloads
ai scan ~/.cache/huggingface/hub

# Launch
ai start qwen
```

---

## 📋 Commands

| Command | Description | Status |
|---------|-------------|--------|
| `ai start <model> [ctx] [port]` | Start server (foreground) | ✅ |
| `ai start <model>` | Start server (background) | ✅ |
| `ai stop [port]` | Stop server | ✅ |
| `ai ps` | List running servers | ✅ |
| `ai logs [model]` | View/tail logs | ✅ |
| `ai list` | Show registered models | ✅ |
| `ai path <model>` | Show model file path | ✅ |
| `ai scan [path]` | Auto-discover GGUF files | 🚧 |
| `ai install <repo>` | Download from HuggingFace | 🚧 |
| `ai init` | Setup wizard | 🚧 |

---

## 🗺️ Roadmap

### Phase 1: Core Infrastructure
*Making the tool reliable and configurable*

- [ ] **Configuration system** (`~/.config/ai/config.yaml`)
  - Custom default ports/context sizes
  - User-defined model directories
  - Profile presets (coding, creative, etc.)
  
- [ ] **JSON Registry** (`~/.config/ai/registry.json`)
  - Metadata extraction from GGUF headers
  - Favorites system
  - Model tags/aliases
  
- [ ] **Background daemon mode**
  - PID management
  - Log rotation
  - Auto-restart on crash

- [ ] **Local model discovery** (`ai scan`)
  - Parse GGUF metadata (arch, quant, params)
  - Search common cache locations (HF, ollama, lm-studio)
  - Interactive nickname assignment
  - Duplicate detection

### Phase 2: Package Management
*Turning it into a real package manager for models*

- [ ] **Install command** (`ai install`)
  - HuggingFace repo integration
  - Quantization selection (interactive picker)
  - Resume failed downloads
  - Verify checksums
  
- [ ] **Search & discovery**
  - `ai search <query>` (HF hub search)
  - `ai trending` (cached popular models)
  - Filter by architecture, size, license
  
- [ ] **Update management**
  - Check for newer quantizations
  - `ai update --all` (batch updates)
  - Disk space management (prune old versions)

### Phase 3: Developer Experience
*Making it feel like a native part of the OS*

- [ ] **Onboarding wizard** (`ai init`)
  - Permission handling (scan locations)
  - llama.cpp auto-installation (Homebrew/source/static)
  - Shell completion setup (zsh/bash/fish)
  - First-run model import
  
- [ ] **Multiple installation methods**
  - Homebrew: `brew install ai-launcher`
  - npm: `npm install -g ai-launcher`
  - Cargo: `cargo install ai-launcher`
  - Static binary for CI/CD
  
- [ ] **Migration assistants**
  - Import from Ollama
  - Import from LM Studio
  - Import from KoboldCPP

### Phase 4: Power User Features
*For people living in the terminal*

- [ ] **TUI mode** (`ai tui`)
  - Interactive model browser (like lazygit)
  - Real-time GPU/RAM usage
  - Keyboard-driven workflow
  
- [ ] **Chat interface** (`ai chat`)
  - REPL mode with history
  - One-shot prompts: `ai chat qwen "Explain quantum computing"`
  - Context file injection: `ai chat qwen -f code.py`
  
- [ ] **Model router**
  - Load multiple models, route by request
  - Auto-load/unload based on usage
  - Load balancing between GPU/CPU

### Phase 5: Ecosystem
*Becoming a platform*

- [ ] **Plugin system**
  - Custom backends (vLLM, tabbyAPI, etc.)
  - Pre/post-processing hooks
  
- [ ] **Remote models**
  - SSH tunnel support
  - `ai remote add server-url`
  
- [ ] **Model versioning**
  - Pin specific GGUF revisions
  - A/B testing different quants

---

## 🏗️ Architecture Philosophy

**Unix-native**: Works with pipes, returns proper exit codes, respects `$XDG_CONFIG_HOME`.

**Offline-first**: No analytics, no required API keys, no phone-home on startup.

**Cache-agnostic**: Doesn't care if you use HuggingFace, civitai, or manually downloaded files. If it's a GGUF, it works.

**Shell-first, TUI-second**: The CLI is the API. The TUI is a convenience layer, not a requirement.

---

## 🛠️ Development

```bash
git clone https://github.com/yourname/ai-launcher.git
cd ai-launcher

# Run tests
make test

# Install locally
make install PREFIX=~/bin

# Uninstall
make uninstall
```

### Project Structure
```
ai-launcher/
├── bin/ai                    # Main executable
├── lib/
│   ├── scanner.sh            # GGUF discovery logic
│   ├── registry.sh           # JSON registry management
│   └── installer.sh          # HF download logic
├── config/
│   ├── config.yaml.example
│   └── completions/
│       ├── ai.zsh
│       └── ai.bash
└── README.md
```

---

## 🤝 Contributing

PRs welcome! Priority areas:
1. **Bash compatibility** (currently zsh-optimized)
2. **GGUF metadata parsing** (pure shell or minimal dependencies)
3. **Windows support** (Git Bash/WSL)

See [CONTRIBUTING.md](CONTRIBUTING.md) for style guide.

---

## 📜 License

MIT - Do whatever you want. If you make money with it, consider sponsoring the project.

---

**Built with frustration and love for local AI.** No GPUs were rented in the making of this tool.
