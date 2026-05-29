from astra.config import AstraConfig
from astra.models import WorkflowContentItem
from astra.service import AstraGenerator, check_ollama_health, ollama_transport_factory
import json
from urllib import error as urlerror


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

    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            captured["health_timeout"] = timeout
            return FakeResponse({"models": [{"name": "llama3.1:8b"}]})
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    class FakeResponse:
        def __init__(self, payload=None):
            self.payload = payload or {"response": "{\"ideas\":[]}"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    monkeypatch.setattr("astra.service.urlrequest.urlopen", fake_urlopen)
    transport = ollama_transport_factory(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")

    result = transport(system_prompt="system", user_prompt="user", model="ignored")

    assert result == "{\"ideas\":[]}"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["payload"]["model"] == "llama3.1:8b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"] == "json"
    assert "System:" in captured["payload"]["prompt"]
    assert captured["health_timeout"] == 5
    assert captured["timeout"] == 300


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


def test_ollama_health_reports_model_present(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"models": [{"name": "llama3.1:8b"}]}).encode("utf-8")

    monkeypatch.setattr("astra.service.urlrequest.urlopen", lambda request, timeout: FakeResponse())

    message = check_ollama_health(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")

    assert "Ollama is running" in message


def test_ollama_health_reports_missing_model(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"models": [{"name": "other:model"}]}).encode("utf-8")

    monkeypatch.setattr("astra.service.urlrequest.urlopen", lambda request, timeout: FakeResponse())

    try:
        check_ollama_health(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")
    except RuntimeError as exc:
        assert "model `llama3.1:8b` is missing" in str(exc)
        assert "ollama pull llama3.1:8b" in str(exc)
    else:
        raise AssertionError("Expected missing model error.")


def test_ollama_transport_timeout_says_running_but_slow(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "llama3.1:8b"}]})
        raise TimeoutError("slow")

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    monkeypatch.setattr("astra.service.urlrequest.urlopen", fake_urlopen)
    transport = ollama_transport_factory(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")

    try:
        transport(system_prompt="system", user_prompt="user", model="ignored")
    except RuntimeError as exc:
        assert "Ollama is running" in str(exc)
        assert "took too long" in str(exc)
        assert "ollama serve" not in str(exc)
    else:
        raise AssertionError("Expected slow generation timeout error.")


def test_ollama_health_server_unavailable(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise urlerror.URLError("offline")

    monkeypatch.setattr("astra.service.urlrequest.urlopen", fake_urlopen)

    try:
        check_ollama_health(base_url="http://127.0.0.1:11434", ollama_model="llama3.1:8b")
    except RuntimeError as exc:
        assert "Ollama is not reachable" in str(exc)
        assert "ollama serve" in str(exc)
    else:
        raise AssertionError("Expected unavailable server error.")


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


def test_generator_normalizes_ollama_shaped_product_posts_and_preserves_channel() -> None:
    generator = AstraGenerator(
        AstraConfig(api_key="x"),
        transport=lambda **_: json.dumps(
            {
                "posts": [
                    {
                        "topic": ["Continuity Layer", "launch"],
                        "hook": ["Stop re-explaining", "your project to AI?"],
                        "script_lines": [
                            {"pain": "Every agent starts cold", "fix": "Continuity packets carry the current state"},
                            "It is local-first and Windows-first while the beta is early.",
                        ],
                        "caption": {"cta": "GitHub is open", "offer": "$19 early access"},
                        "hashtags": ["#ai"],
                        "platform_notes": ["This sounds like Reddit even though the request is Bluesky."],
                        "retention_check": ["The pain is clear immediately"],
                        "suggested_post_time": "afternoon",
                    }
                ]
            }
        ),
    )

    items = generator.draft_product_posts(channel="x_bluesky", count=1, goal="Launch")

    assert items[0].platform == "x_bluesky"
    assert items[0].hook == "Stop re-explaining your project to AI?"
    assert items[0].caption == "cta: GitHub is open; offer: $19 early access"
    assert "requested Bluesky" in (items[0].platform_notes or "")


def test_generator_normalizes_ollama_shaped_campaign_and_reply() -> None:
    campaign_generator = AstraGenerator(
        AstraConfig(api_key="x"),
        transport=lambda **_: json.dumps(
            {
                "product": ["Continuity", "Layer"],
                "goal": ["Launch", "early access"],
                "summary": {"summary": "Founder-led launch with practical posts."},
                "days": [
                    {
                        "day": 1,
                        "channel": "reddit",
                        "angle": ["Ask about repeated context"],
                        "cta": {"primary": "GitHub"},
                        "reply_focus": ["workflow pain"],
                        "objection_to_watch": ["Why not README?"],
                        "tracking_goal": ["replies"],
                    }
                ],
                "notes": ["Review every draft before posting."],
            }
        ),
    )
    reply_generator = AstraGenerator(
        AstraConfig(api_key="x"),
        transport=lambda **_: json.dumps(
            {
                "product": ["Continuity", "Layer"],
                "scenario": "why_not_readme_notion",
                "user_signal": ["Why not just use Notion?"],
                "reply": {"ack": "Good question.", "difference": "Astra needs current agent-ready packets."},
                "follow_up": ["What context do you repeat most?"],
                "tracking_note": {"objection": "docs comparison"},
            }
        ),
    )

    plan = campaign_generator.generate_campaign_plan(goal="Launch", days=7)
    reply = reply_generator.draft_reply(scenario="why_not_readme_notion")

    assert plan.product == "Continuity Layer"
    assert plan.days[0].cta == "primary: GitHub"
    assert reply.reply == "ack: Good question.; difference: Astra needs current agent-ready packets."


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
