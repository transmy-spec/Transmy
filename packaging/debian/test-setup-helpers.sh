#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TEST_SCRIPT=$(mktemp)
cleanup() { rm -f "$TEST_SCRIPT"; }
trap cleanup EXIT INT TERM

sed '/^setup()/,$d' "$SCRIPT_DIR/transmy" >"$TEST_SCRIPT"
cat >>"$TEST_SCRIPT" <<'EOF'
address=$(detect_private_ipv4)
validate_ipv4 "$address"

automatic=$(prompt_value_timeout "Mode" "local" 1 </dev/null)
[ "$automatic" = local ]

selected=$(printf 'public\n' | prompt_value_timeout "Mode" "local" 1)
[ "$selected" = public ]

printf 'Detected and validated private IPv4 address: %s\n' "$address"
EOF

sh "$TEST_SCRIPT"
