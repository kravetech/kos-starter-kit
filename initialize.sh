#!/usr/bin/env bash
set -euo pipefail

starter_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
agent="auto"
answers=""
dry_run="false"
migration="false"

while (($#)); do
  case "$1" in
    --agent) agent="${2:?missing agent}"; shift 2 ;;
    --answers) answers="${2:?missing answer file}"; shift 2 ;;
    --dry-run) dry_run="true"; shift ;;
    --resume) printf '%s\n' 'RESUME_REQUIRES_JOURNAL_REVIEW: inspect the interrupted journal and preview rollback before replanning.' >&2; exit 2 ;;
    --migration) migration="true"; shift ;;
    -h|--help)
      printf '%s\n' "Usage: ./initialize.sh [--agent auto|codex|claude|gemini] [--answers FILE] [--dry-run] [--migration]"
      exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

case "$agent" in
  auto|codex|claude|gemini) ;;
  *) printf '%s\n' 'ERROR: choose auto, codex, claude or gemini.' >&2; exit 2 ;;
esac
if [[ -n "$answers" && ! -f "$answers" ]]; then
  printf '%s\n' 'ERROR: answer file not found.' >&2
  exit 2
fi

if command -v codex >/dev/null 2>&1; then have_codex="true"; else have_codex="false"; fi
if command -v claude >/dev/null 2>&1; then have_claude="true"; else have_claude="false"; fi
if command -v gemini >/dev/null 2>&1; then have_gemini="true"; else have_gemini="false"; fi
if [[ "$agent" == "auto" ]]; then
  if [[ "$have_codex" == "true" ]]; then agent="codex"
  elif [[ "$have_claude" == "true" ]]; then agent="claude"
  elif [[ "$have_gemini" == "true" ]]; then agent="gemini"
  else printf '%s\n' "ERROR: no supported agent was found on PATH." >&2; exit 2
  fi
fi
if [[ "$agent" == "codex" && "$have_codex" != "true" ]]; then
  printf '%s\n' "ERROR: codex not found." >&2
  exit 2
fi
if [[ "$agent" == "claude" && "$have_claude" != "true" ]]; then
  printf '%s\n' "ERROR: claude not found." >&2
  exit 2
fi

if [[ "$agent" == "gemini" && "$have_gemini" != "true" ]]; then
  printf '%s\n' "ERROR: gemini not found." >&2; exit 2
fi

prompt="Read KOS-INSTALLER.md and execute the installation."
if [[ -n "$answers" ]]; then
  answer_path="$(cd -- "$(dirname -- "$answers")" && pwd)/$(basename -- "$answers")"
  prompt+=" Use answer file: $answer_path"
fi
if [[ "$dry_run" == "true" ]]; then prompt+=" Run in dry-run mode only."; fi
if [[ "$migration" == "true" ]]; then prompt+=" Use migration mode and preserve existing files."; fi

mkdir -p "$starter_root/logs"
log="$starter_root/logs/initialize-$(date +%Y%m%d-%H%M%S).log"
answer_supplied="false"
if [[ -n "$answers" ]]; then answer_supplied="true"; fi
printf 'KOS Community installer folder: %s\nAgent: %s\nAnswer file supplied: %s\nDry run: %s\nMigration: %s\n' \
  "$starter_root" "$agent" "$answer_supplied" "$dry_run" "$migration" >"$log"

cd "$starter_root"
if [[ "$agent" == "codex" ]]; then
  exec codex -C "$starter_root" "$prompt"
elif [[ "$agent" == "gemini" ]]; then
  exec gemini "$prompt"
else
  exec claude --add-dir "$starter_root" "$prompt"
fi
