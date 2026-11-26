# -*- coding: utf-8 -*-
"""把 Dingkao/Taicang 各套试卷的错题生成自包含的错题复习网页 wrong.html。"""
import datetime
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TAICANG = Path("/home/data1/zhiyu/data/Github/Daily.review.email/Dingkao/Taicang")
OUT = BASE / "wrong.html"

# (题库文件, 错题文件) 按页面入口顺序排列
SOURCES = [
    ("questions.json", "wrong.json"),
    ("questions_dk2024_1.json", "wrong_dk2024_1.json"),
]

# 定期考核第2次：题号仍属 -1 卷体系，单独入口、掌握进度与第1次分开记录
ROUND2 = ("questions_dk2024_1.json", "wrong_dk2024_2.json", "2024-2026定期考核-2（第2次）")


def load_wrong_ids(path):
    """兼容两种格式：纯列表 [1,3,...] 或 {"ids": [...]}"""
    d = json.loads(path.read_text(encoding="utf-8"))
    ids = d["ids"] if isinstance(d, dict) else d
    return set(int(i) for i in ids)


data = {"sets": []}
for qfile, wfile in SOURCES:
    questions = json.loads((TAICANG / "data" / qfile).read_text(encoding="utf-8"))
    wrong_ids = load_wrong_ids(TAICANG / "data" / wfile)
    seen, sources = set(), []
    for q in questions:
        if q["source"] not in seen:
            seen.add(q["source"])
            sources.append(q["source"])
    for s in sources:
        qs = [q for q in questions if q["source"] == s and q["id"] in wrong_ids]
        for q in qs:
            q["key"] = f'{s}::{q["id"]}'  # 跨题库唯一主键，掌握记录不串题
        data["sets"].append({"source": s, "questions": qs})

# —— 定期考核第2次入口（复用 -1 卷题号体系，独立进度）——
qfile, wfile, label = ROUND2
questions = json.loads((TAICANG / "data" / qfile).read_text(encoding="utf-8"))
wrong_ids = load_wrong_ids(TAICANG / "data" / wfile)
qs = [q for q in questions if q["source"] == "2024-2026定期考核（中医）-1" and q["id"] in wrong_ids]
for q in qs:
    q["key"] = f'{label}::{q["id"]}'
data["sets"].append({"source": label, "questions": qs})

