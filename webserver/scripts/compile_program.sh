#!/bin/bash
# Build generated IEC 61131-3 logic and the runtime with the same compiler pass.
set -euo pipefail

fail() {
    echo "Error: $*" >&2
    echo "Compilation finished with errors!" >&2
    exit 1
}

if [[ $# -ne 1 || "$1" != *.st || "$1" == */* ]]; then
    fail "Provide one Structured Text filename from webserver/st_files (e.g. blank_program.st)"
fi

CALLER_DIR="$PWD"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WEBSERVER_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
REPO_DIR=$(cd -- "$WEBSERVER_DIR/.." && pwd)
PROGRAM="$1"
[[ -f "$WEBSERVER_DIR/st_files/$PROGRAM" ]] || fail "Structured Text file not found: $PROGRAM"

OPENPLC_PLATFORM=$(cat "$SCRIPT_DIR/openplc_platform")
OPENPLC_DRIVER=$(cat "$SCRIPT_DIR/openplc_driver")
ETHERCAT_OPT=""
if [[ -f "$SCRIPT_DIR/ethercat" ]]; then
    ETHERCAT_OPT=$(cat "$SCRIPT_DIR/ethercat")
fi

case "$OPENPLC_PLATFORM" in
    win) COMPILER="${CXX:-g++}" ;;
    linux|rpi) COMPILER="${CXX:-clang++-14}" ;;
    *) fail "Undefined platform: $OPENPLC_PLATFORM (expected win, linux or rpi)" ;;
esac
command -v "$COMPILER" >/dev/null 2>&1 || fail "Compiler not found: $COMPILER. Install it or set CXX."

INSTRUMENT_FLAGS=()
if [[ "$OPENPLC_PLATFORM" != win ]]; then
    case "${OPENPLC_INSTRUMENTATION:-1}" in
        1)
            INSTRUMENT_PASS="${OPENPLC_INSTRUMENTATION_PASS:-$REPO_DIR/instrument.so}"
            if [[ "$INSTRUMENT_PASS" != /* ]]; then
                INSTRUMENT_PASS="$CALLER_DIR/$INSTRUMENT_PASS"
            fi
            [[ -f "$INSTRUMENT_PASS" ]] || fail "Instrumentation pass not found: $INSTRUMENT_PASS. Set OPENPLC_INSTRUMENTATION_PASS to a compatible build."
            INSTRUMENT_FLAGS=(-fno-discard-value-names -flegacy-pass-manager -g
                              -Xclang -load -Xclang "$INSTRUMENT_PASS")
            ;;
        0) echo "Instrumentation disabled: building an uninstrumented baseline." ;;
        *) fail "OPENPLC_INSTRUMENTATION must be 0 or 1" ;;
    esac
fi

for TOOL in "$WEBSERVER_DIR/st_optimizer" "$WEBSERVER_DIR/iec2c" "$WEBSERVER_DIR/core/glue_generator"; do
    [[ -x "$TOOL" ]] || fail "Build tool missing or not executable: $TOOL. Run the installer first."
done

COMPILE_FLAGS=(-std=gnu++11 -I ./lib -w)
LINK_FLAGS=(-pthread -fpermissive)
if [[ "$OPENPLC_PLATFORM" == win ]]; then
    LINK_FLAGS+=(-I /usr/local/include/modbus -L /usr/local/lib -lmodbus)
else
    command -v pkg-config >/dev/null 2>&1 || fail "pkg-config is required"
    MODBUS_CONFIG=$(pkg-config --cflags --libs libmodbus) || fail "libmodbus development files not found by pkg-config"
    read -r -a MODBUS_FLAGS <<< "$MODBUS_CONFIG"
    LINK_FLAGS+=("${MODBUS_FLAGS[@]}" -lasiodnp3 -lasiopal -lopendnp3 -lopenpal)
    if [[ "$OPENPLC_PLATFORM" == rpi ]]; then
        LINK_FLAGS+=(-lrt -lwiringPi)
        [[ "$OPENPLC_DRIVER" != sequent ]] || COMPILE_FLAGS+=(-DSEQUENT)
    elif [[ "$OPENPLC_DRIVER" == sl_rp4 ]]; then
        COMPILE_FLAGS+=(-DSL_RP4)
    fi
fi

if [[ "$ETHERCAT_OPT" == ethercat ]]; then
    COMPILE_FLAGS+=(-I../../utils/ethercat_src/src -D_ethercat_src)
    LINK_FLAGS+=(-L../../utils/ethercat_src/build/lib -lethercat_src)
fi

cd -- "$WEBSERVER_DIR"
echo "Optimizing ST program..."
./st_optimizer "./st_files/$PROGRAM" "./st_files/$PROGRAM" || fail "ST optimization failed"
echo "Generating C files..."
./iec2c -f -l -p -r -R -a "./st_files/$PROGRAM" || fail "Error generating C files"

if [[ "$ETHERCAT_OPT" == ethercat ]]; then
    sed -i '7s/^/#include "ethercat_src.h" /' Res0.c
fi
mv -f POUS.c POUS.h LOCATED_VARIABLES.h VARIABLES.csv Config0.c Config0.h Res0.c ./core/ || fail "Error moving generated files"

cd core
echo "Compiling for $OPENPLC_PLATFORM with $COMPILER"
"$COMPILER" "${INSTRUMENT_FLAGS[@]}" "${COMPILE_FLAGS[@]}" -c Config0.c -o Config0.o || fail "Error compiling Config0.c"
"$COMPILER" "${INSTRUMENT_FLAGS[@]}" "${COMPILE_FLAGS[@]}" -c Res0.c -o Res0.o || fail "Error compiling Res0.c"
echo "Generating glueVars..."
./glue_generator || fail "Error generating glueVars"
echo "Compiling main program..."
# Preserve the last working executable and active program when linking fails.
trap 'rm -f -- openplc.new' EXIT
"$COMPILER" "${INSTRUMENT_FLAGS[@]}" "${COMPILE_FLAGS[@]}" *.cpp Config0.o Res0.o -o openplc.new "${LINK_FLAGS[@]}" || fail "Error linking runtime"
mv -f -- openplc.new openplc
printf '%s\n' "$PROGRAM" > "$WEBSERVER_DIR/active_program"
echo "Compilation finished successfully!"
