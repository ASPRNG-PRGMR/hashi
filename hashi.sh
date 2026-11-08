#!/usr/bin/env bash
#
# HASHI launcher: build what is present, run every check, and report.
#
# The default target is `check`, which builds and verifies and touches no
# device. Running the host itself is a separate, explicit target, because it
# sends bytes to the iPad and creates a Mutter session — a monitor appears on
# the desktop and a screen-sharing indicator shows.
#
# Usage:
#   ./hashi.sh                 # same as `check`
#   ./hashi.sh check           # build everything present, run all checks
#   ./hashi.sh build           # build only
#   ./hashi.sh test            # the three test suites, no conformance
#   ./hashi.sh conformance     # the cross-implementation byte comparison
#   ./hashi.sh plan            # print what a run would do; touches nothing
#   ./hashi.sh devices         # ask the local usbmuxd what is attached
#   ./hashi.sh run [args...]   # the real thing; needs --allow-session
#   ./hashi.sh clean           # remove both build trees
#
# plan, devices and run drive the PYTHON host, because that is the
# implementation that has actually worked (FED-HOST-E001). The native binary
# is the same three commands with a `native-` prefix; it has never been run.
#
#   ./hashi.sh native-plan
#   ./hashi.sh native-devices
#   ./hashi.sh native-run [args...]

set -o errexit
set -o nounset
set -o pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly NATIVE_BUILD="${ROOT}/native/build"
readonly HASHI_BIN="${NATIVE_BUILD}/hashi"

# Colour only when stdout is a terminal, so logs stay readable when piped.
if [[ -t 1 ]]; then
    readonly BOLD=$'\e[1m' DIM=$'\e[2m' RED=$'\e[31m' GREEN=$'\e[32m' OFF=$'\e[0m'
else
    readonly BOLD='' DIM='' RED='' GREEN='' OFF=''
fi

step()  { printf '%s==>%s %s\n' "${BOLD}" "${OFF}" "$*"; }
note()  { printf '%s    %s%s\n' "${DIM}" "$*" "${OFF}"; }
fail()  { printf '%s!!!%s %s\n' "${RED}" "${OFF}" "$*" >&2; exit 1; }
ok()    { printf '%s  ok%s %s\n' "${GREEN}" "${OFF}" "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# --- build -----------------------------------------------------------------

build_native() {
    have cmake || fail "cmake is not installed, so the C++ core cannot be built"
    step "Building the C++ core"
    cmake -S "${ROOT}/native" -B "${NATIVE_BUILD}" >/dev/null
    cmake --build "${NATIVE_BUILD}" -j >/dev/null
    ok "native/build"
}

build_rust() {
    if ! have cargo; then
        note "cargo is not installed, so the Rust core is skipped"
        return 0
    fi
    step "Building the Rust core"
    # --offline on purpose: the crate has no dependencies, so a build must
    # never need the network. If this ever fails for want of a crate, that is
    # a dependency that crept in.
    ( cd "${ROOT}/rust" && cargo build --offline --release >/dev/null 2>&1 )
    ok "rust/target/release"
}

# --- checks ----------------------------------------------------------------

test_python() {
    step "Python reference suite"
    # Named explicitly: python/tests has no __init__.py, so plain discovery
    # finds nothing.
    ( cd "${ROOT}/python" && python3 -m unittest \
        tests.test_hashi_framing tests.test_hashi_mode tests.test_hashi_startup \
        tests.test_hashi_stream tests.test_hashi_jpeg tests.test_hashi_usbmux \
        tests.test_hashi_gnome tests.test_hashi_host tests.test_hashi_cli \
        2>&1 | tail -3 )
}

test_native() {
    step "C++ test binaries"
    # ctest rather than running each binary, so a new target is picked up
    # without editing this script.
    ctest --test-dir "${NATIVE_BUILD}" --output-on-failure | tail -3
}

test_rust() {
    have cargo || return 0
    step "Rust test suite"
    # Named explicitly rather than plain `cargo test`: that also runs the
    # doc-test and unit-test suites, which are empty here, and the last
    # "test result" line would then report 0 passed and look like a loss.
    ( cd "${ROOT}/rust" && cargo test --offline --quiet --test protocol 2>&1 \
        | grep "test result" )
}

run_conformance() {
    step "Cross-implementation conformance"
    note "the Python modules are the reference; the ports must match their bytes"
    python3 "${ROOT}/native/tools/conformance.py"
}

# --- the host ---------------------------------------------------------------

require_binary() {
    [[ -x "${HASHI_BIN}" ]] || fail "${HASHI_BIN} is missing; run './hashi.sh build' first"
}

# The Python host needs its own directory on sys.path, since the modules import
# each other by bare name.
python_host() {
    local command="$1"
    shift
    ( cd "${ROOT}/python" && exec python3 hashi_cli.py "${command}" "$@" )
}

# --- targets ----------------------------------------------------------------

target_build() {
    build_native
    build_rust
}

target_test() {
    test_python
    test_native
    test_rust
}

target_check() {
    target_build
    target_test
    run_conformance
    printf '\n'
    ok "everything present was built and checked"
    note "nothing here contacted the device or created a session"
    note "to see what a run would do:  ./hashi.sh plan"
}

target_clean() {
    step "Removing build trees"
    rm -rf "${NATIVE_BUILD}"
    [[ -d "${ROOT}/rust/target" ]] && rm -rf "${ROOT}/rust/target"
    ok "clean"
}

main() {
    local target="${1:-check}"
    [[ $# -gt 0 ]] && shift
    case "${target}" in
        check)        target_check ;;
        build)        target_build ;;
        test)         target_test ;;
        conformance)  run_conformance ;;
        clean)        target_clean ;;
        plan|devices)
            python_host "${target}" "$@"
            ;;
        run)
            # The CLI enforces --allow-session itself; this only makes the
            # consequences visible before the flag is read.
            note "run sends bytes to the iPad and creates a Mutter session:"
            note "a monitor appears and a screen-sharing indicator shows"
            python_host run "$@"
            ;;
        native-plan|native-devices)
            require_binary
            exec "${HASHI_BIN}" "${target#native-}" "$@"
            ;;
        native-run)
            require_binary
            note "the native host has NEVER been run; treat this as an experiment"
            note "it sends bytes to the iPad and creates a Mutter session"
            exec "${HASHI_BIN}" run "$@"
            ;;
        -h|--help|help)
            # From line 3 to the end of the leading comment block, so the
            # usage text cannot drift out of sync with the help output.
            awk 'NR < 3 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' \
                "${BASH_SOURCE[0]}"
            ;;
        *)
            fail "unknown target '${target}'; try './hashi.sh --help'"
            ;;
    esac
}

main "$@"
