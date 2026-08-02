#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音「合集/合辑」视频批量下载脚本
==================================
功能：
  1. 用无头浏览器打开抖音合集页，自动点击"加载更多"翻页，拦截接口拿到全部视频直链
  2. 解析每集标题（第N天《方剂名》），重命名为 第NNN天_方剂名.mp4
  3. 并发下载到 output/video/ 目录，支持断点续传（已存在的有效文件自动跳过）

依赖：Python 3.8+，脚本会自动创建 .venv_dl 虚拟环境并安装 playwright
      （首次运行会自动下载无头浏览器，约 150MB，仅需一次）

用法：
  python3 download_douyin_collection.py [合集ID或URL] [输出目录]

示例：
  python3 download_douyin_collection.py                        # 默认下载"王点点-中医方剂"合集
  python3 download_douyin_collection.py 7627689248653346816 output/video
  python3 download_douyin_collection.py "https://www.douyin.com/collection/7627689248653346816"
"""
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(SCRIPT_DIR, ".venv_dl")
DEFAULT_MIX_ID = "7627689248653346816"          # 王点点-自学中医「中医方剂歌诀」合集
DEFAULT_OUT = os.path.join(os.path.dirname(SCRIPT_DIR), "output", "video")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
ILLEGAL = re.compile(r'[\\/:*?"<>|\n\r\t]')

bodies = []          # 拦截到的 mix 接口响应
cookies = []         # 会话 cookies（备用）


# ---------------------------------------------------------------------------
# 环境准备：venv + playwright
# ---------------------------------------------------------------------------
def ensure_env():
    """确保 .venv_dl 虚拟环境里有 playwright。"""
    py = os.path.join(VENV_DIR, "bin", "python")
    if not os.path.exists(py):
        print("[env] 创建虚拟环境 .venv_dl ...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
        subprocess.run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=False)
    try:
        subprocess.run([py, "-c", "import playwright"], check=True,
                       capture_output=True)
    except subprocess.CalledProcessError:
        print("[env] 安装 playwright ...")
        subprocess.run([py, "-m", "pip", "install", "-q", "playwright"], check=True)
    return py


def find_chromium():
    """在 ms-playwright 缓存里找可用的 Chromium 可执行文件。"""
    cache = os.path.expanduser("~/Library/Caches/ms-playwright")
    if not os.path.isdir(cache):
        return None
    candidates = []
    for root, dirs, files in os.walk(cache):
        for f in files:
            if f in ("Chromium", "chrome-headless-shell",
                     "Google Chrome for Testing"):
                candidates.append(os.path.join(root, f))
    if candidates:
        # 取路径层级最深(即最新版本)的
        return max(candidates, key=lambda p: p.count(os.sep))
    return None


# ---------------------------------------------------------------------------
# 枚举合集（无头浏览器 + 拦截接口）
# ---------------------------------------------------------------------------
def on_response(resp):
    if "aweme/v1/web/mix/aweme" in resp.url:
        try:
            if "json" in resp.headers.get("content-type", ""):
                body = resp.text()
                if "aweme_list" in body:
                    bodies.append({"url": resp.url, "body": body})
        except Exception:
            pass


def enumerate_collection(mix_id, py):
    sys.path.insert(0, os.path.join(VENV_DIR, "lib",
                                    f"python{sys.version_info.major}.{sys.version_info.minor}",
                                    "site-packages"))
    from playwright.sync_api import sync_playwright

    url = mix_id if mix_id.startswith("http") else f"https://www.douyin.com/collection/{mix_id}"
    exe = find_chromium()

    with sync_playwright() as p:
        launch_kwargs = dict(headless=True,
                             args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        if exe:
            launch_kwargs["executable_path"] = exe
        else:
            print("[env] 未找到本地 Chromium，尝试用 playwright 自带浏览器 ...")
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 900},
                                  locale="zh-CN")
        page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print("[warn] 页面加载提示:", e)
        time.sleep(8)

        def click_load_more():
            return page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('*')).filter(e =>
                    e.innerText && e.innerText.includes('加载更多') && e.children.length === 0);
                if (els.length) { els[0].click(); return true; }
                return false;
            }""")

        def scroll_container():
            page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('*')).filter(e => {
                    const s = getComputedStyle(e);
                    return (s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 50;
                });
                if (!els.length) return;
                const c = els[0];
                const step = () => { c.scrollTop += 1500;
                    if (c.scrollTop < c.scrollHeight - c.clientHeight) setTimeout(step, 120); };
                step();
            }""")

        def episode_count():
            return page.evaluate("""() => {
                const t = document.body.innerText;
                const m = t.match(/第\\d+集/g);
                return m ? new Set(m).size : 0;
            }""")

        prev, stall = 0, 0
        while stall < 5:
            scroll_container()
            time.sleep(2.5)
            clicked = click_load_more()
            time.sleep(3)
            n = episode_count()
            print(f"[enum] 已加载 {n} 集  接口响应 {len(bodies)} 个  点击加载: {clicked}")
            if n == prev and not clicked:
                stall += 1
            else:
                stall = 0
            prev = n
        cookies = ctx.cookies()
        browser.close()
    return cookies


# ---------------------------------------------------------------------------
# 解析与清单
# ---------------------------------------------------------------------------
def normalize(desc):
    # 去掉 emoji 变体选择符和键帽组合符（1️⃣ → 1），🔟 → 10
    return desc.replace("\ufe0f", "").replace("\u20e3", "").replace("\U0001f51f", "10")


def parse(desc):
    s = normalize(desc)
    m = re.search(r"第(\d+)天《([^》]+)》", s)
    if m:
        return int(m.group(1)), m.group(2).strip()
    m = re.search(r"第(\d+)天", s)
    return (int(m.group(1)), "") if m else (None, "")


def build_manifest():
    vids = []
    seen = set()
    for b in bodies:
        try:
            data = json.loads(b["body"])
        except Exception:
            continue
        for aw in data.get("aweme_list", []):
            vid = aw["aweme_id"]
            if vid in seen:
                continue
            seen.add(vid)
            v = aw.get("video", {})
            url = ""
            for br in v.get("bit_rate", []):
                pa = br.get("play_addr") or {}
                if "h264" in pa.get("url_key", "") and "1080" in pa.get("url_key", ""):
                    url = pa["url_list"][0]
                    break
            if not url:
                pa = v.get("play_addr_h264") or v.get("play_addr") or {}
                if pa.get("url_list"):
                    url = pa["url_list"][0]
            vids.append({"id": vid, "desc": aw.get("desc", ""), "url": url})

    items, used = [], set()
    for v in vids:
        ep, name = parse(v["desc"])
        name = ILLEGAL.sub("_", name) or "无标题"
        fname = f"第{ep:03d}天_{name}.mp4" if ep is not None else f"未编号_{v['id']}.mp4"
        if fname in used:                      # 同名冲突（如同一天两集）
            base, ext = os.path.splitext(fname)
            fname = f"{base}_{v['id']}{ext}"
        used.add(fname)
        items.append({"ep": ep, "name": name, "fname": fname, "url": v["url"], "id": v["id"]})
    items.sort(key=lambda x: (x["ep"] is None, x["ep"] or 0))
    return items


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------
def is_valid_mp4(path):
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        return head[4:8] == b"ftyp" and os.path.getsize(path) > 100000
    except Exception:
        return False


def download(item, out_dir):
    path = os.path.join(out_dir, item["fname"])
    if os.path.exists(path) and is_valid_mp4(path):
        return item["fname"], "skip"
    for attempt in range(4):
        tmp = path + ".part"
        subprocess.run(
            ["curl", "-s", "-L", "--max-time", "90", "--retry", "2",
             "-A", UA, "-H", "Referer: https://www.douyin.com/",
             "-o", tmp, item["url"]],
            capture_output=True)
        if os.path.exists(tmp) and is_valid_mp4(tmp):
            os.replace(tmp, path)
            return item["fname"], "ok"
        time.sleep(1 + attempt)
    if os.path.exists(tmp):
        os.remove(tmp)
    return item["fname"], "FAIL"


def main():
    arg1 = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MIX_ID
    arg2 = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    mix_id = arg1.split("/collection/")[-1].strip("/") if "/collection/" in arg1 else arg1
    out_dir = arg2
    os.makedirs(out_dir, exist_ok=True)

    print(f"合集: {mix_id}\n输出目录: {out_dir}")
    py = ensure_env()
    enumerate_collection(mix_id, py)

    if not bodies:
        print("!! 未获取到任何视频数据，请检查合集ID是否正确")
        sys.exit(1)

    items = build_manifest()
    print(f"\n共 {len(items)} 个视频")
    dups = {k: c for k, c in Counter(i["ep"] for i in items if i["ep"]).items() if c > 1}
    if dups:
        print("提示: 以下天数在该合集中有多个视频:", dups)

    stats = Counter()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(download, it, out_dir): it for it in items}
        for f in as_completed(futs):
            fname, st = f.result()
            stats[st] += 1
            if st == "ok":
                print(f"  [ok] {fname}")
            elif st == "FAIL":
                print(f"  [FAIL] {fname}")

    print(f"\n=== 完成: 成功 {stats['ok']} | 跳过(已存在) {stats['skip']} | 失败 {stats['FAIL']} ===")
    bad = [i["fname"] for i in items
           if not os.path.exists(os.path.join(out_dir, i["fname"]))]
    if bad:
        print("以下文件未下载成功:")
        for b in bad:
            print("  ", b)


if __name__ == "__main__":
    main()
