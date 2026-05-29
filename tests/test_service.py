from astra.config import AstraConfig
from astra.models import WorkflowContentItem
from astra.service import AstraGenerator, ollama_transport_factory
import json


def test_generator_parses_ideas_response() -> None:
    generator = AstraGenerator(
        AstraConfig(api_key="x"),
        transport=lambda **_: '{"ideas":[{"topic":"AI shame spiral","reason":"It creates tension fast."}]}',
    )
    ideas = generator.generate_ideas(topic="AI", count=5, platform="tiktok")
    assert ideas[0].rank == 1
    assert ideas[0].topic == "AI shame spiral"


def test_ollama_transport_sends_json_request(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "{\"ideas\":[]}"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("astra.service.urlrequest.urlopen", fake_urlopen)
    transport = ollama_transport_factory(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")

    result = transport(system_prompt="system", user_prompt="user", model="ignored")

    assert result == "{\"ideas\":[]}"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["payload"]["model"] == "llama3.1:8b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"] == "json"
    assert "System:" in captured["payload"]["prompt"]


def test_ollama_transport_unavailable_has_clear_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise OSError("offline")

    monkeypatch.setattr("astra.service.urlrequest.urlopen", fake_urlopen)
    transport = ollama_transport_factory(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")

    try:
        transport(system_prompt="system", user_prompt="user", model="ignored")
    except RuntimeError as exc:
        assert "Ollama is not reachable" in str(exc)
        assert "ollama serve" in str(exc)
    else:
        raise AssertionError("Expected Ollama transport to fail clearly.")


def test_generator_rewrites_weak_post() -> None:
    responses = iter(
        [
            '{"posts":[{"topic":"AI trust","hook":"This is a very long and generic hook that should be rewritten fast","script_lines":["This line is too bloated for Astra content because it keeps going for too long"],"caption":"This caption is also too long and too explanatory for a sharp social post.","hashtags":["#ai"],"platform_notes":null,"retention_check":"The contrast keeps attention","suggested_post_time":"afternoon"}]}',
            '{"topic":"AI trust","hook":"AI feels smart. Useful is scarier.","script_lines":["Smart impressed people.","Useful replaced them."],"caption":"Useful changes the game.","hashtags":["#ai"],"platform_notes":null,"retention_check":"The hook flips the angle instantly","suggested_post_time":"morning"}',
        ]
    )
    generator = AstraGenerator(AstraConfig(api_key="x"), transport=lambda **_: next(responses))

    posts = generator.generate_posts(topic="AI trust", count=1)

    assert posts[0].hook == "AI feels smart. Useful is scarier."
    assert posts[0].caption == "Useful changes the game."


def test_generator_rewrites_short_but_overly_conclusive_post() -> None:
    responses = iter(
        [
            '{"posts":[{"topic":"AI trust","hook":"AI is changing fast.","script_lines":["In reality, the answer is simple.","It is just a tool."],"caption":"The truth is simpler than people think.","hashtags":["#ai"],"platform_notes":null,"retention_check":"It is clear and direct.","suggested_post_time":"afternoon"}]}',
            '{"topic":"AI trust","hook":"What if the scary part is not what you think?","script_lines":["Everyone watches the headline.","But here\'s the part nobody talks about...","It gets stranger when the tool starts shaping behavior."],"caption":"The answer is not the weird part.","hashtags":["#ai"],"platform_notes":null,"retention_check":"The open loop keeps the tension alive.","suggested_post_time":"evening"}',
        ]
    )
    generator = AstraGenerator(AstraConfig(api_key="x"), transport=lambda **_: next(responses))

    posts = generator.generate_posts(topic="AI trust", count=1)

    assert posts[0].hook == "What if the scary part is not what you think?"
    assert "But here's the part nobody talks about..." in posts[0].script_lines


def test_generator_rewrites_flat_or_preachy_post() -> None:
    responses = iter(
        [
            '{"posts":[{"topic":"Focus","hook":"Focus matters.","script_lines":["You need to stop multitasking.","The lesson is simple."],"caption":"This is about improving focus.","hashtags":["#focus"],"platform_notes":"calm","retention_check":"It is clear and direct.","suggested_post_time":"afternoon"}]}',
            '{"topic":"Focus","hook":"This should work... but it does not.","script_lines":["More tabs should feel productive.","Instead they split your attention.","You did not change... the environment did.","That shift changes what focus feels like."],"caption":"More effort does not fix a scattered environment.","hashtags":["#focus"],"platform_notes":"fast cuts, highlight \\"environment\\"","retention_check":"The shift lands without fully closing the loop.","suggested_post_time":"evening"}',
        ]
    )
    generator = AstraGenerator(AstraConfig(api_key="x"), transport=lambda **_: next(responses))

    posts = generator.generate_posts(topic="Focus", count=1)

    assert posts[0].hook == "This should work... but it does not."
    assert posts[0].platform_notes == 'fast cuts, highlight "environment"'


def test_generator_rewrites_bad_platform_note_tone() -> None:
    responses = iter(
        [
            '{"posts":[{"topic":"Attention","hook":"You did not change... the feed did.","script_lines":["The pattern looks harmless.","Then it starts shaping your reflexes.","That shift is easy to miss."],"caption":"The feed changes the pace before you notice it.","hashtags":["#attention"],"platform_notes":"fast cuts, tone slightly rebellious","retention_check":"The shift stays open enough to think about.","suggested_post_time":"evening"}]}',
            '{"topic":"Attention","hook":"You did not change... the feed did.","script_lines":["The pattern looks harmless.","Then it starts shaping your reflexes.","That shift is easy to miss."],"caption":"The feed changes the pace before you notice it.","hashtags":["#attention"],"platform_notes":"fast cuts, hold a short pause on the shift line","retention_check":"The shift stays open enough to think about.","suggested_post_time":"evening"}',
        ]
    )
    generator = AstraGenerator(AstraConfig(api_key="x"), transport=lambda **_: next(responses))

    posts = generator.generate_posts(topic="Attention", count=1)

    assert "rebellious" not in (posts[0].platform_notes or "").lower()


def test_generator_formats_master_item_for_platform() -> None:
    generator = AstraGenerator(
        AstraConfig(api_key="x"),
        transport=lambda **_: '{"topic":"AI trust","hook":"AI trust should feel simple... but it does not.","script_lines":["It looks like a tool story.","What matters more is how it changes leverage quietly."],"caption":"Leverage shifts before people have language for it.","hashtags":["#ai","#tiktok"],"platform_notes":"Fast cuts. Highlight leverage.","retention_check":"The hook creates immediate pressure.","suggested_post_time":"evening"}',
    )
    master = WorkflowContentItem(
        id="abc12345",
        topic="AI trust",
        hook="AI trust is changing fast",
        script_lines=["line one", "line two"],
        caption="caption",
        hashtags=["#ai"],
        platform="master",
        suggested_post_time="afternoon",
        status="draft",
        created_at="2026-03-29T00:00:00Z",
        workflow_stage="master",
        retention_check="It keeps the idea moving.",
    )

    item = generator.format_for_platform(master, "tiktok")

    assert item.platform == "tiktok"
    assert item.workflow_stage == "platform_variant"
    assert item.source_item_id == "abc12345"
    assert item.safety.decision == "PASS"


def test_generator_discards_post_that_still_fails_after_rewrite() -> None:
    responses = iter(
        [
            '{"posts":[{"topic":"Focus","hook":"This hook is far too long and generic to feel sharp in a short-form video format","script_lines":["In reality the answer is simple and you need to follow it immediately."],"caption":"This is about improving focus.","hashtags":["#focus"],"platform_notes":"calm","retention_check":"It explains the point clearly.","suggested_post_time":"afternoon"}]}',
            '{"topic":"Focus","hook":"Focus is harder now.","script_lines":["The truth is you need to fix your routine."],"caption":"The point is simple.","hashtags":["#focus"],"platform_notes":"calm","retention_check":"It stays direct.","suggested_post_time":"afternoon"}',
        ]
    )
    generator = AstraGenerator(AstraConfig(api_key="x"), transport=lambda **_: next(responses))

    items = generator.generate_workflow_items(topic="Focus", count=1)

    assert items[0].safety.decision == "DISCARD"
    assert "Rewrite did not clear the safety gate." in items[0].safety.reasons


def test_generator_rewrites_identity_drift_before_passing() -> None:
    responses = iter(
        [
            '{"posts":[{"topic":"Attention","hook":"This changes everything!!!","script_lines":["It is important to note that studies show a measurable shift."],"caption":"Therefore the result is obvious.","hashtags":["#attention"],"platform_notes":"Fast cuts. Highlight the shift.","retention_check":"It explains the point clearly.","suggested_post_time":"afternoon"}]}',
            '{"topic":"Attention","hook":"Attention should feel easier now... but it does not.","script_lines":["More tools should help.","What matters more is what they train your brain to expect.","That shift changes the feeling before people notice it."],"caption":"Convenience can change the pace before it looks important.","hashtags":["#attention"],"platform_notes":"Fast cuts. Highlight the shift.","retention_check":"It stays calm and leaves a small gap for thought.","suggested_post_time":"evening"}',
        ]
    )
    generator = AstraGenerator(AstraConfig(api_key="x"), transport=lambda **_: next(responses))

    posts = generator.generate_posts(topic="Attention", count=1)

    assert posts[0].hook == "Attention should feel easier now... but it does not."
    assert "What matters more is" in posts[0].script_lines[1]
