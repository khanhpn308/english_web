#!/usr/bin/env bash

set -uo pipefail

MODE="${1:-fast}"

ROOT="$(git rev-parse --show-toplevel)" || {
    echo "T090 SANDBOX_BLOCKED: verification requires a Git working tree" >&2
    exit 2
}
if [[ -z "$ROOT" || "$ROOT" == "/" ]]; then
    echo "T090 SANDBOX_BLOCKED: invalid verification repository root" >&2
    exit 2
fi
cd "$ROOT"

RUN_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/.agent/runs/logs/$RUN_ID"
mkdir -p "$LOG_DIR"

declare -A PIDS
declare -A STATUS
declare -A SECONDS_USED
GATES=()
FAILED=0

start_gate() {
    local name="$1"
    shift

    GATES+=("$name")
    echo "[START] $name"

    (
        start=$(date +%s)
        "$@" >"$LOG_DIR/$name.log" 2>&1
        rc=$?
        end=$(date +%s)

        echo "$rc" >"$LOG_DIR/$name.rc"
        echo "$((end - start))" >"$LOG_DIR/$name.seconds"
        exit "$rc"
    ) &

    PIDS["$name"]=$!
    # In the constrained Docker verification profile each gate completes
    # before another begins. This bounds combined RAM and workspace pressure.
    if [[ "${T090_SANDBOX_LIMITED:-0}" == "1" ]]; then
        wait_gate "$name"
    fi
}

wait_gate() {
    local name="$1"
    local pid="${PIDS[$name]}"

    # A sequential sandbox already harvested this gate in start_gate().
    if [[ -n "${STATUS[$name]:-}" ]]; then
        return 0
    fi
    if wait "$pid"; then
        STATUS["$name"]="PASS"
    else
        STATUS["$name"]="FAIL"
        FAILED=1
    fi

    SECONDS_USED["$name"]="$(cat "$LOG_DIR/$name.seconds")"
}

wait_phase() {
    local name

    for name in "$@"; do
        wait_gate "$name"
    done

    if (( FAILED != 0 )); then
        echo
        echo "Phase failed; stopping later phases."
        print_summary
        # CI-only synthetic probe: source and logs are inside an isolated
        # container without mounted Host secrets. Disabled for ordinary runs.
        if [[ "${T090_SANDBOX_DIAGNOSTIC:-0}" == "1" ]]; then
            echo "[T090-DIAGNOSTIC] free filesystem capacity"
            df -h /workspace /tmp || true
            for gate in "${GATES[@]}"; do
                if [[ "${STATUS[$gate]:-}" == "FAIL" ]]; then
                    echo "[T090-DIAGNOSTIC] $gate (last 30 log lines)"
                    tail -n 30 "$LOG_DIR/$gate.log" || true
                fi
            done
        fi
        exit 1
    fi
}

print_summary() {
    echo
    echo "========================================"
    echo "GATE SUMMARY"
    echo "========================================"

    local name
    for name in "${GATES[@]}"; do
        if [[ -n "${STATUS[$name]:-}" ]]; then
            printf "%-24s %-5s %ss\n" \
                "$name" \
                "${STATUS[$name]}" \
                "${SECONDS_USED[$name]}"

            if [[ "${STATUS[$name]}" == "FAIL" ]]; then
                echo "  log: $LOG_DIR/$name.log"
            fi
        fi
    done
}

echo "Mode:   $MODE"
echo "Run ID: $RUN_ID"
echo "Logs:   $LOG_DIR"
echo

case "$MODE" in

    fast)
        start_gate portable-pytest \
            python -m pytest \
            --ignore=backend/tests/windows/test_source_paths.py \
            -n 10 \
            --no-cov

        start_gate typecheck npm run typecheck
        start_gate contract npm run test:contract

        wait_phase \
            portable-pytest \
            typecheck \
            contract
        ;;

    full)
        echo "=== PHASE 1: lightweight/static gates ==="

        start_gate format-check npm run format:check
        start_gate lint npm run lint
        start_gate typecheck npm run typecheck
        start_gate floor npm run floor:check
        start_gate contract npm run test:contract
        start_gate architecture npm run architecture:check
        start_gate security-code npm run security:code
        start_gate security-deps npm run security:deps
        start_gate security-secrets npm run security:secrets

        wait_phase \
            format-check \
            lint \
            typecheck \
            floor \
            contract \
            architecture \
            security-code \
            security-deps \
            security-secrets

        echo
        echo "=== PHASE 2: heavy test gates ==="

        # Leave CPU headroom for Vitest coverage.
        start_gate portable-pytest \
            python -m pytest \
            --ignore=backend/tests/windows/test_source_paths.py \
            -n 10

        start_gate frontend-coverage \
            npm run test:frontend:coverage

        wait_phase \
            portable-pytest \
            frontend-coverage

        echo
        echo "=== PHASE 3: artifacts/final checks ==="

        start_gate coverage-check npm run coverage:check
        start_gate build npm run build

        wait_phase \
            coverage-check \
            build
        ;;

    portable-task)
        echo "=== PHASE A: independent concurrent gates ==="

        start_gate check-fast-active npm run check:fast:active
        start_gate frontend-coverage npm run test:frontend:coverage
        if [[ "${T090_SANDBOX_LIMITED:-0}" == "1" ]]; then
            # Same test selection/coverage as npm's portable script; fewer
            # pytest-xdist workers to stay within a finite container budget.
            start_gate portable-pytest python -m pytest --ignore=backend/tests/windows -n 2
        else
            start_gate portable-pytest npm run test:python:portable
        fi
        start_gate security-secrets npm run security:secrets
        start_gate security-code npm run security:code
        start_gate security-deps npm run security:deps
        start_gate architecture npm run architecture:check

        wait_phase \
            check-fast-active \
            frontend-coverage \
            portable-pytest \
            security-secrets \
            security-code \
            security-deps \
            architecture

        echo
        echo "=== PHASE B: dependent coverage check ==="

        start_gate coverage-check npm run coverage:check

        wait_phase \
            coverage-check
        ;;

    *)
        echo "Usage: $0 {fast|full|portable-task}"
        exit 2
        ;;
esac

print_summary

echo
echo "RESULT: PASS"