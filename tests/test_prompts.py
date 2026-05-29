from astra.config import AstraConfig
from astra.prompts import build_batch_prompt, build_campaign_prompt, build_format_prompt, build_ideas_prompt, build_posts_prompt, build_reply_prompt, build_rewrite_prompt, build_system_prompt


def test_system_prompt_includes_astra_rules() -> None:
    config = AstraConfig()
    prompt = build_system_prompt(config)
    assert "PR and marketing operator for LinnuteeInnovations" in prompt
    assert "practical builder explaining useful work plainly" in prompt
    assert "Continuity Layer" in prompt
    assert "Stop re-explaining your project to AI." in prompt
    assert "Human approval remains required" in prompt
    assert "morning, afternoon, or evening" in prompt
    assert "practical builder" in "; ".join(config.tone)
    assert "plainspoken and transparent" in "; ".join(config.tone)


def test_ideas_prompt_includes_platform_guidance() -> None:
    prompt = build_ideas_prompt("Continuity Layer launch", 7, "reddit")
    assert "Generate 7 ranked PR and marketing ideas" in prompt
    assert "useful discussion prompts" in prompt
    assert '"ideas"' in prompt
    assert "buyer feedback loops" in prompt
    assert "honest feedback asks" in prompt


def test_batch_prompt_includes_master_schema() -> None:
    prompt = build_batch_prompt("Continuity Layer launch", 5)
    assert "master PR/marketing drafts" in prompt
    assert '"hashtags"' in prompt
    assert '"suggested_post_time"' in prompt
    assert 'Good hook patterns include: "I keep seeing builders lose time to X."' in prompt
    assert "Follow this flow: pain, product/context, trust boundary, clear ask." in prompt
    assert "Do not pretend the company has traction" in prompt
    assert "Platform notes are required" in prompt


def test_format_prompt_differs_for_youtube_shorts() -> None:
    prompt = build_format_prompt({"topic": "Continuity Layer launch"}, "hacker_news")
    assert "technically inspectable" in prompt
    assert "channel-optimized opening line" in prompt
    assert "GitHub for inspection" in prompt
    assert "Platform notes are required" in prompt
    assert "Follow this flow: pain, product/context, trust boundary, clear ask." in prompt


def test_rewrite_prompt_includes_safety_recovery_guidance() -> None:
    prompt = build_rewrite_prompt({"topic": "AI panic"}, safety_reasons=["Tone needs calmer language."])
    assert "Tone needs calmer language." in prompt
    assert "Reduce certainty on uncertain claims." in prompt
    assert "Bring the draft back to Astra's LinnuteeInnovations PR marketer identity first." in prompt


def test_pr_native_prompts_include_campaign_posts_and_replies() -> None:
    product = AstraConfig().active_product
    campaign = build_campaign_prompt("Launch", product)
    assert "7-day product marketing campaign" in campaign
    assert "reply_focus" in campaign
    assert "`channel` value must be exactly one of these machine IDs" in campaign
    assert "Do not imply anything will auto-post" in campaign

    posts = build_posts_prompt(product, "reddit", 3, goal="Launch")
    assert "Draft 3 platform-native product marketing posts" in posts
    assert "review" in posts.lower()

    reply = build_reply_prompt(product, "why_not_readme_notion", user_signal="Why not Notion?")
    assert "README/Notion" in reply
    assert "practical founder" in reply
