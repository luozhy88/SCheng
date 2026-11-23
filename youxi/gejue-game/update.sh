#!/bin/bash
# 把 youxi 重新生成的游戏同步到本项目的 public/index.html
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$DIR/../gejue-game.html" "$DIR/public/index.html"
echo "updated: $DIR/public/index.html"
