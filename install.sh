#!/bin/bash
set -euo pipefail

# ArmorIQ Installer for OpenClaw
# Usage: curl -fsSL https://armoriq.ai/install-armoriq.sh | bash

# If the shell was started in a directory that has since been removed, git/pnpm
# fail early with "Unable to read current working directory". Move to $HOME
# (or / as a last resort) before running any child process.
if ! pwd -P >/dev/null 2>&1; then
  cd "${HOME:-/}" 2>/dev/null || cd /
fi

R='\033[1;31m'
DR='\033[0;31m'
W='\033[1;97m'
D='\033[0;90m'
G='\033[32m'
N='\033[0m'
CYAN='\033[38;2;0;229;204m'
AMBER='\033[38;2;255;176;32m'
MUTED='\033[38;2;90;100;128m'
BOLD='\033[1m'

GUM=""
GUM_VERSION="0.17.0"
TMPFILES=()

TAGLINES=(
  "Your AI agents called. They want guardrails."
  "Because 'trust me bro' is not a security policy."
  "We armor the IQ so the AI doesn't go AWOL."
  "Zero-trust for agents. Zero chill for threats."
  "If your agent can delete prod, you need ArmorIQ."
  "Like a bouncer for your AI, but smarter."
  "Drift happens. We catch it before it ships."
  "Your policy engine called. It's lonely without you."
  "Agents move fast. ArmorIQ moves faster."
  "Sleep better knowing your agents can't go rogue."
  "Intent verified. Risk mitigated. Coffee earned."
  "Making 'AI safety' more than a buzzword since 2025."
  "Your compliance team will finally sleep at night."
  "Ctrl+Z for AI decisions you didn't authorize."
  "Because every good agent deserves a handler."
  "Policy enforcement at the speed of inference."
  "We read the agent's intent so you don't have to."
  "The guardrail your AI didn't know it needed."
  "Security that scales with your ambition."
  "Armor up. Ship out. Stay safe."
)

VALENTINE_TAGLINES=(
  "Guard your agents like you guard your heart."
  "Roses are red, policies are tight, ArmorIQ keeps your agents right."
  "Your agents love you. ArmorIQ makes sure they show it safely."
)

COMPLETION_MESSAGES=(
  "Locked and loaded. Your agents just got armored."
  "All set. Go build something wild, we'll keep it safe."
  "ArmorIQ is watching. In a good way. Not creepy."
  "Policy engine primed. Time to let the agents loose."
  "Your AI just got a security clearance upgrade."
  "Setup complete. Your future self thanks you."
  "Hardened. Verified. Ready to roll."
  "The shield is up. Send in the agents."
  "Consider your AI officially supervised."
  "Welcome to the armored side."
)

pick_tagline() {
  local month day
  month="$(date +%m)"
  day="$(date +%d)"
  if [[ "$month" == "02" && "$day" == "14" ]]; then
    echo "${VALENTINE_TAGLINES[RANDOM % ${#VALENTINE_TAGLINES[@]}]}"
    return
  fi
  echo "${TAGLINES[RANDOM % ${#TAGLINES[@]}]}"
}

pick_completion_message() {
  echo "${COMPLETION_MESSAGES[RANDOM % ${#COMPLETION_MESSAGES[@]}]}"
}

ARMORIQ_OC_VERSION=""
ARMORIQ_PLUGIN_VERSION=""
ARMORIQ_INSTALL_DIR=""
ARMORIQ_API_KEY=""
ARMORIQ_MODEL="${ARMORIQ_MODEL:-}"
ARMORIQ_OPENAI_KEY="${ARMORIQ_OPENAI_KEY:-}"
ARMORIQ_OPENROUTER_KEY="${ARMORIQ_OPENROUTER_KEY:-}"
ARMORIQ_ANTHROPIC_KEY="${ARMORIQ_ANTHROPIC_KEY:-}"
ARMORIQ_TELEGRAM_TOKEN="${ARMORIQ_TELEGRAM_TOKEN:-}"
ARMORIQ_TELEGRAM_DM_POLICY="${ARMORIQ_TELEGRAM_DM_POLICY:-open}"
ARMORIQ_TELEGRAM_STREAM_MODE="${ARMORIQ_TELEGRAM_STREAM_MODE:-partial}"
ARMORIQ_SLACK_BOT_TOKEN="${ARMORIQ_SLACK_BOT_TOKEN:-}"
ARMORIQ_GEMINI_KEY="${ARMORIQ_GEMINI_KEY:-}"
ARMORIQ_SKIP_KEY=false
ARMORIQ_NO_PROMPT=false
ARMORIQ_VERBOSE=false
ARMORIQ_DRY_RUN=false
ARMORIQ_SKIP_BUILD=false
OS="unknown"
INSTALL_STAGE_TOTAL=6
INSTALL_STAGE_CURRENT=0

cleanup_tmpfiles() {
  local f
  for f in "${TMPFILES[@]:-}"; do
    rm -rf "$f" 2>/dev/null || true
  done
}
trap cleanup_tmpfiles EXIT

mktempfile() {
  local f; f="$(mktemp)"; TMPFILES+=("$f"); echo "$f"
}


ui_info() {
  if [[ -n "$GUM" ]]; then
    "$GUM" log --level info "$*"
  else
    echo -e "${MUTED}·${N} $*"
  fi
}

ui_warn() {
  if [[ -n "$GUM" ]]; then
    "$GUM" log --level warn "$*"
  else
    echo -e "${AMBER}!${N} $*"
  fi
}

ui_success() {
  if [[ -n "$GUM" ]]; then
    local mark; mark="$("$GUM" style --foreground "#00e5cc" --bold "✓")"
    echo "${mark} $*"
  else
    echo -e "${CYAN}✓${N} $*"
  fi
}

ui_error() {
  if [[ -n "$GUM" ]]; then
    "$GUM" log --level error "$*"
  else
    echo -e "${R}✗${N} $*"
  fi
}

ui_section() {
  if [[ -n "$GUM" ]]; then
    "$GUM" style --bold --foreground "#ff4d4d" --padding "1 0" "$1"
  else
    echo ""
    echo -e "${R}${BOLD}$1${N}"
  fi
}

ui_stage() {
  INSTALL_STAGE_CURRENT=$((INSTALL_STAGE_CURRENT + 1))
  ui_section "[${INSTALL_STAGE_CURRENT}/${INSTALL_STAGE_TOTAL}] $1"
}

ui_kv() {
  local key="$1" value="$2"
  if [[ -n "$GUM" ]]; then
    local kp vp
    kp="$("$GUM" style --foreground "#5a6480" --width 22 "$key")"
    vp="$("$GUM" style --bold "$value")"
    "$GUM" join --horizontal "$kp" "$vp"
  else
    echo -e "  ${MUTED}${key}:${N} ${value}"
  fi
}

ui_panel() {
  if [[ -n "$GUM" ]]; then
    "$GUM" style --border rounded --border-foreground "#5a6480" --padding "0 1" "$1"
  else
    echo "$1"
  fi
}

ui_celebrate() {
  if [[ -n "$GUM" ]]; then
    "$GUM" style --bold --foreground "#00e5cc" "$1"
  else
    echo -e "${CYAN}${BOLD}$1${N}"
  fi
}

is_promptable() {
  [[ "$ARMORIQ_NO_PROMPT" != "true" ]] && [[ -r /dev/tty && -w /dev/tty ]]
}

run_with_spinner() {
  local title="$1"; shift
  if [[ -n "$GUM" ]] && [[ -t 2 || -t 1 ]]; then
    "$GUM" spin --spinner dot --title "$title" -- "$@"
    return $?
  fi
  "$@"
}

