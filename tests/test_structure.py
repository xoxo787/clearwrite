import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clearwrite.core import apply_plan, prepare, text_hash, verify  # noqa: E402
from clearwrite.personas import DEFAULT_PERSONA, PERSONAS, gate_options, get_persona, persona_instruction  # noqa: E402
from clearwrite.structure import diagnosis_instruction, structure_signals  # noqa: E402

AI_LIKE = ("주말 아침, 설레는 마음으로 도서관으로 발걸음을 옮겼습니다. 문을 열고 들어서자, 주민들이 삼삼오오 모여 있었고, "
           "강의실은 활기를 띠고 있었습니다. 첫째, 강사는 책을 소개했습니다. 둘째, 주민들은 질문했습니다. "
           "도서관이 단순히 책을 빌리는 곳이 아니라 배움터로 바뀌는 순간이었습니다. 가슴 한구석이 벅차올랐습니다. "
           "과연 다음 강좌는 어떨까요? 저의 일주일을 소개합니다.")
PLAIN = ("토요일에 도서관 강좌에 갔다. 강사는 첫 시간에 책 두 권을 골라 왔다. 질문이 많아서 강의는 20분 늦게 끝났다. "
         "다음 주에는 아이를 데려갈 생각이다.")


class SignalTests(unittest.TestCase):
    def test_counts_each_pattern_with_examples(self):
        s = structure_signals(AI_LIKE)
        p = s["patterns"]
        self.assertGreaterEqual(p["ending_comma"]["count"], 2)
        self.assertEqual(p["enumeration"]["count"], 2)
        self.assertGreaterEqual(p["teaser"]["count"], 2)
        self.assertGreaterEqual(p["wrap_up"]["count"], 2)
        self.assertGreaterEqual(p["stock_phrase"]["count"], 3)
        self.assertEqual(p["not_only"]["count"], 1)
        self.assertTrue(set(s["dominant"]) >= {"enumeration", "teaser", "wrap_up", "stock_phrase"})
        self.assertTrue(all(len(v["examples"]) <= 3 for v in p.values()))
        self.assertIn("AI 작성 판정이 아니다", s["interpretation"])

    def test_plain_prose_has_no_dominant_pattern(self):
        s = structure_signals(PLAIN)
        self.assertEqual(s["dominant"], [])
        self.assertIn("억지로 고칠 곳을 만들지 않는다", diagnosis_instruction(s))

    def test_single_ordinal_is_not_an_enumeration(self):
        self.assertEqual(structure_signals("첫째 아이가 학교에 갔다. 나는 집에 있었다.")["patterns"]["enumeration"]["count"], 0)

    def test_quotes_and_code_are_not_counted(self):
        quoted = '그는 "가슴이 벅차올랐고, 눈 녹듯 사라진 순간이었다"라고 적었다.\n\n```\n첫째, 둘째,\n```\n'
        p = structure_signals(quoted)["patterns"]
        self.assertEqual((p["wrap_up"]["count"], p["stock_phrase"]["count"], p["enumeration"]["count"]), (0, 0, 0))

    def test_diagnosis_names_dominant_patterns_and_keeps_information(self):
        text = diagnosis_instruction(structure_signals(AI_LIKE))
        self.assertIn("상투적인 묘사 표현", text)
        self.assertIn("정보·장면·대화·조건은 그대로 둔다", text)

    def test_uniformity_is_reference_only(self):
        u = structure_signals(AI_LIKE)["uniformity"]
        self.assertIsNotNone(u["sentence_length_cv"])
        self.assertIn("일부러 들쭉날쭉하게 만들지 않는다", u["note"])


class PersonaTests(unittest.TestCase):
    def test_natural_persona_shape(self):
        n = get_persona("natural")
        self.assertEqual((n.intensity, n.policy, n.max_change, n.restructure, n.min_retention), ("strong", "safe-subset", .5, True, .75))
        self.assertFalse(n.changes_voice)
        self.assertEqual(DEFAULT_PERSONA, "editor")
        self.assertEqual([p.id for p in PERSONAS.values() if p.restructure], ["natural"])

    def test_gate_options(self):
        self.assertEqual(gate_options(get_persona("natural")), {"min_retention": .75, "local_compression": False})
        self.assertEqual(gate_options(get_persona("editor")), {"min_retention": .85, "local_compression": True})
        self.assertEqual(gate_options(get_persona("natural"), .9)["min_retention"], .9)
        self.assertEqual(gate_options(get_persona("natural"), 0)["min_retention"], 0)

    def test_natural_prompt_allows_paragraph_rewrites_and_keeps_limits(self):
        text = persona_instruction(get_persona("natural"))
        self.assertIn("여러 문장을 한 편집으로 묶어", text)
        self.assertIn("replacement는 빈 문자열", text)
        self.assertIn("숫자·조건·가능성이 든 문장은 지우지 않는다", text)
        self.assertNotIn("한 편집은 한 문장을 넘지 않게", text)
        self.assertIn("부정·가능성·조건", text)

    def test_prepare_adds_diagnosis_only_for_natural(self):
        natural, editor = prepare(AI_LIKE, persona="natural"), prepare(AI_LIKE, persona="editor")
        self.assertIn("구조 진단", natural["instruction"])
        self.assertNotIn("구조 진단", editor["instruction"])
        self.assertIn("structure", natural)
        self.assertIn("structure", editor)
        self.assertNotIn("구조 진단", prepare(AI_LIKE, persona="natural", mode="preserve")["instruction"])


