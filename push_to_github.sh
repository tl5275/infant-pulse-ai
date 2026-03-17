#!/usr/bin/env bash

set -u
set -o pipefail

COMMIT_MESSAGE="Initial commit - Infant Pulse AI system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  printf '[%s] %s\n' "$1" "$2"
}

fail() {
  log "ERROR" "$1"
  exit 1
}

run() {
  log "INFO" "$*"
  "$@"
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    fail "Command failed with exit code $exit_code: $*"
  fi
}

trim() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

validate_repo_url() {
  local repo_url="$1"
  if [[ "$repo_url" =~ ^https://github\.com/[^/[:space:]]+/[^/[:space:]]+(\.git)?/?$ ]] || \
     [[ "$repo_url" =~ ^git@github\.com:[^/[:space:]]+/[^/[:space:]]+(\.git)?$ ]]; then
    return 0
  fi

  fail "Invalid GitHub repository URL. Use https://github.com/owner/repo(.git) or git@github.com:owner/repo.git"
}

validate_email() {
  local email="$1"
  [[ "$email" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || fail "Invalid email format."
}

check_internet() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsI https://github.com >/dev/null 2>&1 || fail "Unable to reach GitHub. Check your internet connection and try again."
    return
  fi

  if command -v wget >/dev/null 2>&1; then
    wget --spider -q https://github.com || fail "Unable to reach GitHub. Check your internet connection and try again."
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import sys, urllib.request; urllib.request.urlopen('https://github.com', timeout=10); sys.exit(0)" >/dev/null 2>&1 || \
      fail "Unable to reach GitHub. Check your internet connection and try again."
    return
  fi

  if command -v python >/dev/null 2>&1; then
    python -c "import sys, urllib.request; urllib.request.urlopen('https://github.com', timeout=10); sys.exit(0)" >/dev/null 2>&1 || \
      fail "Unable to reach GitHub. Check your internet connection and try again."
    return
  fi

  fail "Could not find curl, wget, python3, or python to test internet connectivity."
}

ensure_git_identity() {
  local git_user_name
  local git_user_email

  git_user_name="$(git config --get user.name || true)"
  git_user_email="$(git config --get user.email || true)"

  if [[ -z "$git_user_name" ]]; then
    read -r -p "Enter git user.name: " git_user_name
    [[ -n "$git_user_name" ]] || fail "git user.name cannot be empty."
    run git config user.name "$git_user_name"
  fi

  if [[ -z "$git_user_email" ]]; then
    read -r -p "Enter git user.email: " git_user_email
    [[ -n "$git_user_email" ]] || fail "git user.email cannot be empty."
    validate_email "$git_user_email"
    run git config user.email "$git_user_email"
  fi
}

ensure_gitignore() {
  local gitignore_path=".gitignore"
  local required_entries=(
    "node_modules/"
    ".venv/"
    "venv/"
    "__pycache__/"
    "**/__pycache__/"
    "*.pyc"
    ".env"
    ".next/"
    "dist/"
    "build/"
    ".pytest_cache/"
    "*.log"
    "*.db"
  )

  touch "$gitignore_path" || fail "Failed to create .gitignore."

  local entry
  for entry in "${required_entries[@]}"; do
    grep -Fqx "$entry" "$gitignore_path" || printf '%s\n' "$entry" >>"$gitignore_path"
  done

  log "INFO" ".gitignore is ready."
}

configure_remote() {
  local repo_url="$1"
  local current_remote

  if git remote get-url origin >/dev/null 2>&1; then
    current_remote="$(git remote get-url origin)"
    if [[ "$current_remote" == "$repo_url" ]]; then
      log "INFO" "Remote origin already points to $repo_url"
    else
      log "WARN" "Remote origin exists and will be updated."
      run git remote set-url origin "$repo_url"
    fi
    return
  fi

  run git remote add origin "$repo_url"
}

main() {
  cd "$SCRIPT_DIR" || fail "Failed to switch to the script directory."

  log "INFO" "Starting GitHub push workflow from $PWD"

  command -v git >/dev/null 2>&1 || fail "Git is not installed or not available in PATH."

  local repo_url="${1:-}"
  if [[ -z "$repo_url" ]]; then
    read -r -p "Enter GitHub repository URL: " repo_url
  fi
  repo_url="$(trim "$repo_url")"
  [[ -n "$repo_url" ]] || fail "Repository URL is required."

  validate_repo_url "$repo_url"
  check_internet
  ensure_git_identity
  ensure_gitignore

  if [[ -d .git ]]; then
    log "INFO" "Git repository already initialized."
  else
    run git init
  fi

  run git add .

  if git diff --cached --quiet --ignore-submodules --; then
    if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
      fail "No staged changes found and the repository has no commits yet."
    fi
    log "WARN" "No staged changes detected. Skipping commit."
  else
    run git commit -m "$COMMIT_MESSAGE"
  fi

  run git branch -M main
  configure_remote "$repo_url"
  run git push -u origin main

  log "SUCCESS" "Project pushed to GitHub successfully."
}

main "$@"