run_quiet_step() {
  local title="$1"; shift
  if [[ "$ARMORIQ_VERBOSE" == "true" ]]; then
    run_with_spinner "$title" "$@"
    return $?
  fi
  local log; log="$(mktempfile)"
  if [[ -n "$GUM" ]] && [[ -t 2 || -t 1 ]]; then
    local cmd_quoted="" log_quoted=""
    printf -v cmd_quoted '%q ' "$@"
    printf -v log_quoted '%q' "$log"
    if run_with_spinner "$title" bash -c "${cmd_quoted}>${log_quoted} 2>&1"; then
      return 0
    fi
  else
    if "$@" >"$log" 2>&1; then
      return 0
    fi
  fi
  ui_error "${title} failed"
  if [[ -s "$log" ]]; then
    tail -n 40 "$log" >&2 || true
  fi
  return 1
}

prompt_input() {
  local prompt_text="$1"
  local result=""
  if [[ -n "$GUM" ]] && is_promptable; then
    result="$("$GUM" input --placeholder "$prompt_text" < /dev/tty)" || true
  elif is_promptable; then
    echo -en "  ${W}${prompt_text}: ${N}" >&2
    read -r result < /dev/tty
  fi
  echo "$result"
}

prompt_confirm() {
  local prompt_text="$1"
  if [[ -n "$GUM" ]] && is_promptable; then
    "$GUM" confirm "$prompt_text" < /dev/tty
    return $?
  elif is_promptable; then
    echo -en "  ${W}${prompt_text} (y/n): ${N}" >&2
    local answer
    read -r answer < /dev/tty
    [[ "$answer" =~ ^[Yy] ]]
    return $?
  fi
  return 1
}

prompt_choice() {
  local header="$1"; shift
  if [[ -n "$GUM" ]] && is_promptable; then
    "$GUM" choose --header "$header" "$@" < /dev/tty
    return $?
  elif is_promptable; then
    echo -e "  ${W}${header}${N}" >&2
    local i=1 opt
    for opt in "$@"; do
      echo -e "    ${i}) ${opt}" >&2
      i=$((i + 1))
    done
    echo -en "  ${W}Choice: ${N}" >&2
    local choice
    read -r choice < /dev/tty
    local idx=1
    for opt in "$@"; do
      if [[ "$idx" == "$choice" ]]; then
        echo "$opt"
        return 0
      fi
      idx=$((idx + 1))
    done
    echo "$1"
    return 0
  fi
  echo "$1"
  return 0
}


gum_detect_os() {
  case "$(uname -s 2>/dev/null || true)" in
    Darwin) echo "Darwin" ;; Linux) echo "Linux" ;; *) echo "unsupported" ;;
  esac
}

gum_detect_arch() {
  case "$(uname -m 2>/dev/null || true)" in
    x86_64|amd64) echo "x86_64" ;; arm64|aarch64) echo "arm64" ;;
    i386|i686) echo "i386" ;; *) echo "unknown" ;;
  esac
}

bootstrap_gum() {
  GUM=""
  if [[ "${ARMORIQ_NO_GUM:-}" == "1" ]]; then return 1; fi
  if [[ "${TERM:-dumb}" == "dumb" ]]; then return 1; fi
  if [[ ! -t 2 && ! -t 1 ]] && [[ ! -r /dev/tty || ! -w /dev/tty ]]; then return 1; fi

  if command -v gum >/dev/null 2>&1; then
    GUM="gum"; ui_success "gum available (system)"; return 0
  fi

  local os arch asset base gum_tmpdir gum_path
  os="$(gum_detect_os)"; arch="$(gum_detect_arch)"
  [[ "$os" == "unsupported" || "$arch" == "unknown" ]] && return 1

  asset="gum_${GUM_VERSION}_${os}_${arch}.tar.gz"
  base="https://github.com/charmbracelet/gum/releases/download/v${GUM_VERSION}"
  gum_tmpdir="$(mktemp -d)"; TMPFILES+=("$gum_tmpdir")

  if command -v curl &>/dev/null; then
    curl -fsSL -o "$gum_tmpdir/$asset" "${base}/${asset}" 2>/dev/null || return 1
  elif command -v wget &>/dev/null; then
    wget -q -O "$gum_tmpdir/$asset" "${base}/${asset}" 2>/dev/null || return 1
  else
    return 1
  fi

  tar -xzf "$gum_tmpdir/$asset" -C "$gum_tmpdir" >/dev/null 2>&1 || return 1
  gum_path="$(find "$gum_tmpdir" -type f -name gum 2>/dev/null | head -n1 || true)"
  [[ -z "$gum_path" ]] && return 1
  chmod +x "$gum_path" 2>/dev/null || true
  [[ ! -x "$gum_path" ]] && return 1

  GUM="$gum_path"
  ui_success "gum bootstrapped (v${GUM_VERSION})"
  return 0
}



print_banner() {
  clear 2>/dev/null || true
  sleep 0.1
  local tagline
  tagline="$(pick_tagline)"
echo ""
echo -e "${R}    ╔════════════════════════════════════════════════════════════╗${N}"
echo -e "${R}    ║${N}                                                            ${R}║${N}"
echo -e "${R}    ║${W}     ▄▀█ █▀█ █▀▄▀█ █▀█ █▀█ █▀▀ █   ▄▀█ █ █ █                ${N}${R}║${N}"
echo -e "${R}    ║${W}     █▀█ █▀▄ █ ▀ █ █▄█ █▀▄ █▄▄ █▄▄ █▀█ ▀▄▀▄▀                ${N}${R}║${N}"
echo -e "${R}    ║${N}                                                            ${R}║${N}"
echo -e "${R}    ║${D}      AI agents are moving fast. Security isn't.            ${N}${R}║${N}"
echo -e "${R}    ║${N}                                                            ${R}║${N}"
echo -e "${R}    ║${W}      The control layer for the agent era.                  ${N}${R}║${N}"
echo -e "${R}    ║${D}      Track intent. Catch drift. Stop risk.                 ${N}${R}║${N}"
echo -e "${R}    ║${N}                                                            ${R}║${N}"
echo -e "${R}    ║${DR}                   armoriq.ai                               ${N}${R}║${N}"
echo -e "${R}    ║${N}                                                            ${R}║${N}"
echo -e "${R}    ╚════════════════════════════════════════════════════════════╝${N}"
echo ""
sleep 0.8
}