def deletion_plan(text, original):
    a = text.index(original)
    return {"schema_version": "1.0", "source_sha256": text_hash(text),
            "edits": [{"start": a, "end": a + len(original), "original": original, "replacement": "", "reason": "정보 없는 감상", "rule": "wrap_up"}]}


LONG = ("지난 토요일 아침 아홉 시에 동네 도서관 강좌에 처음 갔다. 강사는 첫 시간에 읽을 책 두 권을 골라 와서 한 권씩 앞부분을 소리 내어 읽어 주었다. "
        "주민들은 읽은 대목을 두고 저마다 떠오른 경험을 이야기했고, 질문이 끊이지 않아 강의는 예정보다 이십 분 늦게 끝났다. "
        "돌아오는 길에 빌린 책을 가방에 넣고 다음 주 강좌 신청서도 받아 왔다. 도서관이 책을 빌리는 곳을 넘어 배움과 나눔의 따뜻한 공간으로 바뀌는 뜻깊은 순간이었다. "
        "다만 강좌 신청은 선착순 30명까지만 받을 수 있다.")


EMPTY = "도서관이 책을 빌리는 곳을 넘어 배움과 나눔의 따뜻한 공간으로 바뀌는 뜻깊은 순간이었다. "


class GateTests(unittest.TestCase):
    def test_natural_may_delete_an_empty_sentence(self):
        plan = deletion_plan(LONG, EMPTY)
        r = apply_plan(LONG, plan, policy="safe-subset", max_change=.5, **gate_options(get_persona("natural")))
        self.assertEqual(r["status"], "edited", r["rejected_edits"])
        self.assertNotIn("뜻깊은 순간", r["text"])

    def test_editor_still_blocks_the_same_deletion(self):
        plan = deletion_plan(LONG, EMPTY)
        r = apply_plan(LONG, plan, policy="safe-subset", max_change=.5, **gate_options(get_persona("editor")))
        self.assertEqual(r["rejected_edits"][0]["reason"], "excessive_local_compression")

    def test_natural_cannot_delete_numbers_or_conditions(self):
        plan = deletion_plan(LONG, "다만 강좌 신청은 선착순 30명까지만 받을 수 있다.")
        r = apply_plan(LONG, plan, policy="safe-subset", max_change=.5, **gate_options(get_persona("natural")))
        self.assertEqual(r["status"], "unchanged")
        self.assertEqual(r["rejected_edits"][0]["reason"], "numbers_units_or_order_changed")

    def test_natural_keeps_the_document_length_floor(self):
        floor = gate_options(get_persona("natural"))["min_retention"]
        check = verify(LONG, LONG[: len(LONG) // 2], max_change=.5, min_retention=floor)
        self.assertIn("excessive_document_compression", check["failures"])
        self.assertFalse(verify(LONG, LONG.replace(EMPTY, ""), max_change=.5, min_retention=floor)["failures"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="구조 편집 ")
        self.root = Path(self.tmp.name)
        self.src = self.root / "원문.txt"
        self.src.write_bytes(LONG.encode("utf-8"))
        self.plan = self.root / "제안.json"
        p = deletion_plan(LONG, EMPTY)
        for e in p["edits"]:
            del e["start"], e["end"]
        self.plan.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "rewrite.py"), *map(str, args)], capture_output=True,
                              text=True, encoding="utf-8", timeout=30)

    def test_apply_with_natural_reports_gates(self):
        report = self.root / "report.json"
        r = self.run_cli("apply", self.src, "--proposals", self.plan, "--persona", "natural", "-o", self.root / "out.txt", "--report", report)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(data["gates"], {"min_retention": .75, "local_compression": False})
        self.assertEqual(data["edit_budget"], {"max_change": .5, "policy": "safe-subset"})

    def test_explicit_min_retention_still_wins(self):
        report = self.root / "report2.json"
        r = self.run_cli("apply", self.src, "--proposals", self.plan, "--persona", "natural", "--min-retention", ".9",
                         "-o", self.root / "out2.txt", "--report", report)
        # A stricter explicit floor blocks the same deletion: the document keeps under 90%.
        self.assertEqual(r.returncode, 2, r.stderr)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(data["gates"]["min_retention"], .9)
        self.assertIn("excessive_document_compression", data["verification"]["failures"])

    def test_editor_default_is_unchanged(self):
        report = self.root / "report3.json"
        r = self.run_cli("apply", self.src, "--proposals", self.plan, "-o", self.root / "out3.txt", "--report", report)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["gates"], {"min_retention": .85, "local_compression": True})


class SkillTextTests(unittest.TestCase):
    def test_skill_offers_natural_and_ships_the_pattern_guide(self):
        skill = (ROOT / "skills/clearwrite/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("③ 자연스럽게", skill)
        self.assertIn("`natural` 자연스러운 글 편집자", skill)
        self.assertIn("references/structure_patterns.md", skill)
        guide = (ROOT / "skills/clearwrite/references/structure_patterns.md").read_text(encoding="utf-8")
        for key in ["ending_comma", "enumeration", "teaser", "wrap_up", "stock_phrase", "not_only"]:
            self.assertIn(f"`{key}`", guide)
        self.assertIn("탐지기 점수를 기준으로 고치지 않는다", guide)


if __name__ == "__main__":
    unittest.main()
