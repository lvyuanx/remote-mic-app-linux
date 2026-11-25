#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR/frontend"
if command -v corepack >/dev/null 2>&1; then
    corepack pnpm install --frozen-lockfile
    corepack pnpm build
else
    pnpm install --frozen-lockfile
    pnpm build
fi
mkdir -p "$PROJECT_DIR/sayall_linux/web"
cp -r "$PROJECT_DIR/frontend/dist/." "$PROJECT_DIR/sayall_linux/web/"