print_footer() {
  echo ""
  echo -e "${R}  ╔═════════════════════════════════════════════════════════╗${N}"
  echo -e "${R}  ║                                                         ║${N}"
  echo -e "${R}  ║${W}  ✓ Setup complete. Lock it down.                        ${R}║${N}"
  echo -e "${R}  ║                                                         ║${N}"
  echo -e "${R}  ║${D}  → Start the gateway:                                   ${R}║${N}"
  echo -e "${R}  ║                                                         ║${N}"
  echo -e "${R}  ╚═════════════════════════════════════════════════════════╝${N}"
  echo ""
  echo -e "${D}  ┌─────────────────────────────────────────────────────────┐${N}"
  echo -e "${D}  │                                                         │${N}"
  echo -e "${D}  │${W}  \$ cd ${ARMORIQ_INSTALL_DIR}                                ${D}│${N}"
  echo -e "${D}  │${W}  \$ pnpm dev gateway                                     ${D}│${N}"
  echo -e "${D}  │                                                         │${N}"
  echo -e "${D}  └─────────────────────────────────────────────────────────┘${N}"
  echo ""
  echo -e "            ${DR}◉${N} ${W}https://armoriq.ai/${N} ${DR}◉${N}  "
  echo ""
}   

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)         ARMORIQ_OC_VERSION="$2"; shift 2 ;;
      --plugin-version)  ARMORIQ_PLUGIN_VERSION="$2"; shift 2 ;;
      --install-dir)     ARMORIQ_INSTALL_DIR="$2"; shift 2 ;;
      --api-key)         ARMORIQ_API_KEY="$2"; shift 2 ;;
      --skip-key)        ARMORIQ_SKIP_KEY=true; shift ;;
      --no-prompt)       ARMORIQ_NO_PROMPT=true; shift ;;
      --verbose)         ARMORIQ_VERBOSE=true; shift ;;
      --dry-run)         ARMORIQ_DRY_RUN=true; shift ;;
      --skip-build)      ARMORIQ_SKIP_BUILD=true; shift ;;
      --no-gum)          export ARMORIQ_NO_GUM=1; shift ;;
      --help|-h)
        echo "ArmorIQ OpenClaw Installer"
        echo ""
        echo "Usage: install-armoriq.sh [options]"
        echo ""
        echo "Options:"
        echo "  --version <ver>         OpenClaw version to install (default: latest)"
        echo "  --plugin-version <ver>  ArmorClaw plugin version to install (default: latest)"
        echo "  --install-dir <dir>     Where to clone OpenClaw (default: ~/openclaw-armoriq)"
        echo "  --api-key <key>         ArmorIQ API key"
        echo "  --model <model>         LLM model (e.g. openai/gpt-5.2, google/gemini-2.5-flash)"
        echo "  --openai-key <key>      OpenAI API key"
        echo "  --openrouter-key <key>  OpenRouter API key"
        echo "  --anthropic-key <key>   Anthropic API key"
        echo "  --gemini-key <key>      Google Gemini API key"
        echo "  --telegram-token <tok>  Telegram bot token"
        echo "  --telegram-dm-policy <p> DM policy: open|pairing|allowlist (default: open)"
        echo "  --telegram-stream <m>   Stream mode: partial|block|off (default: partial)"
        echo "  --slack-bot-token <tok> Slack bot token (xoxb-...)"
        echo "  --slack-app-token <tok> Slack app token (xapp-...)"
        echo "  --skip-key              Skip API key prompt"
        echo "  --skip-build            Skip pnpm install/build (if already built)"
        echo "  --no-prompt             Non-interactive mode"
        echo "  --verbose               Show command output"
        echo "  --dry-run               Show plan without executing"
        echo "  --no-gum                Disable gum TUI"
        echo "  --help                  Show this help"
        exit 0
        ;;
      --telegram-dm-policy) ARMORIQ_TELEGRAM_DM_POLICY="$2"; shift 2 ;;
      --telegram-stream)    ARMORIQ_TELEGRAM_STREAM_MODE="$2"; shift 2 ;;
      --gemini-key)         ARMORIQ_GEMINI_KEY="$2"; shift 2 ;;
      *) ui_error "Unknown option: $1"; exit 1 ;;
    esac
  done
}


detect_os() {
  if [[ "$OSTYPE" == "darwin"* ]]; then OS="macos"
  elif [[ "$OSTYPE" == "linux-gnu"* ]] || [[ -n "${WSL_DISTRO_NAME:-}" ]]; then OS="linux"
  elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "mingw"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then OS="windows"
  else
    ui_error "Unsupported OS. Supported: macOS, Linux, Windows."
    exit 1
  fi
  ui_success "Detected: ${OS}"
}


check_command() {
  command -v "$1" &>/dev/null
}

ensure_node() {
  # openclaw requires Node >=22.14.0 — check exact major.minor to fail fast
  local required_major=22 required_minor=14
  if check_command node; then
    local node_ver node_major node_minor
    node_ver="$(node -v | sed 's/v//')"
    node_major="$(echo "$node_ver" | cut -d. -f1)"
    node_minor="$(echo "$node_ver" | cut -d. -f2)"
    if [[ "$node_major" -gt "$required_major" ]] || \
       { [[ "$node_major" -eq "$required_major" ]] && [[ "$node_minor" -ge "$required_minor" ]]; }; then
      ui_success "Node.js v${node_ver}"
      return 0
    fi
    ui_warn "Node.js v${node_ver} found but v${required_major}.${required_minor}+ required"
    ui_error "Upgrade Node: https://nodejs.org/en/download"
    ui_info "On Windows: winget upgrade OpenJS.NodeJS.LTS"
    exit 1
  fi

  if [[ "$OS" == "macos" ]] && check_command brew; then
    run_quiet_step "Installing Node.js via Homebrew" brew install node
  elif [[ "$OS" == "linux" ]]; then
    if check_command apt-get; then
      run_quiet_step "Installing Node.js" sudo apt-get install -y nodejs npm
    elif check_command yum; then
      run_quiet_step "Installing Node.js" sudo yum install -y nodejs npm
    else
      ui_error "Install Node.js v${required_major}.${required_minor}+ manually: https://nodejs.org"
      exit 1
    fi
  else
    ui_error "Install Node.js v${required_major}.${required_minor}+ manually: https://nodejs.org"
    exit 1
  fi
  ui_success "Node.js installed"
}

ensure_git() {
  if check_command git; then
    ui_success "Git $(git --version | awk '{print $3}')"
    return 0
  fi
  if [[ "$OS" == "macos" ]]; then
    run_quiet_step "Installing Git" xcode-select --install 2>/dev/null || brew install git
  elif check_command apt-get; then
    run_quiet_step "Installing Git" sudo apt-get install -y git
  else
    ui_error "Install git manually"; exit 1
  fi
  ui_success "Git installed"
}

ensure_pnpm() {
  if check_command pnpm; then
    ui_success "pnpm $(pnpm --version)"
    return 0
  fi

  ui_warn "pnpm is not installed"
  if is_promptable; then
    if ! prompt_confirm "Install pnpm globally?"; then
      ui_error "pnpm is required. Exiting."
      exit 1
    fi
  fi

  if check_command corepack; then
    run_quiet_step "Enabling pnpm via corepack" corepack enable pnpm
    if check_command pnpm; then
      ui_success "pnpm $(pnpm --version) via corepack"
      return 0
    fi
  fi

  run_quiet_step "Installing pnpm" npm install -g pnpm
  ui_success "pnpm installed"
}

# (python3 dep removed in v2026.4 — no core patching needed)


resolve_latest_version() {
  # Pinned. Plugin compatible with vanilla OpenClaw v2026.4.x; no patches.
  # Note: v2026.4.x has a strict plugin scanner — we pass
  # --dangerously-force-unsafe-install when invoking `plugins install`
  # because ArmorClaw legitimately reads env + makes HTTP calls.
  echo "2026.4.12"
}

resolve_version() {
  if [[ -z "$ARMORIQ_OC_VERSION" ]]; then
    ARMORIQ_OC_VERSION="$(resolve_latest_version)"
    if [[ -z "$ARMORIQ_OC_VERSION" ]]; then
      ui_error "Could not resolve latest OpenClaw version from npm"
      exit 1
    fi
  fi
  ui_success "Target: OpenClaw v${ARMORIQ_OC_VERSION}"
}

