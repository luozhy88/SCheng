#!/bin/bash
# 把 youxi 重新生成的页面同步到本项目的 public/
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$DIR/../gejue-game.html" "$DIR/public/index.html"
echo "updated: $DIR/public/index.html"
if [ -f "$DIR/../wrong.html" ]; then
  cp "$DIR/../wrong.html" "$DIR/public/wrong.html"
  echo "updated: $DIR/public/wrong.html"
fi
