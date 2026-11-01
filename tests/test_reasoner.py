import json

import httpx
import pytest

from common.config import ROOT
from contracts.models import BenchEvent, Flag, Procedure
from services.knowledge.parse import hierarchy, read_pages
from services.knowledge.retrieve import Excerpt
from services.reasoner.agent import rework_steps, template_report
from services.reasoner.context import memories, notes_by_step
from services.reasoner.judge import Decision, ask_rules, judge, verified_citations
from services.reasoner.meko import MekoClient, MekoError

PROCEDURE = Procedure(**json.loads((ROOT / "tests" / "fixtures" / "procedure.json").read_text()))
LEAVES = {leaf.section: leaf for s in hierarchy(read_pages(ROOT / "tests" / "fixtures" / "vg100.md")) for leaf in s.leaves}
EXCERPTS = [Excerpt(section, LEAVES[section].page, LEAVES[section].title, LEAVES[section].body, "step") for section in ("4.1", "4.2", "4.3")]
EVENT = BenchEvent(id="e", bench="b", run_id="r", kind="pick", zone="B", frame_offset=1)


def flag(revision="A", reason="out_of_sequence", expected="S1", actual="S2") -> Flag:
    return Flag(id="f", bench="b", run_id="r", event=EVENT, reason=reason, expected_step=expected, actual_step=actual, unit_revision=revision)


def test_e1_rules_confirm_on_rev_a():
    decision = ask_rules(flag("A"), PROCEDURE, EXCERPTS)
    assert decision.status == "confirmed"
    assert decision.spoken == "Stop. Install the gasket first."


def test_e3_rules_clear_on_rev_b_by_quoting_the_note():
    decision = ask_rules(flag("B"), PROCEDURE, EXCERPTS)
    assert decision.status == "cleared"
    assert "skip step 4.1" in decision.citations[0]["quote"]


def test_rev_b_note_can_never_clear_a_rev_a_unit():
    quote = "On a Rev B unit, skip step 4.1 and start at step 4.2."
    wrong = lambda prompt, frames: Decision("cleared", "The manual allows this.", [{"section": "4.1", "quote": quote}], "", "m")
    verdict = judge(flag("A"), PROCEDURE, EXCERPTS, [], [], ask=wrong)
    assert verdict.status == "confirmed" and verdict.model == "local-rules"
    assert verdict.spoken == "Stop. Install the gasket first."


def test_clear_with_a_quote_naming_no_revision_is_refused():
    wrong = lambda prompt, frames: Decision("cleared", "Fine.", [{"section": "4.1", "quote": "Take the gasket from bin A."}], "", "m")
    assert judge(flag("A"), PROCEDURE, EXCERPTS, [], [], ask=wrong).status == "confirmed"


def test_rev_b_note_still_clears_a_rev_b_unit():
    quote = "On a Rev B unit, skip step 4.1 and start at step 4.2."
    right = lambda prompt, frames: Decision("cleared", "Allowed.", [{"section": "4.1", "quote": quote}], "", "m")
    verdict = judge(flag("B"), PROCEDURE, EXCERPTS, [], [], ask=right)
    assert verdict.status == "cleared" and verdict.model == "m"


def test_rules_cannot_pass_a_photo_check():
    decision = ask_rules(flag(reason="step_check", expected="S3", actual=None), PROCEDURE, EXCERPTS)
    assert decision.status == "uncertain"


def test_photo_check_with_no_photo_never_reaches_the_model():
    def fail(prompt, frames):
        raise AssertionError("the model must not be asked")

    verdict = judge(flag(reason="step_check", expected="S3", actual=None), PROCEDURE, EXCERPTS, [], [], ask=fail)
    assert verdict.status == "uncertain"


def test_true_quote_is_accepted_with_page_from_the_manual():
    decision = Decision("confirmed", "x", [{"section": "4.3", "quote": "The cable must not pass through notch B."}], "", "m")
    citations = verified_citations(decision, EXCERPTS)
    assert citations[0].page == 7


def test_section_and_page_come_from_the_manual_not_the_model():
    decision = Decision("cleared", "x", [{"section": "Section 9.9, page 99", "quote": "skip step 4.1 and start at step 4.2"}], "", "m")
    citations = verified_citations(decision, EXCERPTS)
    assert citations[0].section == "4.1" and citations[0].page == 6


def test_empty_quote_is_rejected():
    decision = Decision("confirmed", "x", [{"section": "4.1", "quote": ""}], "", "m")
    assert verified_citations(decision, EXCERPTS) is None