clone_openclaw() {
  local dir="$ARMORIQ_INSTALL_DIR"
  local git_version="$ARMORIQ_OC_VERSION"
  # npm patch releases use YYYY.M.D-N suffix; git tags don't have the -N part
  if [[ "$git_version" =~ ^[0-9]{4}\.[0-9]+\.[0-9]+-[0-9]+$ ]]; then
    git_version="${git_version%-*}"
  fi
  local tag="v${git_version}"

  if [[ -d "$dir/.git" ]]; then
    local existing_ver
    local node_pkg="${dir}/package.json"
    if [[ "$OSTYPE" == msys* ]] || [[ "$OSTYPE" == mingw* ]] || [[ "$OSTYPE" == cygwin* ]]; then
      node_pkg="$(cygpath -m "${dir}/package.json" 2>/dev/null || echo "${dir}/package.json")"
    fi
    existing_ver="$(NODE_PKG="$node_pkg" node -e 'console.log(require(process.env.NODE_PKG).version)' 2>/dev/null || echo "")"
    if [[ "$existing_ver" == "$ARMORIQ_OC_VERSION" ]]; then
      ui_success "OpenClaw v${ARMORIQ_OC_VERSION} already cloned at ${dir}"
      return 0
    fi
    ui_warn "Existing clone is v${existing_ver}, expected v${ARMORIQ_OC_VERSION}"
    if is_promptable; then
      if prompt_confirm "Remove existing clone and re-clone?"; then
        rm -rf "$dir"
      else
        ui_info "Keeping existing clone"
        return 0
      fi
    else
      ui_info "Re-cloning to match target version"
      rm -rf "$dir"
    fi
  fi

  ui_info "Cloning OpenClaw ${tag} to ${dir}"
  run_quiet_step "Cloning OpenClaw" git clone --depth 1 --branch "$tag" \
    https://github.com/openclaw/openclaw.git "$dir"
  ui_success "Cloned OpenClaw ${tag}"
}

build_openclaw() {
  if [[ "$ARMORIQ_SKIP_BUILD" == "true" ]]; then
    ui_info "Skipping build (--skip-build)"
    return 0
  fi

  local prev_dir="$PWD"
  cd "$ARMORIQ_INSTALL_DIR"

  run_quiet_step "Installing dependencies (pnpm install)" pnpm install
  ui_success "Dependencies installed"

  run_quiet_step "Building OpenClaw" pnpm build
  ui_success "Build complete"

  cd "$prev_dir"
}


install_plugin() {
  local plugin_pkg="@armoriq/armorclaw"
  if [[ -n "$ARMORIQ_PLUGIN_VERSION" ]]; then
    plugin_pkg="${plugin_pkg}@${ARMORIQ_PLUGIN_VERSION}"
  fi

  ui_info "Installing ArmorClaw plugin from npm: ${plugin_pkg}"

  # Clean up stale backups from previous installer runs. OpenClaw v2026.4+
  # walks the extensions dir and treats any armorclaw.bak.* as a duplicate
  # plugin id, which causes "global plugin will be overridden" warnings and
  # can load the wrong dist/index.js.
  local extdir="$HOME/.openclaw/extensions"
  if [[ -d "$extdir" ]]; then
    local stale
    for stale in "$extdir"/armorclaw.bak.* "$extdir"/armorclaw.predev-bak.*; do
      [[ -e "$stale" ]] || continue
      rm -rf "$stale" 2>/dev/null && \
        ui_info "Removed stale backup: $(basename "$stale")"
    done
  fi

  # If a previous ArmorClaw extension is installed, back it up rather than
  # nuke it. Users sometimes have local edits or a symlinked dev checkout
  # they don't want to lose silently.
  local existing_ext="$HOME/.openclaw/extensions/armorclaw"
  if [[ -e "$existing_ext" ]]; then
    local backup="${existing_ext}.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$existing_ext" "$backup" 2>/dev/null && \
      ui_warn "Existing ArmorClaw install moved to: ${backup}"
  fi

  node -e "
    const fs = require('fs');
    const f = process.env.HOME + '/.openclaw/openclaw.json';
    try {
      let c = JSON.parse(fs.readFileSync(f, 'utf8'));
      let changed = false;
      if (c.plugins?.entries?.armorclaw) { delete c.plugins.entries.armorclaw; changed = true; }
      if (c.plugins?.installs?.armorclaw) { delete c.plugins.installs.armorclaw; changed = true; }
      if (Array.isArray(c.plugins?.allow)) {
        const idx = c.plugins.allow.indexOf('armorclaw');
        if (idx !== -1) { c.plugins.allow.splice(idx, 1); changed = true; }
      }
      if (changed) fs.writeFileSync(f, JSON.stringify(c, null, 2) + '\n');
    } catch {}
  " 2>/dev/null || true

  local prev_dir="$PWD"
  cd "$ARMORIQ_INSTALL_DIR"

  # OpenClaw v2026.4+ has a strict plugin-install scanner that blocks any
  # plugin reading process.env + making HTTP calls (it flags this as
  # "credential harvesting"). ArmorClaw legitimately does both — that's its
  # job. Pass --dangerously-force-unsafe-install to bypass the static check;
  # we trust @armoriq/armorclaw because we publish it.
  local install_flags="--dangerously-force-unsafe-install --force"
  if [[ -f "openclaw.mjs" ]]; then
    run_quiet_step "Installing ArmorClaw plugin" node openclaw.mjs plugins install $install_flags "$plugin_pkg"
  elif [[ -f "dist/entry.js" ]]; then
    run_quiet_step "Installing ArmorClaw plugin" node dist/entry.js plugins install $install_flags "$plugin_pkg"
  else
    ui_error "No openclaw entry point found. Build may have failed."
    cd "$prev_dir"
    exit 1
  fi

  cd "$prev_dir"

  if [[ -d "$HOME/.openclaw/extensions/armorclaw" ]]; then
    ui_success "ArmorClaw plugin installed from npm"
  else
    ui_error "Plugin installation may have failed"
    ui_info "Try manually: cd $ARMORIQ_INSTALL_DIR && openclaw plugins install ${plugin_pkg}"
  fi
}



setup_api_key() {
  if [[ -n "$ARMORIQ_API_KEY" ]]; then
    ui_success "API key provided via --api-key"
    return 0
  fi

  if [[ -n "${ARMORIQ_API_KEY_ENV:-}" ]]; then
    ARMORIQ_API_KEY="$ARMORIQ_API_KEY_ENV"
    ui_success "API key from environment"
    return 0
  fi

  if [[ "$ARMORIQ_SKIP_KEY" == "true" || "$ARMORIQ_NO_PROMPT" == "true" ]]; then
    ui_info "Skipping API key setup"
    return 0
  fi

  if ! is_promptable; then
    ui_info "No TTY, skipping API key. Set ARMORIQ_API_KEY later."
    return 0
  fi

  echo ""
  ui_section "ArmorClaw API Key"
  echo ""
  echo -e "  ${W}Get your API key at:${N}"
  echo ""
  echo -e "    ${CYAN}https://claw.armoriq.ai/${N}"
  echo ""
  echo -e "  ${D}Sign up or log in, then go to Settings > API Keys.${N}"
  echo ""

  local choice
  choice="$(prompt_choice "Do you have an API key?" \
    "Yes, enter it now" \
    "No, I'll set it up later")"

  case "$choice" in
    "Yes, enter it now")
      ARMORIQ_API_KEY="$(prompt_input "Paste your ArmorIQ API key (ak_live_...)")"
      if [[ -z "$ARMORIQ_API_KEY" ]]; then
        ui_warn "No key entered, skipping"
      else
        ui_success "API key saved"
      fi
      ;;
    *)
      ui_info "Skipped. Set ARMORIQ_API_KEY in your env or openclaw.json later."
      ;;
  esac
}


