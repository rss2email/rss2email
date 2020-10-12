#!/usr/bin/env bash

args=()
for arg in "$@"; do
  case "$arg" in
    --subprocess)
      echo 'Running each invocation of r2e in a separate process...'
      export SUBPROCESS=1
      ;;
    -s)
      echo 'Not suppressing output...'
      export NOCAPTURE=1
      ;;
    *)
      args+=("$arg")
      ;;
  esac
done

if [ "$SUBPROCESS" = "1" ] && [ "$NOCAPTURE" = "1" ]; then
  echo "-s and --subprocess flags are incompatible"
  exit 1
fi

if [ "$SUBPROCESS" != "1" ]; then
  echo "NOTE: Run with --subprocess flag for better test isolation."
fi

cd test || exit 1
python -m unittest "${args[@]}"
