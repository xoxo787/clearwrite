#!/usr/bin/env python3
"""Blind pairwise naturalness evaluation for one reader. Standard library only.

build: turns items and edited variants into randomized pair sessions (HTML for the
reader, key JSON kept apart). score: reads exported answers with the key and reports
wins, a one-sided binomial test, self-consistency and attention checks.

The reader answers one question: which side reads more naturally. This measures one
reader's preference, not authorship, AI probability or detector evasion.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

QUESTION = "어느 쪽이 더 자연스럽게 읽히나요?"
# Deliberately clumsy additions for attention checks: the untouched human text should win.
CONTROL_OPENING = "현대 사회에서 이러한 경험은 다양한 측면에서 중요한 의미를 가진다고 할 수 있다."
CONTROL_CLOSING = "결론적으로, 이러한 일련의 과정은 우리에게 시사하는 바가 크며 앞으로도 지속적인 관심이 필요하다고 할 수 있다."
RAW = "raw"


def read_items(path: Path) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("text"), str):
            raise ValueError(f"{path}:{n}: id와 text가 필요합니다.")
        if item.get("kind") not in {"human", "ai"}:
            raise ValueError(f"{path}:{n}: kind는 human 또는 ai여야 합니다.")
        if item["id"] in items:
            raise ValueError(f"{path}:{n}: 중복 id {item['id']}")
        items[item["id"]] = item
    return items


def variant_text(item: dict[str, Any], variant: str, variants_dir: Path | None) -> str | None:
    if variant == RAW:
        return item["text"]
    if variants_dir is None:
        return None
    path = variants_dir / variant / f"{item['id']}.txt"
    return path.read_text(encoding="utf-8-sig").strip() if path.is_file() else None


def degrade(text: str) -> str:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    return "\n\n".join([CONTROL_OPENING + " " + paragraphs[0], *paragraphs[1:-1], paragraphs[-1] + " " + CONTROL_CLOSING]
                       if len(paragraphs) > 1 else [CONTROL_OPENING + " " + text + " " + CONTROL_CLOSING])


def build(items: dict[str, dict[str, Any]], *, compare: tuple[str, str], variants_dir: Path | None,
          seed: int, session_size: int = 24, repeat_share: float = .15, controls: int = 4,
          only: set[str] | None = None) -> dict[str, Any]:
    """Return {"sessions": [[pair, ...], ...], "skipped": [...]} with pairs carrying their key."""
    if not 0 <= repeat_share <= .5 or session_size < 4 or controls < 0:
        raise ValueError("repeat_share 0~0.5, session_size 4 이상, controls 0 이상이어야 합니다.")
    rng = random.Random(seed)
    left_variant, right_variant = compare
    main, skipped = [], []
    for item in items.values():
        if item["kind"] != "ai" or (only and item["id"] not in only):
            continue
        a, b = variant_text(item, left_variant, variants_dir), variant_text(item, right_variant, variants_dir)
        if a is None or b is None:
            skipped.append({"id": item["id"], "reason": "variant_missing"})
            continue
        if a == b:
            skipped.append({"id": item["id"], "reason": "identical"})
            continue
        main.append({"type": "main", "item": item["id"], "variants": [left_variant, right_variant], "texts": [a, b]})
    humans = [i for i in items.values() if i["kind"] == "human"]
    rng.shuffle(humans)
    checks = [{"type": "control", "item": h["id"], "variants": ["human", "degraded"], "texts": [h["text"], degrade(h["text"])]}
              for h in humans[:controls]]
    repeats = [dict(p, type="repeat", of=p["item"]) for p in rng.sample(main, round(len(main) * repeat_share))] if main else []
    pool = main + checks
    rng.shuffle(pool)
    n_sessions = max(1, math.ceil((len(pool) + len(repeats)) / session_size))
    sessions: list[list[dict[str, Any]]] = [[] for _ in range(n_sessions)]
    for i, pair in enumerate(pool):
        sessions[i % n_sessions].append(pair)
    for i, pair in enumerate(repeats):
        # Put a repeat in a later session than the original when possible, to weaken recall.
        home = next(k for k, s in enumerate(sessions) if any(p.get("item") == pair["item"] and p["type"] == "main" for p in s))
        sessions[(home + 1) % n_sessions if n_sessions > 1 else home].append(pair)
    out = []
    for s_index, session in enumerate(sessions, 1):
        base = [p for p in session if p["type"] != "repeat"]
        rng.shuffle(base)
        for pair in (p for p in session if p["type"] == "repeat"):
            # Same-session repeats go at least three pairs after the original.
            first = next((j for j, p in enumerate(base) if p["type"] == "main" and p["item"] == pair["item"]), -3)
            base.insert(rng.randint(min(first + 3, len(base)), len(base)), pair)
        session = base
        built = []
        for n, pair in enumerate(session, 1):
            swap = rng.random() < .5
            texts = pair["texts"][::-1] if swap else pair["texts"]
            variants = pair["variants"][::-1] if swap else pair["variants"]
            built.append({"pair_id": f"s{s_index:02d}p{n:02d}", "type": pair["type"], "item": pair["item"],
                          "left": {"variant": variants[0], "text": texts[0]}, "right": {"variant": variants[1], "text": texts[1]}})
        out.append(built)
    return {"sessions": out, "skipped": skipped}


def session_html(session_id: str, pairs: list[dict[str, Any]]) -> str:
    """Self-contained page. Only texts and pair ids are embedded: no variant names or item ids."""
    public = [{"pair_id": p["pair_id"], "left": p["left"]["text"], "right": p["right"]["text"]} for p in pairs]
    data = json.dumps({"session_id": session_id, "question": QUESTION, "pairs": public}, ensure_ascii=False)
    data = data.replace("</", "<\\/").replace("<!--", "<\\!--")
    title = html.escape(f"자연스러움 비교 {session_id}")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1b18;--muted:#6b665e;--card:#fff;--line:#e3ded5;--accent:#2f5d50}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171614;--fg:#ece8e1;--muted:#a39d93;--card:#211f1c;--line:#38342f;--accent:#7fb8a6}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:17px/1.75 system-ui,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:16px}}
header{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}}
.muted{{color:var(--muted);font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:14px 0}}
@media (max-width:760px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;white-space:pre-wrap;word-break:keep-all}}
.card h2{{margin:0 0 6px;font-size:14px;color:var(--muted);font-weight:600}}
.choices{{display:flex;gap:12px;flex-wrap:wrap;align-items:center}}
button{{font:inherit;padding:10px 18px;border-radius:8px;border:1px solid var(--accent);background:var(--card);color:var(--fg);cursor:pointer}}
button.primary{{background:var(--accent);color:var(--bg)}}
button:disabled{{opacity:.45;cursor:default}}
label{{font-size:15px}}
</style></head><body><main>
<header><h1 style="font-size:20px;margin:0">{title}</h1><span class="muted" id="progress"></span></header>
<p class="muted">질문은 하나입니다: <strong id="question"></strong> 정답은 없고, 결과는 이 화면에서 보여 주지 않습니다. 단축키 1 = 왼쪽, 2 = 오른쪽.</p>
<section id="task">
<div class="grid"><article class="card"><h2>왼쪽</h2><div id="left"></div></article><article class="card"><h2>오른쪽</h2><div id="right"></div></article></div>
<div class="choices"><button class="primary" id="pick-left">1 · 왼쪽</button><button class="primary" id="pick-right">2 · 오른쪽</button>
<label><input type="checkbox" id="meaning"> 두 글의 뜻이 달라 보임</label><button id="back">이전</button></div>
</section>
<section id="done" hidden><p>모두 끝났습니다. 아래 버튼으로 결과 파일을 저장해 주세요.</p></section>
<p><button id="save">결과 저장 (JSON)</button> <span class="muted" id="status"></span></p>
<script id="session-data" type="application/json">{data}</script>
<script>
(function(){{
  const S = JSON.parse(document.getElementById('session-data').textContent);
  const KEY = 'clearwrite-naturalness-' + S.session_id;
  let state = {{index: 0, answers: {{}}}};
  try {{ const saved = JSON.parse(localStorage.getItem(KEY) || 'null'); if (saved && saved.answers) state = saved; }} catch (e) {{}}
  const $ = (id) => document.getElementById(id);
  $('question').textContent = S.question;
  let shownAt = Date.now();
  function persist() {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}} }}
  function render() {{
    const total = S.pairs.length, done = Object.keys(state.answers).length;
    $('progress').textContent = done + ' / ' + total;
    if (state.index >= total) {{ $('task').hidden = true; $('done').hidden = false; return; }}
    $('task').hidden = false; $('done').hidden = true;
    const p = S.pairs[state.index];
    $('left').textContent = p.left; $('right').textContent = p.right;
    const prev = state.answers[p.pair_id];
    $('meaning').checked = !!(prev && prev.meaning_flag);
    $('back').disabled = state.index === 0;
    shownAt = Date.now(); window.scrollTo(0, 0);
  }}
  function pick(side) {{
    const p = S.pairs[state.index]; if (!p) return;
    state.answers[p.pair_id] = {{choice: side, meaning_flag: $('meaning').checked, ms: Date.now() - shownAt}};
    state.index += 1; persist(); render();
  }}
  $('pick-left').onclick = () => pick('left');
  $('pick-right').onclick = () => pick('right');
  $('back').onclick = () => {{ if (state.index > 0) {{ state.index -= 1; persist(); render(); }} }};
  document.addEventListener('keydown', (e) => {{ if (e.target.tagName === 'INPUT') return; if (e.key === '1') pick('left'); if (e.key === '2') pick('right'); }});
  $('save').onclick = () => {{
    const answers = S.pairs.filter(p => state.answers[p.pair_id]).map(p => Object.assign({{pair_id: p.pair_id}}, state.answers[p.pair_id]));
    const blob = new Blob([JSON.stringify({{session_id: S.session_id, saved_at: new Date().toISOString(), answers}}, null, 1)], {{type: 'application/json'}});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'naturalness-' + S.session_id + '.json'; a.click();
    $('status').textContent = answers.length + '개 응답을 저장했습니다.';
  }};
  render();
}})();
</script></main></body></html>
"""