setup_telegram() {
  if [[ -n "$ARMORIQ_TELEGRAM_TOKEN" ]]; then
    ui_success "Telegram bot token provided"
    return 0
  fi

  if [[ "$ARMORIQ_NO_PROMPT" == "true" ]]; then
    ui_info "Skipping Telegram setup (non-interactive)"
    return 0
  fi

  if ! is_promptable; then
    ui_info "No TTY, skipping Telegram. Set ARMORIQ_TELEGRAM_TOKEN later."
    return 0
  fi

  echo ""
  ui_section "Telegram Bot Setup"
  echo ""
  echo -e "  ${W}Create a bot with @BotFather on Telegram:${N}"
  echo -e "    ${CYAN}https://t.me/BotFather${N}"
  echo ""
  echo -e "  ${D}1. Open Telegram and chat with @BotFather${N}"
  echo -e "  ${D}2. Run /newbot and follow the prompts${N}"
  echo -e "  ${D}3. Copy the bot token${N}"
  echo ""

  local choice
  choice="$(prompt_choice "Set up Telegram bot?" \
    "Yes, I have a bot token" \
    "No, skip for now")"

  case "$choice" in
    "Yes, I have a bot token")
      ARMORIQ_TELEGRAM_TOKEN="$(prompt_input "Paste your Telegram bot token")"
      if [[ -z "$ARMORIQ_TELEGRAM_TOKEN" ]]; then
        ui_warn "No token entered, skipping Telegram"
        return 0
      fi

      local dm_choice
      dm_choice="$(prompt_choice "DM policy (who can message the bot?)" \
        "open - allow all DMs" \
        "pairing - require pairing code approval" \
        "allowlist - only allowed user IDs")"
      case "$dm_choice" in
        "open"*)     ARMORIQ_TELEGRAM_DM_POLICY="open" ;;
        "pairing"*) ARMORIQ_TELEGRAM_DM_POLICY="pairing" ;;
        "allowlist"*) ARMORIQ_TELEGRAM_DM_POLICY="allowlist" ;;
      esac

      local stream_choice
      stream_choice="$(prompt_choice "Stream mode (reply streaming in DMs)" \
        "partial - stream partial updates (recommended)" \
        "block - chunked block updates" \
        "off - no streaming")"
      case "$stream_choice" in
        "partial"*) ARMORIQ_TELEGRAM_STREAM_MODE="partial" ;;
        "block"*)   ARMORIQ_TELEGRAM_STREAM_MODE="block" ;;
        "off"*)     ARMORIQ_TELEGRAM_STREAM_MODE="off" ;;
      esac

      ui_success "Telegram configured (${ARMORIQ_TELEGRAM_DM_POLICY}, stream: ${ARMORIQ_TELEGRAM_STREAM_MODE})"
      ;;
    *)
      ui_info "Skipped. Set ARMORIQ_TELEGRAM_TOKEN later."
      ;;
  esac
}


