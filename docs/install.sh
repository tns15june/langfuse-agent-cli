#!/bin/sh
# Install langfuse-agent-cli (the lf command) and run `lf setup`.
#
#   curl -fsSL https://tns15june.github.io/langfuse-agent-cli/install.sh | sh
#   curl -fsSL https://tns15june.github.io/langfuse-agent-cli/install.sh | sh -s -- --yes   # never prompts
#
# It installs with uv when uv is present, else with pipx, else it installs uv first (into your home
# folder, with uv's official installer). Then `lf setup` asks for your Langfuse host and keys when it
# can reach your terminal; with --yes, or without a terminal, it never prompts.
set -eu

PACKAGE=langfuse-agent-cli

have() { command -v "$1" >/dev/null 2>&1; }

main() {
  yes=0
  for arg in "$@"; do
    case "$arg" in
      -y | --yes) yes=1 ;;
      *) echo "install.sh: unknown option '$arg' (the only option is --yes)" >&2; exit 2 ;;
    esac
  done
  original_path=$PATH

  if have uv; then
    installer=uv
  elif have pipx; then
    installer=pipx
  else
    echo "Neither uv nor pipx is installed; installing uv (https://docs.astral.sh/uv/) into your home folder."
    have curl || { echo "install.sh needs curl to install uv." >&2; exit 1; }
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
    export PATH
    have uv || { echo "uv did not install; install uv or pipx yourself and run this again." >&2; exit 1; }
    installer=uv
  fi

  echo "Installing $PACKAGE with $installer"
  if [ "$installer" = uv ]; then
    uv tool install --upgrade "$PACKAGE"
  else
    pipx install "$PACKAGE" || pipx upgrade "$PACKAGE"
  fi

  lf=$(command -v lf || true)
  [ -n "$lf" ] || lf="$HOME/.local/bin/lf"
  if [ ! -x "$lf" ]; then
    echo "lf was installed, but install.sh cannot find it. Run 'uv tool update-shell' or 'pipx ensurepath'," >&2
    echo "open a new terminal, and run 'lf setup'." >&2
    exit 1
  fi
  "$lf" --version
  case ":$original_path:" in
    *":$(dirname "$lf"):"*) ;;
    *) echo "Note: $(dirname "$lf") is not on your PATH yet. Run 'uv tool update-shell' or 'pipx ensurepath'," \
         "then open a new terminal to run lf directly." ;;
  esac

  # lf setup reads its prompts from the terminal; `curl | sh` leaves stdin as the pipe, so hand it /dev/tty.
  if [ "$yes" -eq 0 ] && (: </dev/tty) 2>/dev/null; then
    exec "$lf" setup </dev/tty
  fi
  exec "$lf" setup --yes
}

main "$@"