# —— 高频错题：两次考核都错的题，掌握进度并入第1次入口（同题同进度）——
r2_ids = load_wrong_ids(TAICANG / "data" / wfile)
s1 = next(s for s in data["sets"] if s["source"] == "2024-2026定期考核（中医）-1")
hf = [q for q in s1["questions"] if int(q["key"].split("::")[-1]) in r2_ids]
data["sets"].append({"source": "🔥 高频错题（两次都错）", "questions": hf})
n_wrong = sum(len(s["questions"]) for s in data["sets"])
version = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>错题复习 · Wrong Question Review</title>
<meta name="app-version" content="__VERSION__">
<style>
:root{--ink:#2b2118;--paper:#fff8ec;--red:#d1495b;--green:#37b26c;--gold:#fb8500}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif;
  background:linear-gradient(180deg,#7ec8ff 0%,#b8e2ff 45%,#ffe9c9 100%);min-height:100vh;color:#fff}
#app{max-width:640px;margin:0 auto;padding:14px 14px 40px}
.top{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.top h1{font-size:20px;text-shadow:0 2px 0 rgba(0,0,0,.15)}
.top .sp{flex:1}
.top .ver{font-size:11px;opacity:.55}
.iconbtn{width:40px;height:40px;border-radius:12px;border:none;background:rgba(255,255,255,.9);
  font-size:19px;cursor:pointer;box-shadow:0 2px 0 rgba(0,0,0,.12)}
.card{background:var(--paper);color:var(--ink);border-radius:18px;padding:16px;margin-bottom:12px;
  box-shadow:0 5px 0 rgba(120,80,20,.22)}
.card h2{font-size:18px}
.card .sub{font-size:13px;color:#9b8871;margin-top:4px}
.card .actions{display:flex;gap:8px;margin-top:12px}
.btn{border:none;border-radius:999px;padding:11px 22px;font-size:15px;font-weight:800;cursor:pointer;
  color:#fff;background:linear-gradient(180deg,#ff9e00,#fb8500);box-shadow:0 3px 0 #b35c00}
.btn:active{transform:translateY(2px);box-shadow:0 1px 0 #b35c00}
.btn.blue{background:linear-gradient(180deg,#4dabf7,#339af0);box-shadow:0 3px 0 #1c6fb8}
.btn.ghost{background:#e9dfc9;color:#7a6a55;box-shadow:0 3px 0 #c9b99a}
.btn:disabled{opacity:.45;pointer-events:none}
.bar{height:10px;background:rgba(255,255,255,.5);border-radius:5px;overflow:hidden;margin:10px 0 14px}
.bar>div{height:100%;background:linear-gradient(90deg,#ffb703,#fb8500);transition:width .3s}
.qhead{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.tag{background:#ffe1e1;color:#c0392b;border-radius:8px;padding:2px 9px;font-size:12px;font-weight:700}
.tag.multi{background:#e7f0ff;color:#1c6fb8}
.tag.tf{background:#eaf7ea;color:#2e8b57}
.stem{font-size:17px;font-weight:700;line-height:1.6;margin-bottom:14px;user-select:text}
.opt{display:block;width:100%;text-align:left;background:#fff;border:2px solid #e5d5b8;border-radius:13px;
  padding:12px 14px;font-size:15px;margin-bottom:9px;cursor:pointer;color:var(--ink);font-weight:600}
.opt.sel{border-color:#339af0;background:#e7f5ff}
.opt.right{background:#d8f5e3;border-color:var(--green)}
.opt.wrong{background:#ffe1e1;border-color:var(--red)}
.opt.dim{opacity:.45;pointer-events:none}
.letter{display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:8px;
  background:#f2e8d5;margin-right:8px;font-size:13px}
.feedback{border-radius:12px;padding:11px 14px;font-size:15px;font-weight:700;margin:6px 0 12px;display:none}
.feedback.ok{display:block;background:#d8f5e3;color:#1e7a46}
.feedback.no{display:block;background:#ffe1e1;color:#c0392b}
.big-emoji{font-size:48px;text-align:center}
.center{text-align:center}
.summary{font-size:16px;line-height:2;text-align:center}
.mastered-badge{font-size:11px;background:#d8f5e3;color:#1e7a46;border-radius:6px;padding:1px 6px;margin-left:6px}
.unmastered-badge{font-size:11px;background:#ffe1e1;color:#c0392b;border-radius:6px;padding:1px 6px;margin-left:6px}
.fbtn{border:2px solid #e5d5b8;background:#fff;border-radius:999px;padding:6px 14px;font-size:13px;font-weight:700;color:#7a6a55;cursor:pointer}
.fbtn.on{background:#fb8500;border-color:#fb8500;color:#fff}
.rowitem{background:#fff;border:2px solid #e5d5b8;border-radius:13px;padding:12px 14px;margin-bottom:9px;
  font-size:14px;line-height:1.7;user-select:text}
.rowitem b.ans{color:var(--red)}
.rowitem .mastered-badge{float:right}
.browsetitle{font-size:14px;font-weight:800;color:#7a6a55;margin:14px 0 8px}
.empty{color:#9b8871;text-align:center;padding:30px 0;font-size:15px}
</style>
</head>
<body>
<div id="app">
  <div class="top">
    <button class="iconbtn" id="btn-home" title="返回主游戏">🏠</button>
    <h1>📝 错题复习</h1>
    <span class="ver">v__VERSION__</span>
    <div class="sp"></div>
    <button class="iconbtn" id="btn-cloud" title="云同步">☁️</button>
    <button class="iconbtn" id="btn-clear" title="清空掌握记录">🗑️</button>
  </div>
  <div id="main"></div>
</div>
<script>
"use strict";
const DATA = __DATA_JSON__;
const LS = "wrong-review-v1";
let prog = {};
try { prog = JSON.parse(localStorage.getItem(LS) || "{}") || {}; } catch (e) {}

/* ---------- 云同步（与主游戏共用密钥，独立存储键，互不覆盖） ---------- */
const MASTER_LS = "gejue-adventure-v1-cloudkey";
let masterKey = null;
try { masterKey = localStorage.getItem(MASTER_LS) || null; } catch (e) {}
if (!masterKey) {
  masterKey = "fq-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  try { localStorage.setItem(MASTER_LS, masterKey); } catch (e) {}
}
const CLOUD_KEY = masterKey + "-wrong";
let cloudTimer = null, cloudBusy = false;
function cloudBadge(ok) {
  const b = $("btn-cloud"); if (!b) return;
  b.textContent = ok === false ? "☁️✖" : "☁️✅";
  b.title = "云同步：" + masterKey;
}
function cloudPush() {
  if (cloudBusy) return; cloudBusy = true;
  prog.__ts = Date.now();
  fetch("/api/save", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: CLOUD_KEY, data: { prog: prog }, updatedAt: prog.__ts }) })
    .then(() => cloudBadge(true))
    .catch(() => cloudBadge(false))
    .finally(() => { cloudBusy = false; });
}
function scheduleCloudPush() { clearTimeout(cloudTimer); cloudTimer = setTimeout(cloudPush, 1200); }
async function cloudPull() {
  try {
    const r = await fetch("/api/save?key=" + encodeURIComponent(CLOUD_KEY));
    if (r.status === 404) { cloudPush(); return; }
    if (!r.ok) { cloudBadge(false); return; }
    const remote = await r.json();
    const rp = (remote.data && remote.data.prog) || {};
    let changed = false;
    for (const k in rp) {
      if (k === "__ts") continue;
      if ((rp[k] || 0) > (prog[k] || 0)) { prog[k] = rp[k]; changed = true; }
    }
    if ((remote.updatedAt || 0) > (prog.__ts || 0)) { prog.__ts = remote.updatedAt; changed = true; }
    if (changed) { save(); if (!cur) renderHome(); }
    else if ((prog.__ts || 0) > (remote.updatedAt || 0)) cloudPush();
    cloudBadge(true);
  } catch (e) { cloudBadge(false); }
}

function save() { try { localStorage.setItem(LS, JSON.stringify(prog)); } catch (e) {} scheduleCloudPush(); }
const GROUP = 50; // 攻克未掌握时每组题数
function masteredCount(qs) { return qs.filter(q => (prog[q.key] || 0) >= 2).length; }
function unmasteredList(s) { return s.questions.filter(q => (prog[q.key] || 0) < 2); }
function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[a[i], a[j]] = [a[j], a[i]]; } return a; }
const $ = id => document.getElementById(id);
const main = $("main");
let cur = null; // 当前答题状态

/* ---------- 首页：每套题一个入口 ---------- */
function renderHome() {
  cur = null;
  main.innerHTML = DATA.sets.map((s, i) => {
    const total = s.questions.length, m = masteredCount(s.questions);
    const left = total - m;
    return `<div class="card">
      <h2>📄 ${s.source}</h2>
      <div class="sub">错题 ${total} 道 · 已掌握 ${m} 道${total ? " · 待攻克 " + left + " 道" : ""}</div>
      ${total ? `<div class="bar"><div style="width:${Math.round(m / total * 100)}%"></div></div>` : ""}
      <div class="actions" style="flex-wrap:wrap">
        ${left ? groupButtons(i, left) : '<button class="btn" disabled title="未掌握题目已清空">⚔️ 攻克未掌握（0）</button>'}
        <button class="btn" data-quizall="${i}" ${total ? "" : "disabled"}>🔁 全部重练（${total}）</button>
        <button class="btn blue" data-browse="${i}" ${total ? "" : "disabled"}>📖 背题模式</button>
      </div>
      ${total && !left ? '<div class="sub" style="color:#1e7a46">🎉 这套错题已全部掌握！可「全部重练」巩固。</div>' : ""}
    </div>`;
  }).join("") + `<p style="text-align:center;font-size:12px;opacity:.6">同一题答对 2 次即标记「已掌握」；掌握状态在背题模式里可查看、筛选</p>`;
  document.querySelectorAll("[data-quizun]").forEach(b => b.onclick = () => startQuiz(+b.dataset.quizun, true, b.dataset.grp == null ? null : +b.dataset.grp));
  document.querySelectorAll("[data-quizall]").forEach(b => b.onclick = () => startQuiz(+b.dataset.quizall, false));
  document.querySelectorAll("[data-browse]").forEach(b => b.onclick = () => renderBrowse(+b.dataset.browse));
}
/* 攻克未掌握分组按钮：未掌握 ≤50 一个按钮，>50 每 50 个一组，分组按固定顺序切，稳定不漂移 */
function groupButtons(i, left) {
  if (left <= GROUP) return `<button class="btn" data-quizun="${i}">⚔️ 攻克未掌握（${left}）</button>`;
  const n = Math.ceil(left / GROUP);
  let html = "";
  for (let g = 0; g < n; g++) {
    const cnt = Math.min(GROUP, left - g * GROUP);
    html += `<button class="btn" data-quizun="${i}" data-grp="${g}">⚔️ 攻克 第${g + 1}组（${cnt}）</button>`;
  }
  return html;
}

/* ---------- 答题模式 ---------- */
function startQuiz(setIdx, onlyUnmastered, grp) {
  const s = DATA.sets[setIdx];
  let pool = onlyUnmastered ? unmasteredList(s) : s.questions;
  if (grp != null) pool = pool.slice(grp * GROUP, (grp + 1) * GROUP); // 分组按原始顺序切片，组内再乱序
  const qs = shuffle([...pool]);
  if (!qs.length) { renderHome(); return; }
  cur = { setIdx, qs, i: 0, right: 0, sel: [], locked: false, onlyUn: !!onlyUnmastered, grp: grp == null ? null : +grp };
  renderQ();
}
function tagOf(q) {
  if (q.section === "多选题") return '<span class="tag multi">多选题</span>';
  if (q.section === "是非题") return '<span class="tag tf">是非题</span>';
  return '<span class="tag">单选题</span>';
}
/* 距掌握进度徽标：答对2次即掌握，答错归零 */
function masteryBadge(q) {
  const p = prog[q.key] || 0;
  if (p >= 2) return '<span class="tag" style="background:#d8f5e3;color:#1e7a46">已掌握 ✓✓</span>';
  if (p === 1) return '<span class="tag" style="background:#fff3cd;color:#8a6d00">✓○ 再答对 1 次掌握</span>';
  return '<span class="tag" style="background:#ffe1e1;color:#c0392b">○○ 再答对 2 次掌握</span>';
}
/* 本轮/本组剩余未掌握题数，作答后即时刷新 */
function updateRoundUn() {
  const el = $("grp-un"); if (!el || !cur) return;
  const n = cur.qs.filter(q => (prog[q.key] || 0) < 2).length;
  el.textContent = (cur.grp != null ? "本组 " : "本轮 ") + cur.qs.length + " 题 · 未掌握 " + n + " 道" + (n === 0 ? " 🎉" : "");
}
function renderQ() {
  const { qs, i } = cur;
  if (i >= qs.length) return renderResult();
  const q = qs[i];
  const letters = Object.keys(q.options);
  const multi = q.section === "多选题";
  cur.sel = []; cur.locked = false;
  main.innerHTML = `
    <div class="card">
      <div class="qhead">${tagOf(q)}${masteryBadge(q)}<span class="tag" style="background:#f2e8d5;color:#7a6a55">编号${q.id}</span>
        <span style="font-size:13px;color:#9b8871">第 ${i + 1} / ${qs.length} 题 · ${DATA.sets[cur.setIdx].source}${cur.grp != null ? " · 第" + (cur.grp + 1) + "组" : ""}</span>
      </div>
      <div class="bar"><div style="width:${Math.round(i / qs.length * 100)}%"></div></div>
      <div class="sub" id="grp-un" style="margin:-4px 0 10px"></div>
      <div class="stem">${q.num}. ${q.stem}</div>
      <div id="opts">${letters.map(L =>
        `<button class="opt" data-l="${L}"><span class="letter">${L}</span>${q.options[L]}</button>`).join("")}
      </div>
      <div class="feedback" id="fb"></div>
      <div class="actions" id="foot">
        ${multi ? '<button class="btn blue" id="btn-ok" style="display:none">确定</button>' : ""}
      </div>
    </div>`;
  document.querySelectorAll("#opts .opt").forEach(b => b.onclick = () => {
    if (cur.locked) return;
    const L = b.dataset.l;
    if (multi) {
      const k = cur.sel.indexOf(L);
      if (k >= 0) { cur.sel.splice(k, 1); b.classList.remove("sel"); }
      else { cur.sel.push(L); b.classList.add("sel"); }
      $("btn-ok").style.display = cur.sel.length ? "" : "none";
    } else {
      submit([L]);
    }
  });
  const okBtn = $("btn-ok");
  if (okBtn) okBtn.onclick = () => submit([...cur.sel].sort());
  updateRoundUn();
}
function submit(sel) {
  const q = cur.qs[cur.i];
  const right = q.answer.split(",").sort().join(",");
  const mine = sel.sort().join(",");
  const ok = mine === right;
  cur.locked = true;
  document.querySelectorAll("#opts .opt").forEach(b => {
    const L = b.dataset.l;
    if (right.split(",").includes(L)) b.classList.add("right");
    else if (mine.split(",").includes(L)) b.classList.add("wrong");
    else b.classList.add("dim");
    b.classList.remove("sel");
  });
  const fb = $("fb");
  if (ok) {
    fb.className = "feedback ok";
    fb.textContent = "✅ 回答正确！" + ((prog[q.key] || 0) + 1 >= 2 ? " 已掌握 🎉" : " 再答对 1 次即掌握");
    prog[q.key] = (prog[q.key] || 0) + 1; save();
    cur.right++;
    $("foot").innerHTML = '<button class="btn" id="btn-next">下一题 →</button>';
  } else {
    fb.className = "feedback no";
    fb.innerHTML = "❌ 答错了，正确答案：<b>" + right.split(",").map(L => L + ". " + q.options[L]).join("；") + "</b>";
    prog[q.key] = 0; save();
    $("foot").innerHTML = '<button class="btn" id="btn-next">下一题 →</button>';
  }
  $("btn-next").onclick = () => { cur.i++; renderQ(); };
  updateRoundUn();
}
function renderResult() {
  const { qs, right } = cur;
  const setIdx = cur.setIdx;
  const all = DATA.sets[setIdx].questions;
  const mastered = masteredCount(all);
  const unmastered = all.length - mastered;
  main.innerHTML = `<div class="card">
    <div class="big-emoji">${right === qs.length ? "🏆" : "💪"}</div>
    <h2 class="center" style="margin:8px 0">本轮成绩${cur.onlyUn === false ? "（全部重练）" : cur.grp != null ? "（攻克第 " + (cur.grp + 1) + " 组）" : ""}</h2>
    <p class="summary">本轮 ${qs.length} 题 · 答对 ${right} 题<br>
    本套进度：<b style="color:#1e7a46">已掌握 ${mastered}</b> / <b style="color:#c0392b">未掌握 ${unmastered}</b>（共 ${all.length} 道）</p>
    <div class="actions" style="justify-content:center;flex-wrap:wrap">
      <button class="btn" id="btn-again">🔁 同范围再来一轮</button>
      ${unmastered && !cur.onlyUn ? '<button class="btn blue" id="btn-goun">⚔️ 转攻克未掌握</button>' : ""}
      <button class="btn ghost" id="btn-back">🏠 返回首页</button>
    </div>
  </div>`;
  $("btn-again").onclick = () => startQuiz(setIdx, cur.onlyUn, cur.grp);
  const gu = $("btn-goun");
  if (gu) gu.onclick = () => startQuiz(setIdx, true, unmastered > GROUP ? 0 : null);
  $("btn-back").onclick = renderHome;
}

/* ---------- 背题模式 ---------- */
function renderBrowse(setIdx, filter) {
  filter = filter || "all";
  const s = DATA.sets[setIdx];
  const all = s.questions;
  const list = all.filter(q => filter === "all"
    || (filter === "un" ? (prog[q.key] || 0) < 2 : (prog[q.key] || 0) >= 2));
  const nUn = all.filter(q => (prog[q.key] || 0) < 2).length;
  const groups = {};
  list.forEach(q => { (groups[q.section] = groups[q.section] || []).push(q); });
  main.innerHTML = `<div class="card">
      <h2>📖 ${s.source} · 背题模式</h2>
      <div class="sub">共 ${all.length} 道错题：已掌握 ${all.length - nUn} 道 · 未掌握 ${nUn} 道；红色为正确答案</div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <button class="fbtn ${filter === "all" ? "on" : ""}" data-f="all">全部 ${all.length}</button>
        <button class="fbtn ${filter === "un" ? "on" : ""}" data-f="un">未掌握 ${nUn}</button>
        <button class="fbtn ${filter === "ok" ? "on" : ""}" data-f="ok">已掌握 ${all.length - nUn}</button>
      </div>
    </div>` +
    (list.length ? Object.keys(groups).map(sec => `
      <div class="browsetitle">${sec}（${groups[sec].length} 道）</div>` +
      groups[sec].map(q => {
        const m = (prog[q.key] || 0) >= 2;
        const ans = q.answer.split(",");
        return `<div class="rowitem">
          ${m ? '<span class="mastered-badge">已掌握</span>' : '<span class="unmastered-badge">未掌握</span>'}
          <b>${q.num}.</b> <small style="color:#b0a48e">[编号${q.id}]</small> ${q.stem}<br>
          ${Object.keys(q.options).map(L =>
            ans.includes(L)
              ? `<b class="ans">${L}. ${q.options[L]}</b>`
              : `<span style="opacity:.65">${L}. ${q.options[L]}</span>`).join("<br>")}
        </div>`;
      }).join("")).join("")
      : '<p class="empty">该分类下没有题目</p>') +
    `<div class="actions" style="justify-content:center;margin-top:14px">
       <button class="btn ghost" id="btn-back">🏠 返回首页</button>
     </div>`;
  document.querySelectorAll(".fbtn").forEach(b => b.onclick = () => renderBrowse(setIdx, b.dataset.f));
  $("btn-back").onclick = renderHome;
}

/* ---------- 顶部 ---------- */
$("btn-home").onclick = () => { location.href = "./"; };
$("btn-cloud").onclick = () => {
  const tip = "☁️ 云同步已开启（与主游戏共用密钥，已自动复制）\n\n本机密钥：" + masterKey +
    "\n\n在其他设备上同步：打开该设备的主游戏 → 左上角 👤 用户面板 → 把本机密钥粘贴到「新用户/云存档」处（或直接点 ☁️ 按钮输入），本页掌握进度即自动同步。";
  if (navigator.clipboard && navigator.clipboard.writeText)
    navigator.clipboard.writeText(masterKey).then(() => alert(tip)).catch(() => alert(tip));
  else alert(tip);
};
$("btn-clear").onclick = () => {
  if (confirm("清空本机的「已掌握」记录？（不影响其他设备，错题列表本身不变）")) { prog = {}; save(); renderHome(); }
};

renderHome();
cloudPull();
</script>
</body>
</html>
"""

html = HTML.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False, indent=1))
html = html.replace("__VERSION__", version)
OUT.write_text(html, encoding="utf-8")
print(f"written {OUT} ({OUT.stat().st_size} bytes) version {version}, 错题 {n_wrong} 道")
for s in data["sets"]:
    print(f"  {s['source']}: {len(s['questions'])} 道错题")
