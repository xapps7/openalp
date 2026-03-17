#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
VERSION="v0.1.0-mvp"
PKG="openalp-${VERSION}.tar.gz"

mkdir -p "$DIST"
"$ROOT/scripts/quality_gate.sh"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

mkdir -p "$TMPDIR/openalp"
cp -R "$ROOT/alp" "$TMPDIR/openalp/"
cp -R "$ROOT/spec" "$TMPDIR/openalp/"
cp -R "$ROOT/samples" "$TMPDIR/openalp/"
cp -R "$ROOT/docs" "$TMPDIR/openalp/"
cp -R "$ROOT/scripts" "$TMPDIR/openalp/"
cp -R "$ROOT/tests" "$TMPDIR/openalp/"
cp -R "$ROOT/web" "$TMPDIR/openalp/"
cp "$ROOT/README.md" "$ROOT/pyproject.toml" "$ROOT/LICENSE" "$ROOT/CHANGELOG.md" "$ROOT/.gitignore" "$TMPDIR/openalp/"
find "$TMPDIR/openalp" -depth -type d -name "__pycache__" -exec rm -rf {} \;

cat > "$TMPDIR/openalp/RELEASE.txt" <<REL
OpenALP ${VERSION}
Build date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Contents: runtime, CLI, web demos, samples, tests-backed spec docs
REL

tar -czf "$DIST/$PKG" -C "$TMPDIR" openalp

echo "created=$DIST/$PKG"
