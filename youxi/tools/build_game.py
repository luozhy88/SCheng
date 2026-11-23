# -*- coding: utf-8 -*-
"""把 tools/gejue-data.json 注入模板，生成自包含的 gejue-game.html。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TPL = BASE / "tools" / "game_template.html"
DATA = BASE / "tools" / "gejue-data.json"
OUT = BASE / "gejue-game.html"

data_json = DATA.read_text(encoding="utf-8")
html = TPL.read_text(encoding="utf-8")
assert "__DATA_JSON__" in html, "模板缺少占位符"
html = html.replace("__DATA_JSON__", data_json)
OUT.write_text(html, encoding="utf-8")
print(f"written {OUT} ({OUT.stat().st_size} bytes)")
