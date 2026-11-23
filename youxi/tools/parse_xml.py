# -*- coding: utf-8 -*-
"""解析 input/zhuli.xml（生词本格式）为歌诀记忆游戏的结构化数据。"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
XML = BASE / "input" / "zhuli.xml"
OUT = BASE / "tools" / "gejue-data.json"

LOC_KEYWORDS = ("乌", "老家", "亚朵", "杭州", "图书馆", "大学", "小学", "中学", "医院",
                "酒店", "邮局", "银行", "食堂", "宿舍", "礼堂", "楼梯", "扶梯", "楼道",
                "门口", "门前", "门后", "墙", "电梯", "广场", "柱", "棚", "柜", "ATM",
                "玻璃", "房", "箭头", "车位", "前台", "卖部", "豆腐脑", "书店", "房顶",
                "操场", "进门", "正门", "旁边", "对面", "里面", "左边", "右边", "前面",
                "后面", "中间", "走廊", "路口", "楼下", "楼上", "学校", "商店", "打印",
                "停车", "台阶", "走道", "北墙", "东墙", "保险柜", "柜台", "草坪", "马路",
                "广场", "食堂", "宿舍", "门口", "门", "操场", "亭", "宿舍", "柱")
PUNCT = "，,。.;；、·!！?？:：-—…~～ \t"
JUE_CHARS = re.compile(r"[^0-9A-Za-z\u4e00-\u9fa5]")
FORMULA_SUFFIX = re.compile(r"^[\u4e00-\u9fa5]{2,12}(汤|丸|散|饮|煎|丹|膏|方|酒|露|片|汁|胶|囊)$")
BRACKET_RE = re.compile(r"【([^】]*)】")
FULLTITLE = ""


def clean_line(s):
    s = s.strip()
    s = re.sub(r"[;；]+\s*$", "", s).strip()
    return s


def strip_punct(s):
    return "".join(c for c in s if c not in PUNCT)


def norm_jue(s):
    return JUE_CHARS.sub("", s or "")


def looks_like_loc(s):
    return any(k in s for k in LOC_KEYWORDS)


def strip_brackets(text):
    return BRACKET_RE.sub(lambda m: m.group(1), text).strip()


def remove_brackets(text):
    return BRACKET_RE.sub("", text).strip()


def parse_loc_jue(inner):
    """括号/横线内容 → (地点, 歌诀或None)。含地点关键词的段为地点，其余拼作歌诀。"""
    parts = [p.strip() for p in re.split(r"[-—]", inner)]
    parts = [strip_brackets(p) for p in parts if p.strip()]
    cleaned = []
    for p in parts:
        p = re.sub(r"[（(][^（）()]*[)）]", "", p).strip()
        if p and not re.search(r"[()（）]", p):
            cleaned.append(p)
    locs, jues = [], []
    for p in cleaned:
        (locs if looks_like_loc(p) else jues).append(p)
    anchor = "，".join(locs)
    jue = norm_jue("".join(jues)) if jues else None
    if jue and not (1 <= len(jue) <= 12):
        jue = None
    return anchor, jue


def split_formula(text):
    """证型-方剂[-提示字]；兼容全角冒号与【证型】前缀。失败返回 None。"""
    text = strip_brackets(text).strip().strip(";；")
    m = re.match(r"^(?P<s>.{2,26}?)[-—](?P<r>.+)$", text)
    if not m:
        m = re.match(r"^(?P<s>[\u4e00-\u9fa5]{2,12})[:：](?P<r>.{2,})$", text)
        if not m:
            return None
    syndrome = m.group("s").strip(" ：:")
    if "：" in syndrome or ":" in syndrome:
        l, r = re.split(r"[:：]", syndrome, maxsplit=1)
        if 2 <= len(l) <= 12:
            syndrome = l
            text = r + "-" + m.group("r")
            m = re.match(r"^(?P<s>.{2,26}?)[-—](?P<r>.+)$", text)
            if not m:
                return None
            syndrome = m.group("s").strip(" ：:")
    rest = m.group("r").strip()
    parts = [p.strip() for p in rest.split("-")]
    formula = parts[0]
    hint = None
    if len(parts) > 1 and len(norm_jue(parts[1])) == 1:
        hint = norm_jue(parts[1])
    return {"syndrome": syndrome, "formula": formula, "hint": hint}


def common_prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def is_subsequence(s, t):
    it = iter(t)
    return all(c in it for c in s)


NAME_STRIP = " ：:;；、，,!！?？."


def split_item(word, trans):
    global FULLTITLE
    lines = [clean_line(l) for l in trans.splitlines()]
    lines = [l for l in lines if l]
    full_title = strip_punct(clean_line(word))
    FULLTITLE = full_title
    title = full_title[:12]
    sections, knowledge = [], []
    cur = None
    last_name = ""

    def ensure_cur():
        nonlocal cur
        if cur is None:
            cur = {"name": title, "anchor": "", "jue": None, "formulas": []}
        return cur

    def close_cur():
        nonlocal cur
        if cur is not None:
            if cur["jue"] or cur["anchor"] or cur["formulas"]:
                sections.append(cur)
            cur = None

    def fresh(sec):
        return sec is not None and not sec["formulas"] and not sec["jue"] and not sec["anchor"]

    def detect_name(bn):
        """判断 bn 是否为小节疾病名（子串/前缀/子序列匹配词条标题）。"""
        if not bn:
            return ""
        if (bn in full_title or full_title.startswith(bn)
                or common_prefix_len(bn, full_title) >= 3
                or (len(bn) >= 3 and is_subsequence(bn, full_title))):
            return bn
        return ""

    def new_section(name, anchor, jue):
        nonlocal cur, last_name
        close_cur()
        cur = {"name": name or (last_name or title),
               "anchor": anchor, "jue": jue, "formulas": []}
        if name and name != title:
            last_name = name

    for raw in lines:
        # 去掉闭括号后的尾冒号/分号："...）：" → "...）"
        raw = re.sub(r"[)）]\s*[:：;；]+$", "）", raw)

        # ---- A) 名称-中间-【歌诀】 ----
        m = re.match(r"^(?P<name>[^-—（()【】]{2,15}?)-(?P<mid>[^-—【】]{2,30}?)-【(?P<jue>[^】]{1,12})】$", raw)
        if m:
            anchor, _ = parse_loc_jue(m.group("mid"))
            new_section(m.group("name").strip("：: "), anchor or m.group("mid").strip(),
                        norm_jue(m.group("jue")) or None)
            continue

        # ---- B) 含括号的行：最外层优先，失败回退最后一组括号 ----
        groups = list(re.finditer(r"[（(]([^（）()]*)[)）]", raw))
        if groups:
            opens = [i for i in (raw.find("（"), raw.find("(")) if i != -1]
            outer_open = min(opens)
            cand = []
            if raw[-1] in "）)":
                cand.append((remove_brackets(raw[:outer_open]), raw[outer_open + 1:-1].strip()))
            g = groups[-1]
            before_fb = remove_brackets(re.sub(r"[（(][^（）()]*[)）]", "", raw[:g.start()]))
            cand.append((before_fb, g.group(1).strip()))

            chosen = None
            for before_raw, inner in cand:
                if not inner or re.search(r"[()（）]", re.sub(r"[（(][^（）()]*[)）]", "", inner)):
                    continue
                a, j = parse_loc_jue(inner)
                if not (a or j):
                    continue
                has_dash = ("-" in inner) or ("—" in inner)
                if not has_dash and not looks_like_loc(strip_brackets(inner)):
                    continue  # 无横线非地点（如别名夹注）→ 不算锚点
                before = before_raw.strip(NAME_STRIP)
                before_norm = re.sub(r"[、，,]", "", before)
                chosen = (before, before_norm, a, j)
                break

            if chosen:
                before, before_norm, anchor, jue = chosen
                name = ""
                if before_norm:
                    if looks_like_loc(before_norm):
                        anchor = before_norm + ("，" + anchor if anchor else "")
                    else:
                        name = detect_name(before_norm)
                        if not name and 2 <= len(norm_jue(before_norm)) <= 12:
                            jue = jue or norm_jue(before_norm)
                if jue and fresh(cur) and not name:
                    cur["anchor"] = anchor or cur["anchor"]
                    cur["jue"] = jue
                    continue
                new_section(name, anchor, jue)
                continue

            # 注释路径：剥掉【】保留括号内容作备注
            note = strip_brackets(raw).strip(" ：:;；")
            before0 = remove_brackets(raw[:outer_open]).strip(NAME_STRIP)
            bn = re.sub(r"[、，,]", "", before0)
            nm = detect_name(bn)
            if nm:
                new_section(nm, "", None)
            if note:
                ensure_cur()["formulas"].append({"note": note})
            continue

        # ---- C) 无括号：横线行（地点-歌诀 / 名-歌诀-地点 / 歌诀-地点 / 证型-方剂）----
        if re.search(r"[-—]", raw):
            parts = [p.strip() for p in re.split(r"[-—]", raw)]
            if (len(parts) >= 3 and looks_like_loc(parts[-1])
                    and len(norm_jue(parts[-1])) >= 2):
                anchor = parts[-1]
                jue = norm_jue("".join(parts[1:-1]))
                nm = parts[0] if 2 <= len(norm_jue(parts[0])) <= 12 else ""
                if jue and fresh(cur) and not nm:
                    cur["anchor"], cur["jue"] = anchor, jue
                    continue
                new_section(nm, anchor, jue or None)
                continue
            # 两段：歌诀-地点（如 六鬼左右-乌图书馆一楼楼梯）
            if (len(parts) == 2 and looks_like_loc(parts[1])
                    and not looks_like_loc(parts[0])
                    and 2 <= len(norm_jue(parts[0])) <= 12
                    and not FORMULA_SUFFIX.match(parts[1])):
                jue = norm_jue(parts[0])
                if jue and fresh(cur):
                    cur["anchor"], cur["jue"] = parts[1], jue
                    continue
                new_section("", parts[1], jue or None)
                continue
            fm = split_formula(raw)
            if fm and looks_like_loc(fm["syndrome"]) and not fm["hint"]:
                anchor, jue = parse_loc_jue(raw)
                if jue and fresh(cur):
                    cur["anchor"], cur["jue"] = anchor, jue
                    continue
                new_section("", anchor, jue)
                continue
            if fm:
                ensure_cur()["formulas"].append(fm)
                continue

        # ---- D) 裸方剂名 ----
        text = strip_brackets(raw).strip(" ：:;；")
        if FORMULA_SUFFIX.match(text):
            ensure_cur()["formulas"].append({"syndrome": "", "formula": text})
            continue

        # ---- E) 小节标题（含中间冒号的定义行不算标题；与当前歌诀同名 → 跳过） ----
        core = text.strip(" ：:;；")
        if cur and cur["jue"] and norm_jue(core) == cur["jue"]:
            continue
        if (2 <= len(core) <= 14 and not re.search(r"[，,。.]", core)
                and not re.search(r"[:：]", core)):
            close_cur()
            cur = {"name": core, "anchor": "", "jue": None, "formulas": []}
            if core != title:
                last_name = core
            continue

        # ---- F) 备注 ----
        ensure_cur()["formulas"].append({"note": text})

    close_cur()

    # ---- 后处理 ----
    def is_size_name(nm):
        return nm.startswith(("大于", "小于"))

    # 1) 同名空小节并入前一小节（带走锚点/歌诀）
    merged = []
    for s in sections:
        if (merged and s["name"] == merged[-1]["name"] and not s["formulas"]
                and (s["jue"] or s["anchor"])):
            merged[-1]["anchor"] = s["anchor"] or merged[-1]["anchor"]
            merged[-1]["jue"] = s["jue"] or merged[-1]["jue"]
            continue
        merged.append(s)

    # 2) 同词条内歌诀去重：保留方剂多者；名称从小节名/被弃者择优
    final = []
    for s in merged:
        dup = next((x for x in final if x["jue"] and x["jue"] == s["jue"]), None)
        if dup:
            keep, drop = (dup, s) if len(dup["formulas"]) >= len(s["formulas"]) else (s, dup)
            if keep is s:
                final[final.index(dup)] = s
            if (is_size_name(keep["name"]) or keep["name"] == title) \
                    and not is_size_name(drop["name"]) and drop["name"] != title:
                keep["name"] = drop["name"]
            if not keep["anchor"]:
                keep["anchor"] = drop["anchor"]
            if dup is not keep:
                pass
            continue
        final.append(s)
    # 清理：去掉没有歌诀/锚点且没有方剂的小节
    sections = [s for s in final if s["jue"] or s["anchor"] or s["formulas"]]

    if sections and sections[0]["name"] == title and not sections[0]["jue"] \
            and not sections[0]["anchor"]:
        if not sections[0]["formulas"]:
            sections.pop(0)
    if not sections:
        knowledge = [strip_brackets(l) for l in lines]
    return {"id": full_title, "title": full_title, "sections": sections, "knowledge": knowledge}


def main():
    text = XML.read_text(encoding="utf-8-sig")
    items = re.findall(r"<item>(.*?)</item>", text, re.S)
    entries, seen = [], set()
    for it in items:
        wm = re.search(r"<word>(.*?)</word>", it, re.S)
        tm = re.search(r"<trans><!\[CDATA\[(.*?)\]\]></trans>", it, re.S)
        if not wm or not tm:
            continue
        e = split_item(wm.group(1), tm.group(1))
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        entries.append(e)

    OUT.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    n_jue = sum(1 for e in entries for s in e["sections"] if s["jue"])
    n_sec = sum(len(e["sections"]) for e in entries)
    n_know = sum(1 for e in entries if e["knowledge"])
    print(f"词条 {len(entries)}  小节 {n_sec}  含歌诀 {n_jue}  知识卡 {n_know}")
    for e in entries:
        marks = [f"[{s['name']}|{s['anchor']}|{s['jue'] or '-'}|{len(s['formulas'])}]"
                 for s in e["sections"]]
        print(e["title"], " ".join(marks), ("K" + str(len(e["knowledge"])) if e["knowledge"] else ""))


if __name__ == "__main__":
    sys.exit(main())
