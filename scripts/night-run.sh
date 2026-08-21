#!/usr/bin/env bash
# Finish a Gauntlet fleet run inside the quiet window (2am–6am).
#
# Kevin's desktop is near-silent in normal use, so long benchmarks belong at
# night rather than being started opportunistically during the day. This resumes
# an existing run id — completed cells are skipped, so it is safe to re-invoke.
#
# The run releases the GPU on a clean exit; models are also loaded with a TTL as
# a backstop in case this is killed hard.
#
# Intended for invocation during the quiet window. Runs until the fleet finishes
# or 6am local — whichever comes first. At 6am a note is logged and the run is
# stopped so the machine is quiet again before morning use.

set -euo pipefail

RUN_ID="${1:-fleet-0726b}"
STOP_AT="${2:-06:00}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

PYTHON=".venv/bin/python"

MODELS=(
    "llama-3.2-1b-instruct"
    "nvidia/nemotron-3-nano-4b"
    "matrixportalx/tulu-3.1-8b-supernova"
    "google/gemma-4-12b"
    "qwen/qwen3.5-9b"
    "openai_gpt-oss-20b"
    "nvidia/nemotron-3-nano"
    "google/gemma-4-31b"
    "zai-org/glm-4.7-flash"
)

log() { echo "[$(date '+%H:%M:%S')] $*"; }

model_args=()
for m in "${MODELS[@]}"; do
    model_args+=(--model "$m")
done

# Refuse to start if a run is already going. This exists as a safety net for a
# run started earlier in the day, so it must never become a second writer to the
# same run directory — two processes appending to cells.jsonl would corrupt it.
existing=$("$PYTHON" -m gauntlet.cli status 2>&1 || true)
if [[ "$existing" == *RUNNING* ]]; then
    log "a run is already in progress — nothing to do"
    echo "$existing"
    exit 0
fi

log "resuming $RUN_ID (quiet window, stop by $STOP_AT)"

# --no-overlay: nobody is at the machine, and the lamp would only add a poll loop.
"$PYTHON" -m gauntlet.cli run --resume "$RUN_ID" --no-overlay "${model_args[@]}" &
proc_pid=$!

stop_hhmm="${STOP_AT//:/}"
noted_6am=false

while kill -0 "$proc_pid" 2>/dev/null; do
    now_hhmm=$(date '+%H%M')
    if [[ "$now_hhmm" -ge "$stop_hhmm" ]]; then
        if [[ "$noted_6am" == false ]]; then
            log "quiet window closed ($STOP_AT) — stopping run"
            noted_6am=true
        fi
        kill "$proc_pid" 2>/dev/null || true
        wait "$proc_pid" 2>/dev/null || true
        sleep 5
        # A hard stop skips the in-process cleanup, so free the GPU explicitly.
        "$PYTHON" -m gauntlet.cli release
        break
    fi
    sleep 60
done

wait "$proc_pid" 2>/dev/null || true

log "done"
"$PYTHON" -m gauntlet.cli status