setup_agent_model() {
  if [[ -n "$ARMORIQ_MODEL" ]]; then
    ui_success "Model already set: ${ARMORIQ_MODEL}"
    return 0
  fi

  if [[ "$ARMORIQ_NO_PROMPT" == "true" ]]; then
    return 0
  fi

  if ! is_promptable; then
    return 0
  fi

  echo ""
  ui_section "Agent Model"
  echo ""

  local model_choice
  model_choice="$(prompt_choice "Select primary LLM provider" \
    "OpenAI GPT (gpt-5.2)" \
    "Anthropic Claude (claude-opus-4-6)" \
    "Google Gemini (gemini-2.5-flash)" \
    "OpenRouter (any model)" \
    "Custom model ID")"

  case "$model_choice" in
    "OpenAI GPT"*)
      ARMORIQ_MODEL="openai/gpt-5.2"
      if [[ -z "$ARMORIQ_OPENAI_KEY" ]]; then
        ARMORIQ_OPENAI_KEY="$(prompt_input "Paste your OpenAI API key (sk-...)")"
      fi
      ;;
    "Anthropic Claude"*)
      ARMORIQ_MODEL="anthropic/claude-opus-4-6"
      if [[ -z "$ARMORIQ_ANTHROPIC_KEY" ]]; then
        ARMORIQ_ANTHROPIC_KEY="$(prompt_input "Paste your Anthropic API key (sk-ant-...)")"
      fi
      ;;
    "Google Gemini"*)
      ARMORIQ_MODEL="google/gemini-2.5-flash"
      if [[ -z "$ARMORIQ_GEMINI_KEY" ]]; then
        ARMORIQ_GEMINI_KEY="$(prompt_input "Paste your Google Gemini API key (AIza...)")"
      fi
      ;;
    "OpenRouter"*)
      ARMORIQ_MODEL="openrouter/auto"
      if [[ -z "$ARMORIQ_OPENROUTER_KEY" ]]; then
        ARMORIQ_OPENROUTER_KEY="$(prompt_input "Paste your OpenRouter API key (sk-or-...)")"
      fi
      ;;
    "Custom"*)
      ARMORIQ_MODEL="$(prompt_input "Enter model ID (e.g. openai/gpt-5.2, anthropic/claude-opus-4-6)")"
      # Offer to capture an API key for whatever provider they typed
      if [[ "$ARMORIQ_MODEL" == openai/* && -z "$ARMORIQ_OPENAI_KEY" ]]; then
        ARMORIQ_OPENAI_KEY="$(prompt_input "Paste your OpenAI API key (sk-...) [optional]" || true)"
      elif [[ "$ARMORIQ_MODEL" == anthropic/* && -z "$ARMORIQ_ANTHROPIC_KEY" ]]; then
        ARMORIQ_ANTHROPIC_KEY="$(prompt_input "Paste your Anthropic API key (sk-ant-...) [optional]" || true)"
      elif [[ "$ARMORIQ_MODEL" == google/* && -z "$ARMORIQ_GEMINI_KEY" ]]; then
        ARMORIQ_GEMINI_KEY="$(prompt_input "Paste your Google Gemini API key [optional]" || true)"
      elif [[ "$ARMORIQ_MODEL" == openrouter/* && -z "$ARMORIQ_OPENROUTER_KEY" ]]; then
        ARMORIQ_OPENROUTER_KEY="$(prompt_input "Paste your OpenRouter API key (sk-or-...) [optional]" || true)"
      fi
      ;;
  esac

  if [[ -n "$ARMORIQ_MODEL" ]]; then
    ui_success "Model: ${ARMORIQ_MODEL}"
  fi
}


ARMORIQ_USER_EMAIL=""

resolve_user_email() {
  # Attempt auto-resolve from API key whoami endpoint
  if [[ -n "$ARMORIQ_API_KEY" ]]; then
    local backend_url="https://armorclaw-api.armoriq.ai"
    if [[ "$ARMORIQ_API_KEY" != ak_claw_* ]]; then
      backend_url="https://api.armoriq.ai"
    fi

    local resp=""
    if command -v curl &>/dev/null; then
      resp="$(curl -fsSL -H "X-API-Key: ${ARMORIQ_API_KEY}" "${backend_url}/api-keys/whoami" 2>/dev/null || true)"
    elif command -v wget &>/dev/null; then
      resp="$(wget -qO- --header="X-API-Key: ${ARMORIQ_API_KEY}" "${backend_url}/api-keys/whoami" 2>/dev/null || true)"
    fi

    if [[ -n "$resp" ]]; then
      local email
      email="$(echo "$resp" | node -e "try{const d=JSON.parse(require('fs').readFileSync(0,'utf8'));if(d.email)console.log(d.email)}catch{}" 2>/dev/null || true)"
      if [[ -n "$email" ]]; then
        ARMORIQ_USER_EMAIL="$email"
        ui_success "Resolved account: ${email}"
      else
        ui_warn "Could not resolve account email from API key"
      fi
    else
      ui_warn "Could not reach backend to resolve account email"
    fi
  fi

  # If still unset (no key, or whoami failed), prompt so userId is never 'default-user'
  if [[ -z "$ARMORIQ_USER_EMAIL" ]] && is_promptable; then
    echo ""
    ui_info "Your email is used as your agent's userId in ArmorIQ."
    local entered_email
    entered_email="$(prompt_input "Enter your email address (e.g. you@example.com)")"
    # Strip any characters that would break the JS string interpolation
    entered_email="$(echo "$entered_email" | tr -d "'\"\\\n\r")"
    if [[ -n "$entered_email" ]]; then
      ARMORIQ_USER_EMAIL="$entered_email"
      ui_success "userId set to: ${ARMORIQ_USER_EMAIL}"
    else
      ui_warn "No email entered. userId will default to 'default-user' — update openclaw.json later."
    fi
  fi
}

configure_openclaw_json() {
  local config_dir="$HOME/.openclaw"
  local config_file="${config_dir}/openclaw.json"

  mkdir -p "$config_dir"

  # On Windows (MSYS/Git Bash), $HOME is /c/Users/... which Node.js cannot
  # read.  Convert to C:/Users/... so the inline node -e script works.
  # This is a no-op on Linux/macOS where $HOME is already a native path.
  local node_config_file="$config_file"
  local node_config_dir="$config_dir"
  if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "mingw"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
    node_config_file="$(cygpath -m "$config_file" 2>/dev/null || echo "$config_file")"
    node_config_dir="$(cygpath -m "$config_dir" 2>/dev/null || echo "$config_dir")"
  fi

  local api_key_val=""
  [[ -n "$ARMORIQ_API_KEY" ]] && api_key_val="$ARMORIQ_API_KEY"

  local model_val="${ARMORIQ_MODEL}"
  local openai_key_val="${ARMORIQ_OPENAI_KEY}"
  local openrouter_key_val="${ARMORIQ_OPENROUTER_KEY}"
  local anthropic_key_val="${ARMORIQ_ANTHROPIC_KEY}"
  local gemini_key_val="${ARMORIQ_GEMINI_KEY}"
  local telegram_token="${ARMORIQ_TELEGRAM_TOKEN}"
  local telegram_dm_policy="${ARMORIQ_TELEGRAM_DM_POLICY}"
  local telegram_stream_mode="${ARMORIQ_TELEGRAM_STREAM_MODE}"
  local user_email="${ARMORIQ_USER_EMAIL}"

  ARMORIQ_USER_EMAIL_SAFE="$user_email" node -e "
    const fs = require('fs');
    const path = require('path');
    let c = {};
    try { c = JSON.parse(fs.readFileSync('${node_config_file}', 'utf8')); } catch {}

    if (!c.agents) c.agents = {};
    if (!c.agents.defaults) c.agents.defaults = {};
    if (!c.commands) c.commands = {};
    c.commands.native = c.commands.native || 'auto';
    c.commands.nativeSkills = c.commands.nativeSkills || 'auto';
    if (!c.gateway) c.gateway = {};
    c.gateway.mode = c.gateway.mode || 'local';
    if (!c.plugins) c.plugins = {};
    c.plugins.enabled = true;
    if (!c.plugins.entries) c.plugins.entries = {};
    if (!c.channels) c.channels = {};
    if (!c.messages) c.messages = {};
    c.messages.ackReactionScope = c.messages.ackReactionScope || 'group-mentions';

    // model config
    const modelVal = '${model_val}';
    if (modelVal) {
      if (!c.agents.defaults.model) c.agents.defaults.model = {};
      c.agents.defaults.model.primary = modelVal;
    } else if (!c.agents.defaults.model?.primary) {
      if (!c.agents.defaults.model) c.agents.defaults.model = {};
      c.agents.defaults.model.primary = 'openai/gpt-5.2';
    }

    // auth profiles in openclaw.json (no apiKey here, keys go in agent auth-profiles.json)
    if (!c.auth) c.auth = {};
    if (!c.auth.profiles) c.auth.profiles = {};
    if (!c.auth.order) c.auth.order = {};

    const openaiKey = '${openai_key_val}';
    const openrouterKey = '${openrouter_key_val}';
    const anthropicKey = '${anthropic_key_val}';
    const geminiKey = '${gemini_key_val}';
    const telegramToken = '${telegram_token}';
    const telegramDmPolicy = '${telegram_dm_policy}';
    const telegramStreamMode = '${telegram_stream_mode}';

    if (openaiKey) {
      c.auth.profiles['openai:default'] = { provider: 'openai', mode: 'api_key' };
      c.auth.order.openai = c.auth.order.openai || ['openai:default'];
    }
    if (openrouterKey) {
      c.auth.profiles['openrouter:default'] = { provider: 'openrouter', mode: 'api_key' };
      c.auth.order.openrouter = c.auth.order.openrouter || ['openrouter:default'];
    }
    if (anthropicKey) {
      c.auth.profiles['anthropic:default'] = { provider: 'anthropic', mode: 'api_key' };
      c.auth.order.anthropic = c.auth.order.anthropic || ['anthropic:default'];
    }
    if (geminiKey) {
      c.auth.profiles['google:default'] = { provider: 'google', mode: 'api_key' };
      c.auth.order.google = c.auth.order.google || ['google:default'];
    }

    // Telegram channel
    if (telegramToken) {
      c.channels.telegram = {
        enabled: true,
        botToken: telegramToken,
        dmPolicy: telegramDmPolicy || 'open',
        allowFrom: ['*'],
        groupPolicy: 'allowlist',
        streamMode: telegramStreamMode || 'partial',
        ...(c.channels.telegram || {}),
      };
      c.channels.telegram.botToken = telegramToken;
      if (!c.plugins.entries.telegram) c.plugins.entries.telegram = {};
      c.plugins.entries.telegram.enabled = true;
      if (!c.plugins.allow) c.plugins.allow = [];
      if (!c.plugins.allow.includes('telegram')) c.plugins.allow.push('telegram');
    }

    // armorclaw always in allow list
    if (!c.plugins.allow) c.plugins.allow = [];
    if (!c.plugins.allow.includes('armorclaw')) c.plugins.allow.unshift('armorclaw');

    // armorclaw plugin
    const existing = c.plugins.entries.armorclaw?.config || {};
    const apiKey = '${api_key_val}';
    // ak_claw_* → armorclaw-api/customer-iap (no proxy); else api/iap/proxy
    const isArmorClawKey = apiKey && apiKey.startsWith('ak_claw_');
    const defaults = isArmorClawKey
      ? {
          iap:     'https://customer-iap.armoriq.ai',
          backend: 'https://armorclaw-api.armoriq.ai',
          proxy:   null,                                // ak_claw_ doesn't need it
        }
      : {
          iap:     'https://iap.armoriq.ai',
          backend: 'https://api.armoriq.ai',
          proxy:   'https://proxy.armoriq.ai',
        };
    const newConfig = {
      enabled: true,
      ...existing,
      policyUpdateEnabled: existing.policyUpdateEnabled ?? true,
      policyUpdateAllowList: existing.policyUpdateAllowList?.length ? existing.policyUpdateAllowList : ['*'],
      userId: existing.userId || process.env.ARMORIQ_USER_EMAIL_SAFE || 'default-user',
      agentId: existing.agentId || 'openclaw-agent-001',
      contextId: existing.contextId || 'default',
      policyStorePath: existing.policyStorePath || '${node_config_dir}/armoriq.policy.json',
      iapEndpoint: existing.iapEndpoint || defaults.iap,
      backendEndpoint: existing.backendEndpoint || defaults.backend,
    };
    if (existing.proxyEndpoint) {
      // user explicitly set proxy — preserve regardless of key flavor
      newConfig.proxyEndpoint = existing.proxyEndpoint;
    } else if (defaults.proxy) {
      // ak_live_*/ak_test_* path needs proxy
      newConfig.proxyEndpoint = defaults.proxy;
    }
    if (apiKey) newConfig.apiKey = apiKey;
    c.plugins.entries.armorclaw = {
      ...c.plugins.entries.armorclaw,
      enabled: true,
      config: newConfig
    };
    fs.writeFileSync('${node_config_file}', JSON.stringify(c, null, 2) + '\\n');

    // write actual API keys into agent auth-profiles.json (where OpenClaw reads them)
    // format: { version: 1, profiles: { "provider:default": { type: "api_key", provider, key } }, order: {} }
    const agentAuthProfiles = {};
    const agentAuthOrder = {};
    if (openaiKey) {
      agentAuthProfiles['openai:default'] = { type: 'api_key', provider: 'openai', key: openaiKey };
      agentAuthOrder.openai = ['openai:default'];
    }
    if (openrouterKey) {
      agentAuthProfiles['openrouter:default'] = { type: 'api_key', provider: 'openrouter', key: openrouterKey };
      agentAuthOrder.openrouter = ['openrouter:default'];
    }
    if (anthropicKey) {
      agentAuthProfiles['anthropic:default'] = { type: 'api_key', provider: 'anthropic', key: anthropicKey };
      agentAuthOrder.anthropic = ['anthropic:default'];
    }
    if (geminiKey) {
      agentAuthProfiles['google:default'] = { type: 'api_key', provider: 'google', key: geminiKey };
      agentAuthOrder.google = ['google:default'];
    }

    if (Object.keys(agentAuthProfiles).length > 0) {
      const authPaths = [
        path.join('${node_config_dir}', 'auth-profiles.json'),
        path.join('${node_config_dir}', 'agents', 'main', 'agent', 'auth-profiles.json'),
      ];
      for (const apFile of authPaths) {
        try {
          fs.mkdirSync(path.dirname(apFile), { recursive: true });
          let store = { version: 1, profiles: {}, order: {} };
          try {
            const raw = JSON.parse(fs.readFileSync(apFile, 'utf8'));
            if (raw.profiles) store = raw;
          } catch {}
          store.profiles = { ...store.profiles, ...agentAuthProfiles };
          store.order = { ...store.order, ...agentAuthOrder };
          fs.writeFileSync(apFile, JSON.stringify(store, null, 2) + '\\n');
        } catch {}
      }
    }
  " 2>/dev/null

  ui_success "openclaw.json configured"
}