def binomial_upper_tail(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 0.5)."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)


def required_wins(n: int, alpha: float = .05) -> int:
    return next((k for k in range(n + 1) if binomial_upper_tail(k, n) <= alpha), n + 1)


def score(key: dict[str, Any], results: list[dict[str, Any]], *, candidate: str, min_control: float = .75,
          min_consistency: float = .7, alpha: float = .05) -> dict[str, Any]:
    pairs = {p["pair_id"]: p for session in key["sessions"] for p in session}
    answers: dict[str, dict[str, Any]] = {}
    for result in results:
        for a in result.get("answers", []):
            if a.get("pair_id") in pairs and a.get("choice") in {"left", "right"}:
                answers[a["pair_id"]] = a
    chosen = {pid: pairs[pid][a["choice"]]["variant"] for pid, a in answers.items()}
    main = [pid for pid in chosen if pairs[pid]["type"] == "main"]
    wins = sum(chosen[pid] == candidate for pid in main)
    controls = [pid for pid in chosen if pairs[pid]["type"] == "control"]
    control_ok = sum(chosen[pid] == "human" for pid in controls)
    by_item = {pairs[pid]["item"]: chosen[pid] for pid in main}
    repeats = [pid for pid in chosen if pairs[pid]["type"] == "repeat" and pairs[pid]["item"] in by_item]
    consistent = sum(chosen[pid] == by_item[pairs[pid]["item"]] for pid in repeats)
    flags = sorted(pairs[pid]["item"] for pid, a in answers.items() if a.get("meaning_flag"))
    n = len(main)
    control_rate = control_ok / len(controls) if controls else None
    consistency = consistent / len(repeats) if repeats else None
    valid = (control_rate is None or control_rate >= min_control) and (consistency is None or consistency >= min_consistency)
    need = required_wins(n, alpha)
    return {"candidate": candidate, "main_pairs": n, "candidate_wins": wins,
            "win_rate": round(wins / n, 3) if n else None, "wilson_95": wilson(wins, n),
            "one_sided_p": round(binomial_upper_tail(wins, n), 4), "wins_needed_for_alpha": need,
            "attention_checks": {"answered": len(controls), "passed": control_ok, "rate": control_rate, "minimum": min_control},
            "self_consistency": {"repeats": len(repeats), "consistent": consistent, "rate": consistency, "minimum": min_consistency},
            "meaning_flags": flags, "unanswered": len(pairs) - len(answers),
            "valid": valid, "decision": ("candidate_preferred" if valid and n and wins >= need else
                                         "not_shown" if valid else "invalid_session"),
            "interpretation": "한 독자의 자연스러움 선호입니다. 저자 판정, AI 확률, 탐지기 회피 지표가 아닙니다."}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="세션 HTML과 정답 키 생성")
    b.add_argument("--items", type=Path, required=True)
    b.add_argument("--variants", type=Path, help="<variants>/<변형 이름>/<id>.txt")
    b.add_argument("--compare", required=True, help="비교할 두 변형. 예: raw,clearwrite-0.4")
    b.add_argument("--out", type=Path, required=True, help="세션 HTML을 둘 새 폴더")
    b.add_argument("--key", type=Path, required=True, help="정답 키 JSON 경로. 세션 폴더 밖에 두세요")
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--session-size", type=int, default=24)
    b.add_argument("--repeat-share", type=float, default=.15)
    b.add_argument("--controls", type=int, default=4)
    s = sub.add_parser("score", help="응답 채점")
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--results", type=Path, nargs="+", required=True)
    s.add_argument("--candidate", required=True, help="이겼는지 볼 변형 이름")
    args = p.parse_args(argv)
    try:
        if args.command == "build":
            compare = tuple(x.strip() for x in args.compare.split(","))
            if len(compare) != 2 or compare[0] == compare[1]:
                raise ValueError("--compare에는 서로 다른 변형 두 개를 쉼표로 적으세요.")
            if args.out.exists() and any(args.out.iterdir()):
                raise ValueError("--out 폴더가 비어 있지 않습니다. 새 폴더를 지정하세요.")
            key_path = args.key.resolve()
            if args.out.resolve() in key_path.parents:
                raise ValueError("정답 키를 세션 폴더 안에 두지 마세요. 독자가 열 수 있습니다.")
            if key_path.exists():
                raise ValueError("정답 키 파일이 이미 있습니다. 덮어쓰지 않습니다.")
            items = read_items(args.items)
            built = build(items, compare=compare, variants_dir=args.variants, seed=args.seed,
                          session_size=args.session_size, repeat_share=args.repeat_share, controls=args.controls)
            if not any(built["sessions"]):
                raise ValueError("만들 수 있는 쌍이 없습니다.")
            args.out.mkdir(parents=True, exist_ok=True)
            for n, session in enumerate(built["sessions"], 1):
                (args.out / f"session-{n:02d}.html").write_text(session_html(f"{args.seed}-{n:02d}", session), encoding="utf-8")
            meta = {"schema_version": "1.0", "compare": list(compare), "seed": args.seed,
                    "items_sha256": hashlib.sha256(args.items.read_bytes()).hexdigest(), "skipped": built["skipped"],
                    "sessions": built["sessions"]}
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            counts = [len(s) for s in built["sessions"]]
            print(json.dumps({"sessions": len(counts), "pairs_per_session": counts, "skipped": built["skipped"]}, ensure_ascii=False))
        else:
            key = json.loads(args.key.read_text(encoding="utf-8"))
            results = [json.loads(path.read_text(encoding="utf-8")) for path in args.results]
            print(json.dumps(score(key, results, candidate=args.candidate), ensure_ascii=False, indent=1))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"naturalness_eval: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