def test_invented_quote_on_a_photo_check_downgrades_to_uncertain():
    fake = lambda prompt, frames: Decision("cleared", "fine", [{"section": "4.3", "quote": "Notch B is approved for all cables."}], "", "m")
    verdict = judge(flag(reason="step_check", expected="S3", actual=None), PROCEDURE, EXCERPTS, [], [b"jpg"], ask=fake)
    assert verdict.status == "uncertain"
    assert verdict.citations == []


def test_invented_quote_can_never_clear_an_order_fault():
    fake = lambda prompt, frames: Decision("cleared", "fine", [{"section": "4.3", "quote": "Rev A units may skip anything."}], "", "m")
    verdict = judge(flag("A"), PROCEDURE, EXCERPTS, [], [], ask=fake)
    assert verdict.status == "uncertain"
    assert verdict.citations == []


def test_verdict_with_no_citation_downgrades_to_uncertain():
    fake = lambda prompt, frames: Decision("confirmed", "bad", [], "Stop.", "m")
    verdict = judge(flag(), PROCEDURE, EXCERPTS, [], [], ask=fake)
    assert verdict.status == "uncertain" and verdict.spoken is None


def test_model_failure_falls_back_to_rules():
    def broken(prompt, frames):
        raise TimeoutError("slow")

    verdict = judge(flag(), PROCEDURE, EXCERPTS, [], [], ask=broken)
    assert verdict.status == "confirmed" and verdict.model == "local-rules"


def test_prompt_carries_revision_and_notes():
    seen = {}

    def spy(prompt, frames):
        seen["prompt"] = prompt
        return Decision("uncertain", "x", [], "", "m")

    judge(flag("B"), PROCEDURE, EXCERPTS, ["Fault 2 at S1"], [b"jpg"], ask=spy)
    assert "Unit revision: B" in seen["prompt"]
    assert "Fault 2 at S1" in seen["prompt"]
    assert "Note 4.1" in seen["prompt"]


def test_rework_undoes_later_steps_latest_first():
    plan = rework_steps(PROCEDURE, "S2", ["S1", "S2", "S3", "S4"])
    assert plan[0].startswith("Undo S4") and plan[1].startswith("Undo S3") and plan[-1].startswith("Do S2")
    assert not any(line.startswith("Undo S1") for line in plan)


def test_rework_for_first_missing_step_only_does_that_step():
    assert rework_steps(PROCEDURE, "S1", []) == ["Do S1: Lay the gasket in the tray"]


def test_third_fault_cites_the_repeat_rule():
    verdict = judge(flag(), PROCEDURE, EXCERPTS, [], [])
    assert "section 6.4" in template_report(verdict, ["Do S1"], 3)
    assert "section 6.4" not in template_report(verdict, ["Do S1"], 2)


def meko(handler) -> MekoClient:
    return MekoClient("https://meko.test/mcp", "mko_tkn_test", transport=httpx.MockTransport(handler))


def test_meko_sends_bearer_key_user_agent_and_session():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((body.get("method"), dict(request.headers)))
        if body.get("method") == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}}, headers={"mcp-session-id": "s1"})
        if "id" not in body:
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "{\"conversation_id\": \"c1\"}"}]}})

    result = meko(handler).call("conversation_create", agent_id="a", title=None)
    assert result == {"conversation_id": "c1"}
    method, headers = seen[-1]
    assert method == "tools/call"
    assert headers["authorization"] == "Bearer mko_tkn_test"
    assert headers["mcp-session-id"] == "s1"
    assert headers["user-agent"] == "vigil/0.1"


def test_meko_reads_sse_and_double_encoded_results():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "id" not in body:
            return httpx.Response(202)
        inner = json.dumps(json.dumps({"results": [{"memory": "Fault at S3"}]}))
        result = {"content": [{"type": "text", "text": inner}]}
        text = "data: " + json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result}) + "\n\n"
        return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})

    assert memories(meko(handler).call("memory_search", query="x")) == ["Fault at S3"]


def test_meko_tool_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "id" not in body:
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"isError": True, "content": [{"type": "text", "text": "conversation_id Missing"}]}})

    with pytest.raises(MekoError, match="conversation_id"):
        meko(handler).call("memory_search", query="x")


def test_meko_error_returned_as_data_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "id" not in body:
            return httpx.Response(202)
        text = json.dumps({"error": "conversation_id_required", "detail": "Pass conversation_id."})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": text}]}})

    with pytest.raises(MekoError, match="conversation_id_required"):
        meko(handler).call("datapack_search", name="x")


def test_memories_group_by_their_step():
    found = {"results": [{"memory": "a", "metadata": {"step_id": "S3"}}, {"memory": "b", "metadata": {"step_id": "S1"}}, {"memory": "c", "metadata": {}}]}
    assert notes_by_step(found) == {"S3": ["a"], "S1": ["b"]}