write_env_file() {
  local env_file="${ARMORIQ_INSTALL_DIR}/.env"

  if [[ -f "$env_file" ]]; then
    if grep -q "ARMORIQ_API_KEY" "$env_file" 2>/dev/null; then
      ui_info ".env already has ArmorIQ vars"
      if [[ -n "$ARMORIQ_API_KEY" ]]; then
        sed -i.bak "s|^ARMORIQ_API_KEY=.*|ARMORIQ_API_KEY=${ARMORIQ_API_KEY}|" "$env_file"
        rm -f "${env_file}.bak"
        ui_success "Updated ARMORIQ_API_KEY in .env"
      fi
      return 0
    fi
  fi

  local key_val=""
  [[ -n "$ARMORIQ_API_KEY" ]] && key_val="$ARMORIQ_API_KEY" || key_val="ak_live_YOUR_KEY_HERE"

  # ak_claw_*  → armorclaw-api + customer-iap, no proxy (local-tool flows)
  # ak_live_*  → api/iap/proxy.armoriq.ai (ArmorIQ platform, needs proxy)
  local iap_url backend_url proxy_block
  if [[ "$key_val" == ak_claw_* ]]; then
    iap_url="https://customer-iap.armoriq.ai"
    backend_url="https://armorclaw-api.armoriq.ai"
    proxy_block=$'\n# Proxy NOT needed for ak_claw_* (local tools skip /invoke).\n# Uncomment only if you wire in MCP-routed tools later.\n# PROXY_ENDPOINT=https://customer-proxy.armoriq.ai'
  else
    iap_url="https://iap.armoriq.ai"
    backend_url="https://api.armoriq.ai"
    proxy_block=$'\n# Proxy REQUIRED for ak_live_* / ak_test_* (ArmorIQ platform).\nPROXY_ENDPOINT=https://proxy.armoriq.ai'
  fi

  # Env vars are fallbacks; openclaw.json wins. Kept for raw-SDK consumers.
  cat >> "$env_file" << ENVEOF

# ArmorIQ
ARMORIQ_API_KEY=${key_val}
IAP_ENDPOINT=${iap_url}
BACKEND_ENDPOINT=${backend_url}
${proxy_block}
ENVEOF

  ui_success ".env written with ArmorIQ endpoints"
}


