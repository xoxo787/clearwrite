import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("naturalness_eval", ROOT / "scripts/naturalness_eval.py")
NE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NE)


def items(n_ai=10, n_human=4, edited=True):
    out = {}
    for i in range(n_ai):
        out[f"ai{i:02d}"] = {"id": f"ai{i:02d}", "kind": "ai", "text": f"AI 원문 {i}입니다.\n\n둘째 문단 {i}입니다."}
    for i in range(n_human):
        out[f"h{i:02d}"] = {"id": f"h{i:02d}", "kind": "human", "text": f"사람 글 {i}이다.\n\n다음 문단 {i}이다."}
    return out


class Fixture:
    def __init__(self, n_ai=10, n_human=4, missing=()):
        self.tmp = tempfile.TemporaryDirectory(prefix="자연스러움 평가 ")
        self.root = Path(self.tmp.name)
        self.items = items(n_ai, n_human)
        self.items_path = self.root / "items.jsonl"
        self.items_path.write_bytes("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in self.items.values()).encode())
        self.variants = self.root / "variants"
        (self.variants / "edited").mkdir(parents=True)
        for k, item in self.items.items():
            if item["kind"] == "ai" and k not in missing:
                (self.variants / "edited" / f"{k}.txt").write_bytes(("고친 " + item["text"]).encode())

    def close(self):
        self.tmp.cleanup()


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture(n_ai=20, n_human=4, missing=("ai03",))

    def tearDown(self):
        self.f.close()

    def run_build(self, seed=7, **kw):
        return NE.build(self.f.items, compare=("raw", "edited"), variants_dir=self.f.variants, seed=seed, **kw)

    def test_deterministic_for_seed_and_differs_across_seeds(self):
        self.assertEqual(self.run_build(), self.run_build())
        self.assertNotEqual(self.run_build(seed=1), self.run_build(seed=2))

    def test_pair_counts_controls_repeats_and_skips(self):
        built = self.run_build(session_size=12)
        pairs = [p for s in built["sessions"] for p in s]
        kinds = [p["type"] for p in pairs]
        self.assertEqual(kinds.count("main"), 19)
        self.assertEqual(kinds.count("control"), 4)
        self.assertEqual(kinds.count("repeat"), round(19 * .15))
        self.assertEqual(built["skipped"], [{"id": "ai03", "reason": "variant_missing"}])
        self.assertTrue(all(len(s) <= 14 for s in built["sessions"]))
        self.assertEqual(len({p["pair_id"] for p in pairs}), len(pairs))

    def test_sides_are_balanced_and_texts_match_variants(self):
        pairs = [p for s in self.run_build(session_size=40)["sessions"] for p in s if p["type"] == "main"]
        left_raw = sum(p["left"]["variant"] == "raw" for p in pairs)
        self.assertTrue(5 <= left_raw <= 14, left_raw)
        for p in pairs:
            raw = p["left"] if p["left"]["variant"] == "raw" else p["right"]
            self.assertEqual(raw["text"], self.f.items[p["item"]]["text"])

    def test_same_session_repeat_is_spaced(self):
        session = self.run_build(session_size=200)["sessions"][0]
        for k, p in enumerate(session):
            if p["type"] == "repeat":
                first = next(j for j, q in enumerate(session) if q["type"] == "main" and q["item"] == p["item"])
                self.assertGreaterEqual(abs(k - first), 3)

    def test_controls_degrade_the_human_text(self):
        controls = [p for s in self.run_build()["sessions"] for p in s if p["type"] == "control"]
        for p in controls:
            human = p["left"] if p["left"]["variant"] == "human" else p["right"]
            degraded = p["right"] if human is p["left"] else p["left"]
            self.assertEqual(human["text"], self.f.items[p["item"]]["text"])
            self.assertIn(NE.CONTROL_CLOSING, degraded["text"])

    def test_session_size_is_a_maximum(self):
        for size in (4, 6, 9):
            built = self.run_build(session_size=size)
            self.assertTrue(all(len(s) <= size for s in built["sessions"]), (size, [len(s) for s in built["sessions"]]))

    def test_repeat_spacing_holds_for_many_seeds(self):
        for seed in range(30):
            for session in self.run_build(seed=seed, session_size=200)["sessions"]:
                for k, p in enumerate(session):
                    if p["type"] == "repeat":
                        first = next(j for j, q in enumerate(session) if q["type"] == "main" and q["item"] == p["item"])
                        self.assertGreaterEqual(abs(k - first), 3, seed)

    def test_empty_only_selects_nothing(self):
        built = self.run_build(only=set(), controls=0)
        self.assertEqual([p for s in built["sessions"] for p in s], [])

    def test_unsafe_names_are_rejected(self):
        with self.assertRaises(ValueError):
            NE.build(self.f.items, compare=("raw", "../edited"), variants_dir=self.f.variants, seed=1)
        bad = self.f.root / "bad.jsonl"
        bad.write_bytes(json.dumps({"id": "../../secret", "kind": "ai", "text": "x"}).encode())
        with self.assertRaises(ValueError):
            NE.read_items(bad)

    def test_identical_variant_is_skipped(self):
        (self.f.variants / "edited" / "ai00.txt").write_bytes(self.f.items["ai00"]["text"].encode())
        self.assertIn({"id": "ai00", "reason": "identical"}, self.run_build()["skipped"])


class ExcerptTests(unittest.TestCase):
    BASE = ("첫 문장은 그대로다. 둘째 문장도 그대로다. 셋째 문장에서 고친 말이 나온다. "
            "넷째 문장은 길게 이어지는 설명이다. 다섯째 문장으로 끝난다.")
    OTHER = BASE.replace("고친 말이 나온다", "바뀐 표현이 보인다")

    def test_excerpt_holds_the_change_and_matches_on_both_sides(self):
        a, b = NE.aligned_excerpts(self.BASE, self.OTHER, 60)
        self.assertIn("고친 말이 나온다", a)
        self.assertIn("바뀐 표현이 보인다", b)
        self.assertEqual(a.replace("고친 말이 나온다", "바뀐 표현이 보인다"), b)
        self.assertTrue(a.endswith(".") and b.endswith("."))
        self.assertLess(len(a), len(self.BASE))

    def test_excerpt_keeps_whole_sentences_even_if_one_is_long(self):
        long = "아주 긴 문장 " * 30 + "끝."
        a, b = NE.aligned_excerpts(long + " 다음 문장.", long.replace("끝", "마침") + " 다음 문장.", 60)
        self.assertTrue(a.startswith("아주 긴 문장") and a.endswith("끝."))
        self.assertTrue(b.endswith("마침."))

    def test_lead_excerpt_is_whole_sentences_within_limit(self):
        self.assertEqual(NE.lead_excerpt(self.BASE, 25), "첫 문장은 그대로다. 둘째 문장도 그대로다.")
        self.assertEqual(NE.lead_excerpt("한 문장뿐인 아주 긴 글이다", 5), "한 문장뿐인 아주 긴 글이다")

    def test_build_with_max_chars_shortens_pairs_and_controls(self):
        f = Fixture(n_ai=6, n_human=4)
        try:
            for k, item in f.items.items():
                if item["kind"] == "ai":
                    long = item["text"] + " " + "이어지는 설명 문장이다. " * 20
                    item["text"] = long
                    (f.variants / "edited" / f"{k}.txt").write_bytes(long.replace("둘째 문단", "두 번째 문단").encode())
            full = NE.build(f.items, compare=("raw", "edited"), variants_dir=f.variants, seed=2)
            short = NE.build(f.items, compare=("raw", "edited"), variants_dir=f.variants, seed=2, max_chars=80)
            longest = lambda b: max(len(p[s]["text"]) for x in b["sessions"] for p in x for s in ("left", "right"))
            self.assertLess(longest(short), longest(full) / 2)
            mains = [p for s in short["sessions"] for p in s if p["type"] == "main"]
            self.assertTrue(mains and all(p["left"]["text"] != p["right"]["text"] for p in mains))
            with self.assertRaises(ValueError):
                NE.build(f.items, compare=("raw", "edited"), variants_dir=f.variants, seed=2, max_chars=10)
        finally:
            f.close()


class HtmlTests(unittest.TestCase):
    def test_page_has_texts_but_no_key_and_escapes_markup(self):
        pairs = [{"pair_id": "s01p01", "type": "main", "item": "secret-item-id",
                  "left": {"variant": "clearwrite-secret", "text": "</script><script>alert(1)</script> 왼쪽"},
                  "right": {"variant": "raw", "text": "<!-- 오른쪽 -->"}}]
        page = NE.session_html("7-01", pairs)
        self.assertNotIn("clearwrite-secret", page)
        self.assertNotIn("secret-item-id", page)
        self.assertNotIn('"raw"', page)
        self.assertEqual(page.count("</script>"), 2)
        data = re.search(r'<script id="session-data" type="application/json">(.*?)</script>', page, re.S).group(1)
        payload = json.loads(data.replace("<\\/", "</").replace("<\\!--", "<!--"))
        self.assertEqual(payload["pairs"][0]["left"], "</script><script>alert(1)</script> 왼쪽")
        self.assertIn(NE.QUESTION, data)


class ScoreTests(unittest.TestCase):
    def key_and_answers(self, n_main=20, candidate_wins=15, control_pass=4, consistent=True):
        sessions, answers = [[]], []
        for i in range(n_main):
            pid = f"m{i}"
            sessions[0].append({"pair_id": pid, "type": "main", "item": f"ai{i}",
                                "left": {"variant": "edited"}, "right": {"variant": "raw"}})
            answers.append({"pair_id": pid, "choice": "left" if i < candidate_wins else "right"})
        for i in range(4):
            sessions[0].append({"pair_id": f"c{i}", "type": "control", "item": f"h{i}",
                                "left": {"variant": "human"}, "right": {"variant": "degraded"}})
            answers.append({"pair_id": f"c{i}", "choice": "left" if i < control_pass else "right"})
        for i in range(3):
            sessions[0].append({"pair_id": f"r{i}", "type": "repeat", "item": f"ai{i}",
                                "left": {"variant": "raw"}, "right": {"variant": "edited"}})
            answers.append({"pair_id": f"r{i}", "choice": "right" if consistent else "left"})
        return {"sessions": sessions}, [{"answers": answers}]

    def test_binomial_and_threshold(self):
        self.assertAlmostEqual(NE.binomial_upper_tail(15, 20), 0.020695, places=5)
        self.assertEqual(NE.required_wins(20), 15)
        self.assertEqual(NE.required_wins(48), 31)
        self.assertEqual(NE.binomial_upper_tail(0, 0), 1.0)

    def test_score_counts_wins_checks_and_consistency(self):
        key, results = self.key_and_answers()
        r = NE.score(key, results, candidate="edited")
        self.assertEqual((r["main_pairs"], r["candidate_wins"]), (20, 15))
        self.assertEqual(r["attention_checks"]["rate"], 1.0)
        self.assertEqual(r["self_consistency"]["rate"], 1.0)
        self.assertEqual(r["decision"], "candidate_preferred")
        self.assertIn("AI 확률", r["interpretation"])

    def test_failed_checks_invalidate_the_session(self):
        key, results = self.key_and_answers(control_pass=2)
        self.assertEqual(NE.score(key, results, candidate="edited")["decision"], "invalid_session")
        key, results = self.key_and_answers(consistent=False)
        self.assertEqual(NE.score(key, results, candidate="edited")["decision"], "invalid_session")

    def test_not_enough_wins_is_not_shown(self):
        key, results = self.key_and_answers(candidate_wins=12)
        self.assertEqual(NE.score(key, results, candidate="edited")["decision"], "not_shown")

    def test_unanswered_checks_invalidate_the_session(self):
        key, results = self.key_and_answers()
        results[0]["answers"] = [a for a in results[0]["answers"] if not a["pair_id"].startswith(("c", "r"))]
        r = NE.score(key, results, candidate="edited")
        self.assertEqual(r["decision"], "invalid_session")
        self.assertEqual(set(r["problems"]), {"attention_checks_incomplete", "repeats_incomplete"})

    def test_duplicate_answers_are_rejected(self):
        key, results = self.key_and_answers()
        with self.assertRaises(ValueError):
            NE.score(key, results + results, candidate="edited")

    def test_results_from_another_session_are_rejected(self):
        key, results = self.key_and_answers()
        key["session_ids"] = ["7-01-abc"]
        results[0]["session_id"] = "7-01-zzz"
        with self.assertRaises(ValueError):
            NE.score(key, results, candidate="edited")
        results[0]["session_id"] = "7-01-abc"
        self.assertEqual(NE.score(key, results, candidate="edited")["main_pairs"], 20)

    def test_excluded_items_are_reported(self):
        key, results = self.key_and_answers()
        key["skipped"] = [{"id": "x", "reason": "identical"}, {"id": "y", "reason": "identical"}]
        r = NE.score(key, results, candidate="edited")
        self.assertEqual(r["excluded_items"], {"identical": 2})
        self.assertIn("분모에 없습니다", r["scope"])

    def test_unknown_or_bad_answers_are_ignored(self):
        key, results = self.key_and_answers()
        results[0]["answers"] += [{"pair_id": "nope", "choice": "left"}, {"pair_id": "m0", "choice": "up"}]
        self.assertEqual(NE.score(key, results, candidate="edited")["main_pairs"], 20)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture(n_ai=12, n_human=4)

    def tearDown(self):
        self.f.close()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts/naturalness_eval.py"), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_build_then_score_round_trip(self):
        out, key = self.f.root / "세션", self.f.root / "keys" / "key.json"
        r = self.cli("build", "--items", self.f.items_path, "--variants", self.f.variants, "--compare", "raw,edited",
                     "--out", out, "--key", key, "--seed", 3)
        self.assertEqual(r.returncode, 0, r.stderr)
        pages = sorted(out.glob("session-*.html"))
        self.assertTrue(pages)
        meta = json.loads(key.read_text(encoding="utf-8"))
        self.assertEqual(len(meta["session_ids"]), len(pages))
        for sid, page in zip(meta["session_ids"], pages):
            self.assertIn(sid, page.read_text(encoding="utf-8"))
        files = []
        for n, (sid, session) in enumerate(zip(meta["session_ids"], meta["sessions"])):
            answers = [{"pair_id": p["pair_id"], "choice": "left" if p["left"]["variant"] in {"edited", "human"} else "right"}
                       for p in session]
            res = self.f.root / f"answers-{n}.json"
            res.write_text(json.dumps({"session_id": sid, "answers": answers}), encoding="utf-8")
            files.append(res)
        s = self.cli("score", "--key", key, "--results", *files, "--candidate", "edited")
        self.assertEqual(s.returncode, 0, s.stderr)
        report = json.loads(s.stdout)
        self.assertEqual(report["candidate_wins"], report["main_pairs"])
        self.assertEqual(report["attention_checks"]["rate"], 1.0)

    def test_refuses_key_inside_session_folder_and_overwrites(self):
        out = self.f.root / "세션"
        r = self.cli("build", "--items", self.f.items_path, "--variants", self.f.variants, "--compare", "raw,edited",
                     "--out", out, "--key", out / "key.json", "--seed", 3)
        self.assertEqual(r.returncode, 3)
        self.assertIn("정답 키", r.stderr)
        key = self.f.root / "key.json"
        key.write_text("{}", encoding="utf-8")
        r = self.cli("build", "--items", self.f.items_path, "--variants", self.f.variants, "--compare", "raw,edited",
                     "--out", self.f.root / "새 세션", "--key", key, "--seed", 3)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(key.read_text(encoding="utf-8"), "{}")

    def test_rejects_key_equal_to_session_folder(self):
        out = self.f.root / "같은 경로"
        r = self.cli("build", "--items", self.f.items_path, "--variants", self.f.variants, "--compare", "raw,edited",
                     "--out", out, "--key", out, "--seed", 3)
        self.assertEqual(r.returncode, 3)
        self.assertFalse(out.exists())

    def test_rebuilt_sessions_get_new_ids_when_texts_change(self):
        a = NE.session_id(1, 1, [{"pair_id": "s01p01", "left": {"text": "가"}, "right": {"text": "나"}}])
        b = NE.session_id(1, 1, [{"pair_id": "s01p01", "left": {"text": "가"}, "right": {"text": "다"}}])
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("1-01-"))

    def test_rejects_same_variant_twice(self):
        r = self.cli("build", "--items", self.f.items_path, "--compare", "raw,raw", "--out", self.f.root / "o",
                     "--key", self.f.root / "k.json", "--seed", 1)
        self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
