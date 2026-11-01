#!/usr/bin/env bash
#
# Build the tree that is synced to the bucket.
#
# Usage: prepare-dist.sh <out-dir> <dist-dir> [asset-prefix]
#
# The optional asset prefix relocates _next so this build can share a host with
# another Next.js site. It must be a single path segment with a leading slash.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

OUT_ARG="${1:?usage: prepare-dist.sh <out-dir> <dist-dir> [asset-prefix]}"
DIST_ARG="${2:?usage: prepare-dist.sh <out-dir> <dist-dir> [asset-prefix]}"
PREFIX="${3:-}"

if [ -n "$PREFIX" ]; then
  if ! printf '%s' "$PREFIX" | grep -Eq '^/[A-Za-z0-9._-]+$'; then
    echo "asset prefix must look like /authorize-static (got: $PREFIX)" >&2
    exit 1
  fi
fi

if [ ! -d "$OUT_ARG" ]; then
  echo "build output not found: $OUT_ARG" >&2
  exit 1
fi

OUT_DIR="$(realpath -e "$OUT_ARG")"
DIST_DIR="$(realpath -m "$DIST_ARG")"

case "$OUT_DIR" in
  "$ROOT"/*) ;;
  *) echo "out dir must be inside $ROOT (got: $OUT_DIR)" >&2; exit 1 ;;
esac

case "$DIST_DIR" in
  "$ROOT"/*) ;;
  *) echo "dist dir must be inside $ROOT (got: $DIST_DIR)" >&2; exit 1 ;;
esac

DIST_BASE="$(basename "$DIST_DIR")"
case "$DIST_BASE" in
  dist | dist-*) ;;
  *) echo "dist dir must be named dist or dist-* (got: $DIST_BASE)" >&2; exit 1 ;;
esac

if [ "$DIST_DIR" = "$ROOT" ] || [ "$DIST_DIR" = "$OUT_DIR" ]; then
  echo "refusing to delete $DIST_DIR" >&2
  exit 1
fi

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
cp -r "$OUT_DIR/." "$DIST_DIR/"

if [ -n "$PREFIX" ]; then
  mkdir -p "$DIST_DIR$PREFIX"
  mv "$DIST_DIR/_next" "$DIST_DIR$PREFIX/_next"
fi

for page in authorize/index.html pt/authorize/index.html en/authorize/index.html; do
  if [ ! -f "$DIST_DIR/$page" ]; then
    echo "missing $DIST_DIR/$page" >&2
    exit 1
  fi
done

EXPECTED="/_next/"
if [ -n "$PREFIX" ]; then
  EXPECTED="$PREFIX/_next/"
fi

if ! grep -q "$EXPECTED" "$DIST_DIR/pt/authorize/index.html"; then
  echo "HTML does not reference $EXPECTED" >&2
  exit 1
fi

echo "prepared $DIST_DIR (asset prefix: ${PREFIX:-none})"