# Write per-agent auth-profiles.json. OpenClaw v2026.4+ reads LLM keys
# from this file, not OPENAI_API_KEY/etc env vars.
write_auth_profiles() {
  local store_dir="${HOME}/.openclaw/agents/main/agent"
  local store_file="${store_dir}/auth-profiles.json"
  mkdir -p "$store_dir"

  # Convert path for Node.js on Windows (MSYS/Git Bash)
  local node_store_file="$store_file"
  if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "mingw"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
    node_store_file="$(cygpath -m "$store_file" 2>/dev/null || echo "$store_file")"
  fi

  # Build the profiles object incrementally so multiple keys can land.
  local profiles="{}"
  local emitted_any=false

  if [[ -n "$ARMORIQ_OPENAI_KEY" ]]; then
    profiles=$(printf '%s' "$profiles" | node -e '
      let p = {};
      try { p = JSON.parse(require("fs").readFileSync(0, "utf8")) } catch {}
      p["openai-primary"] = { type: "api_key", provider: "openai", key: process.argv[1], displayName: "OpenAI (installer)" };
      console.log(JSON.stringify(p));
    ' "$ARMORIQ_OPENAI_KEY")
    emitted_any=true
  fi

  if [[ -n "$ARMORIQ_ANTHROPIC_KEY" ]]; then
    profiles=$(printf '%s' "$profiles" | node -e '
      let p = {};
      try { p = JSON.parse(require("fs").readFileSync(0, "utf8")) } catch {}
      p["anthropic-primary"] = { type: "api_key", provider: "anthropic", key: process.argv[1], displayName: "Anthropic (installer)" };
      console.log(JSON.stringify(p));
    ' "$ARMORIQ_ANTHROPIC_KEY")
    emitted_any=true
  fi

  if [[ -n "$ARMORIQ_GEMINI_KEY" ]]; then
    profiles=$(printf '%s' "$profiles" | node -e '
      let p = {};
      try { p = JSON.parse(require("fs").readFileSync(0, "utf8")) } catch {}
      p["gemini-primary"] = { type: "api_key", provider: "google", key: process.argv[1], displayName: "Google Gemini (installer)" };
      console.log(JSON.stringify(p));
    ' "$ARMORIQ_GEMINI_KEY")
    emitted_any=true
  fi

  if [[ -n "$ARMORIQ_OPENROUTER_KEY" ]]; then
    profiles=$(printf '%s' "$profiles" | node -e '
      let p = {};
      try { p = JSON.parse(require("fs").readFileSync(0, "utf8")) } catch {}
      p["openrouter-primary"] = { type: "api_key", provider: "openrouter", key: process.argv[1], displayName: "OpenRouter (installer)" };
      console.log(JSON.stringify(p));
    ' "$ARMORIQ_OPENROUTER_KEY")
    emitted_any=true
  fi

  if [[ "$emitted_any" != "true" ]]; then
    if [[ -f "$store_file" ]]; then
      ui_info "auth-profiles.json untouched (no LLM key supplied via --openai-key/--anthropic-key/--gemini-key)"
    else
      cat > "$store_file" <<'AUTHEOF'
{
  "version": 1,
  "profiles": {}
}
AUTHEOF
      ui_warn "auth-profiles.json created EMPTY — add a provider key before first run"
      ui_info "  Edit: ${store_file}"
    fi
    return 0
  fi

  # Wrap profiles object in the AuthProfileStore envelope.
  printf '%s' "$profiles" | node -e '
    const profiles = JSON.parse(require("fs").readFileSync(0, "utf8"));
    const store = { version: 1, profiles };
    require("fs").writeFileSync(process.argv[1], JSON.stringify(store, null, 2) + "\n");
  ' "$node_store_file"

  ui_success "Wrote ${store_file}"
  # Pretty-print which providers landed.
  local providers_seen=""
  [[ -n "$ARMORIQ_OPENAI_KEY" ]]     && providers_seen="${providers_seen}openai-primary, "
  [[ -n "$ARMORIQ_ANTHROPIC_KEY" ]]  && providers_seen="${providers_seen}anthropic-primary, "
  [[ -n "$ARMORIQ_GEMINI_KEY" ]]     && providers_seen="${providers_seen}gemini-primary, "
  [[ -n "$ARMORIQ_OPENROUTER_KEY" ]] && providers_seen="${providers_seen}openrouter-primary, "
  providers_seen="${providers_seen%, }"
  [[ -n "$providers_seen" ]] && ui_info "  Providers: ${providers_seen}"
}


show_plan() {
  ui_section "Install plan"
  ui_kv "OS" "$OS"
  ui_kv "OpenClaw version" "v${ARMORIQ_OC_VERSION}"
  ui_kv "Install directory" "$ARMORIQ_INSTALL_DIR"

  local plugin_pkg="@armoriq/armorclaw"
  if [[ -n "$ARMORIQ_PLUGIN_VERSION" ]]; then
    plugin_pkg="${plugin_pkg}@${ARMORIQ_PLUGIN_VERSION}"
  else
    plugin_pkg="${plugin_pkg}@latest"
  fi
  ui_kv "Plugin package" "$plugin_pkg"

  if [[ -n "$ARMORIQ_MODEL" ]]; then
    ui_kv "Model" "$ARMORIQ_MODEL"
  else
    ui_kv "Model" "will prompt (OpenAI / Anthropic / Gemini / OpenRouter / Custom)"
  fi
  # Per-provider LLM keys: report what's already pre-supplied vs what'll
  # be collected interactively in setup_agent_model.
  local llm_keys_provided=0
  [[ -n "$ARMORIQ_OPENAI_KEY" ]]     && { ui_kv "OpenAI key" "provided";     llm_keys_provided=1; }
  [[ -n "$ARMORIQ_ANTHROPIC_KEY" ]]  && { ui_kv "Anthropic key" "provided";  llm_keys_provided=1; }
  [[ -n "$ARMORIQ_GEMINI_KEY" ]]     && { ui_kv "Gemini key" "provided";     llm_keys_provided=1; }
  [[ -n "$ARMORIQ_OPENROUTER_KEY" ]] && { ui_kv "OpenRouter key" "provided"; llm_keys_provided=1; }
  if [[ "$llm_keys_provided" == "0" ]]; then
    ui_kv "LLM provider key" "will prompt for the model you pick"
  fi
  if [[ -n "$ARMORIQ_TELEGRAM_TOKEN" ]]; then
    ui_kv "Telegram" "enabled (dm: ${ARMORIQ_TELEGRAM_DM_POLICY}, stream: ${ARMORIQ_TELEGRAM_STREAM_MODE})"
  else
    ui_kv "Telegram" "will prompt"
  fi

  if [[ -n "$ARMORIQ_API_KEY" ]]; then
    ui_kv "API key" "provided"
  elif [[ "$ARMORIQ_SKIP_KEY" == "true" ]]; then
    ui_kv "API key" "skipped"
  else
    ui_kv "API key" "will prompt"
  fi

  if [[ "$ARMORIQ_DRY_RUN" == "true" ]]; then
    ui_kv "Dry run" "yes"
  fi
}

main() {
  bootstrap_gum || true
  print_banner
  detect_os

  if [[ -z "$ARMORIQ_INSTALL_DIR" ]]; then
    ARMORIQ_INSTALL_DIR="$HOME/openclaw-armoriq"
  fi

  ensure_node
  resolve_version
  show_plan

  if [[ "$ARMORIQ_DRY_RUN" == "true" ]]; then
    ui_success "Dry run complete"
    return 0
  fi

  # [1/6] Environment
  ui_stage "Preparing environment"
  ensure_git
  ensure_pnpm
  # python3 no longer required — patches are gone

  # [2/6] Clone (vanilla OpenClaw — no patching)
  ui_stage "Cloning OpenClaw v${ARMORIQ_OC_VERSION}"
  clone_openclaw

  # [3/6] Build
  ui_stage "Building OpenClaw"
  build_openclaw

  # [4/6] ArmorClaw plugin
  ui_stage "Setting up ArmorClaw"
  install_plugin

  # [5/6] Channels, agent model, API keys (collected interactively unless --no-prompt)
  ui_stage "Configuring channels and agent"
  setup_telegram
  setup_agent_model
  setup_api_key

  # [6/6] Write config + LLM auth-profile + .env
  ui_stage "Writing configuration"
  resolve_user_email
  configure_openclaw_json
  write_env_file
  write_auth_profiles

  echo ""
  ui_celebrate "ArmorClaw installed successfully on OpenClaw v${ARMORIQ_OC_VERSION}"
  local completion_msg
  completion_msg="$(pick_completion_message)"
  echo -e "${MUTED}${completion_msg}${N}"
  echo ""

  ui_section "Quick reference"
  ui_kv "OpenClaw" "$ARMORIQ_INSTALL_DIR"
  ui_kv "Plugin" "$HOME/.openclaw/extensions/armorclaw"
  ui_kv "Config" "$HOME/.openclaw/openclaw.json"
  ui_kv "Env file" "${ARMORIQ_INSTALL_DIR}/.env"
  if [[ -n "$ARMORIQ_TELEGRAM_TOKEN" ]]; then
    ui_kv "Telegram" "enabled (dm: ${ARMORIQ_TELEGRAM_DM_POLICY})"
  fi
  ui_kv "Model" "${ARMORIQ_MODEL:-openai/gpt-5.2}"
  if [[ -n "$ARMORIQ_API_KEY" ]]; then
    ui_kv "API key" "configured"
  else
    ui_kv "API key" "not set (add to .env or openclaw.json)"
    echo ""
    echo -e "  ${W}Get your key at: ${CYAN}https://claw.armoriq.ai/${N}"
  fi
  echo ""

  ui_kv "Docs" "https://docs.armoriq.ai"
  ui_kv "Dashboard" "https://claw.armoriq.ai"

  print_footer
}

parse_args "$@"
main