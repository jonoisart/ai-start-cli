# ROADMAP

---

## Phase 1: Core Improvements (Ready to Build Now)

### 1.4 Local Model Discovery (Auto-Import)
**Goal:** Scan filesystem for existing GGUF files and offer to add them to registry.

```bash
ai scan                              # Scan common locations
ai scan ~/Downloads --depth 3        # Scan specific path
ai scan --auto                       # Non-interactive, add all found
```

**Interactive Flow:**
```bash
$ ai scan
Scanning for GGUF models...
Found 3 models not in registry:

1) /Users/<username>/Downloads/mistral-7b-v0.1.Q4_K_M.gguf
   Size: 4.1GB | Quant: Q4_K_M | Parameters: ~7B
   Add to registry? [Y/n]: y
   Nickname [mistral-7b]: mistral
   Context size [4096]: 32768
   ✅ Added 'mistral'

2) /Volumes/External/llama-13b.Q5_K_M.gguf
   Size: 8.9GB | Quant: Q5_K_M | Parameters: ~13B
   Add to registry? [Y/n]: y
   Nickname [llama-13b]: llama13
   ✅ Added 'llama13'

Found 2 models in registry (skipped):
  - qwen @ ~/.cache/huggingface/.../Qwen3.5...

Run 'ai list' to see all models
```

**Scan Locations (configurable):**
- `~/.cache/huggingface/hub/`
- `~/.cache/llama.cpp/`
- `~/Downloads/`
- External drives (mounted volumes)
- Common paths from `ollama`, `lm-studio`, `koboldcpp` if detected

**Metadata Extraction:**
- Parse GGUF headers to auto-detect:
  - Architecture (Llama, Qwen, Mistral, etc.)
  - Quantization level
  - Context length
  - Parameter count
- Use `mdls` (macOS) or `file` (Linux) for creation dates

---

## Phase 2: Installation & Onboarding

### 2.4 First-Time Onboarding Wizard
**Goal:** Run on first execution to configure the environment.

```bash
ai init          # Manual trigger
ai doctor        # Check setup health
```

**Onboarding Flow:**

```bash
$ ai
It looks like this is your first time running ai-launcher.

┌─────────────────────────────────────────┐
│  🤖 AI Launcher Setup Wizard           │
└─────────────────────────────────────────┘

1) 🔍 Model Discovery
   Scan your computer for existing AI models?
   This will search ~/.cache, ~/Downloads, and external drives.
   [Y/n]: y

   Found 4 models:
   - Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf
   - Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf
   - gemma-4-E4B-it-Q8_0.gguf
   - mistral-7b-instruct-v0.2.Q4_K_M.gguf
   
   Add these to your registry with nicknames? [Y/n]: y
   
   Qwen3.5-9B... → Nickname [qwen]: qwen-uncensored
   Gemma-4-E4B... → Nickname [gemma]: gemma-uncensored
   gemma-4-E4B-it... → Nickname [gemma-base]: 
   mistral-7b... → Nickname [mistral]: 

2) 🔧 llama.cpp Setup
   llama-server not found in PATH.
   
   Install method:
   a) Homebrew (brew install llama.cpp) [Recommended]
   b) Build from source (git clone + make)
   c) Download pre-built binary (auto-detect arch)
   d) Specify custom path
   
   Choice [a]: a
   → Checking Homebrew... ✓
   → Installing llama.cpp... (this may take a while)
   
   Or if already installed:
   Path to llama-server [/opt/homebrew/bin/llama-server]: 

3) 📁 Permissions & Locations
   
   Config directory [~/.config/ai]: 
   Models directory [~/.local/share/ai/models]: 
   Logs directory [~/.local/share/ai/logs]: 
   
   Allow ai-launcher to manage these directories? [Y/n]: y
   → Creating directories... ✓

4) 🚀 Quick Test
   Start a test server with 'qwen' to verify everything works?
   [Y/n]: y
   → Starting server on port 8083... ✓
   → Health check passed! ✓
   
   Setup complete! Try: ai run qwen

   Next steps:
   - ai install <model>    # Download new models
   - ai list               # See all your models
   - ai help               # Full command reference
```

**Post-Install Modes:**
```bash
ai init --minimal        # Skip scans, just set paths
ai init --docker         # Configure for Docker-based llama.cpp
ai init --rocm           # Auto-detect AMD GPU, configure ROCm
ai init --cuda           # Auto-detect NVIDIA GPU, configure CUDA
```

---

### 2.5 Self-Installer Script
**Goal:** One-liner install that handles the onboarding.

```bash
# Options to present during curl | sh:
curl -fsSL https://ai-launcher.dev/install.sh | sh -s -- --method=homebrew
curl -fsSL https://ai-launcher.dev/install.sh | sh -s -- --method=static
curl -fsSL https://ai-launcher.dev/install.sh | sh -s -- --method=source
```

**Installation Methods:**

| Method | Pros | Cons | When to Use |
|--------|------|------|-------------|
| **Homebrew** | Easy updates, managed deps | macOS/Linux only, not bleeding edge | Most users |
| **Static Binary** | Single file, no deps | Larger size, manual updates | CI/CD, servers |
| **Build Source** | Latest features, optimized | Requires build tools | Power users |
| **npm (global)** | Cross-platform, easy uninstall | Node dependency | JS developers |
| **Cargo** | Fast, Rust ecosystem | Rust toolchain needed | Rust developers |

**Install Script Features:**
- Detect OS/arch (macOS ARM/x86, Linux ARM/x86)
- Check for existing llama.cpp installations
- Offer to migrate from Ollama, LM Studio, or koboldcpp
- Set up shell completions automatically
- Add `~/bin` to PATH if missing

---

## Updated Phase 4: Distribution

### 4.2 Installation Channels
```bash
# Homebrew (macOS/Linux)
brew tap ai-launcher/tap
brew install ai-launcher

# npm (cross-platform)
npm install -g ai-launcher

# Cargo (Rust users)
cargo install ai-launcher

# Static binary
curl -fsSL https://github.com/user/ai-launcher/releases/latest/download/ai-$(uname)-$(uname -m) -o ~/bin/ai
chmod +x ~/bin/ai
```

### 4.3 Migration Assistant
```bash
ai migrate from-ollama       # Import Ollama models
ai migrate from-lmstudio     # Import LM Studio models
ai migrate --dry-run         # Preview what would be imported
```

---

## Immediate Implementation Order

1. **Local Model Discovery** (`ai scan`) - High value, uses existing infra
2. **Config extraction** - Prerequisite for onboarding
3. **Onboarding wizard** (`ai init`) - First-run experience
4. **Install command** (`ai install`) - Growth feature

