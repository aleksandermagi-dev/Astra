from __future__ import annotations

from textwrap import dedent

from .config import AstraConfig


IDEA_GUIDANCE = {
    "reddit": "Bias toward useful discussion prompts, transparent founder context, and specific requests for feedback.",
    "x_bluesky": "Bias toward short practical build-in-public observations, product lessons, and clear next-step CTAs.",
    "indie_hackers": "Bias toward founder narrative, validation learning, pricing, buyer pain, and honest traction updates.",
    "hacker_news": "Bias toward technical substance, plain limitations, Show HN readiness, and direct product inspection.",
    "devto": "Bias toward practical technical explanation, workflows, examples, and lessons for builders.",
    "email_update": "Bias toward concise company/product updates for people who already opted in.",
    "direct_reply": "Bias toward calm, specific, human replies that answer objections without defensiveness.",
    "tiktok": "Legacy short-form channel: bias toward compact practical observations without hype.",
    "youtube_shorts": "Legacy short-form channel: bias toward clear practical observations without hype.",
    "all": "Generate channel-flexible PR ideas for LinnuteeInnovations that can become campaigns, posts, replies, experiments, or buyer feedback loops.",
}

FORMAT_GUIDANCE = {
    "reddit": "Make it feel like a real community post: specific context, no sales gloss, useful details, and a direct feedback ask.",
    "x_bluesky": "Make it concise, concrete, and easy to quote or reply to. One clear idea, one clear CTA.",
    "indie_hackers": "Make it founder-led: why this exists, what is being tested, what the buyer pain is, and what feedback matters.",
    "hacker_news": "Make it technically inspectable: direct, restrained, transparent about limits, and worthy of a Show HN comment thread.",
    "devto": "Make it a practical builder article with concrete workflow examples, implementation notes, and honest tradeoffs.",
    "email_update": "Make it a compact update: what changed, why it matters, links, and one reply-worthy question.",
    "direct_reply": "Make it a natural reply: acknowledge the point, answer specifically, and invite one useful next step.",
    "tiktok": "Legacy short-form channel: keep it compact, practical, and non-hypey.",
    "youtube_shorts": "Legacy short-form channel: keep it clear, practical, and non-hypey.",
}

REPLY_SCENARIO_GUIDANCE = {
    "skeptical_user": "Answer skepticism calmly. Acknowledge the concern, clarify the real trust boundary, and avoid arguing.",
    "interested_builder": "Help an interested builder decide whether it fits their workflow. Be specific and invite a next step.",
    "setup_lead": "Respond to someone considering setup help. Keep the setup offer useful, optional, and non-pushy.",
    "why_not_readme_notion": "Compare against README/Notion honestly: useful docs are good, but agents need compact current working context, checks, decisions, and unresolved state.",
}


def _product_context(config: AstraConfig) -> str:
    product = config.active_product
    audience = "; ".join(product.get("audience", []))
    trust_points = "; ".join(product.get("trust_points", []))
    links = product.get("links", {})
    return dedent(
        f"""
        Active product campaign:
        - Product: {product.get("name", "Unknown product")}
        - Positioning: {product.get("positioning", "")}
        - Summary: {product.get("summary", "")}
        - Target users: {audience}
        - Offer: {product.get("offer", "")}
        - GitHub: {links.get("github", "")}
        - Checkout: {links.get("checkout", "")}
        - Feedback/setup form: {links.get("feedback_setup", "")}
        - Trust and safety facts: {trust_points}
        """
    ).strip()


def build_system_prompt(config: AstraConfig) -> str:
    return dedent(
        f"""
        You are Project Astra, the PR and marketing operator for {config.company_name}.
        Official role: {config.company_role}
        Audience: {'; '.join(config.audience)}
        Tone: {'; '.join(config.tone)}
        Style: {'; '.join(config.style)}
        {_product_context(config)}

        Core identity:
        - Astra maintains the LinnuteeInnovations public voice across company PR and product campaigns.
        - Sound like a practical builder explaining useful work plainly.
        - Be transparent about constraints, trust boundaries, and open questions.
        - Convert product memory into launch campaigns, posts, replies, experiments, and buyer feedback loops.
        - Never sound hypey, spammy, manipulative, defensive, dramatic, academic, robotic, or exaggerated.

        Core behavior:
        - Draft, plan, track, analyze, and help respond. Human approval remains required.
        - Do not blindly spam, auto-post, or imply public action has already happened.
        - Treat Continuity Layer as the active campaign, not the whole company identity.
        - Adapt to each channel's norms instead of copying one generic post everywhere.
        - Keep buyer pain, product facts, trust disclosures, and feedback asks concrete.
        - Include limitations when relevant, especially Windows-first beta and unsigned installer warnings.
        - Use direct CTAs only when useful: GitHub, checkout, or feedback/setup form.
        - Platform notes are required and must include practical posting, response, or tracking guidance.
        - Suggest only morning, afternoon, or evening for suggested_post_time.
        """
    ).strip()


def build_ideas_prompt(topic: str | None, count: int, platform: str) -> str:
    topic_text = topic.strip() if topic else "No topic provided. Generate the strongest Astra-ready ideas."
    return dedent(
        f"""
        Generate {count} ranked PR and marketing ideas for LinnuteeInnovations.
        Topic context: {topic_text}
        Channel guidance: {IDEA_GUIDANCE[platform]}

        Return strict JSON with this shape:
        {{
          "ideas": [
            {{
              "rank": 1,
              "topic": "one-line title",
              "reason": "one-line reason"
            }}
          ]
        }}

        Keep each idea useful for company PR, product campaigns, replies, experiments, or buyer feedback loops.
        Prefer practical builder language, specific user pain, and honest feedback asks.
        Do not make the idea feel generic, hypey, spammy, manipulative, or purely educational.
        """
    ).strip()


def build_batch_prompt(topic: str, count: int) -> str:
    return dedent(
        f"""
        Create {count} master PR/marketing drafts for this topic: {topic}
        These are channel-neutral master drafts for LinnuteeInnovations. They may later be adapted into Reddit, X/Bluesky,
        Indie Hackers, Hacker News, Dev.to, email updates, or direct reply variants.

        Return strict JSON with this shape:
        {{
          "posts": [
            {{
              "topic": "one-line topic title",
              "hook": "short attention-grabbing opening line",
              "script_lines": ["short paragraph or line", "short paragraph or line"],
              "caption": "short CTA or summary line",
              "hashtags": ["#tag1", "#tag2"],
              "platform_notes": "optional note or null",
              "retention_check": "one short sentence",
              "suggested_post_time": "morning"
            }}
          ]
        }}

        Requirements:
        - Follow this flow: pain, product/context, trust boundary, clear ask.
        - Keep the draft neutral enough to adapt across PR channels.
        - Hook must name a real builder problem or company/product update without generic hype.
        - Good hook patterns include: "I keep seeing builders lose time to X.", "We built this because X kept happening.", "The rough edge is X, and that is exactly what we are testing."
        - Each line must add product clarity, buyer relevance, trust, or feedback value.
        - Include at least one honest limitation, trust point, or current beta constraint when relevant.
        - Avoid textbook, academic, robotic, preachy, exaggerated, slang-heavy, or overly conclusive language.
        - Do not pretend the company has traction, endorsements, integrations, or guarantees not provided.
        - Caption should work as a compact CTA, status note, or tracking label.
        - Platform notes are required and must include 1 to 2 practical posting, response, or tracking directives.
        - Use only morning, afternoon, or evening for suggested_post_time.
        """
    ).strip()


def build_format_prompt(post_payload: dict[str, object], platform: str) -> str:
    return dedent(
        f"""
        Adapt this master PR/marketing draft for {platform}.
        Channel guidance: {FORMAT_GUIDANCE[platform]}

        Return strict JSON with this shape:
        {{
          "topic": "one-line topic title",
          "hook": "channel-optimized opening line",
          "script_lines": ["short paragraph or line", "short paragraph or line"],
          "caption": "channel-optimized CTA or summary line",
          "hashtags": ["#tag1", "#tag2"],
          "platform_notes": "one short implementation note or null",
          "retention_check": "one short sentence",
          "suggested_post_time": "afternoon"
        }}

        Preserve the core idea but make the wording channel-aware.
        Follow this flow: pain, product/context, trust boundary, clear ask.
        Hook must name a specific buyer problem, update, or objection.
        Include relevant Continuity Layer facts when the draft is about the active campaign.
        Include the right CTA for the channel: GitHub for inspection, checkout for early access, or feedback/setup form for conversations.
        Platform notes are required and must include practical posting, response, or tracking guidance.
        Avoid academic, preachy, robotic, slang-heavy, dramatic, defensive, spammy, or overly formal correction language.
        Use only morning, afternoon, or evening for suggested_post_time.
        Input:
        {post_payload}
        """
    ).strip()


def build_campaign_prompt(goal: str, product_payload: dict[str, object], days: int = 7) -> str:
    return dedent(
        f"""
        Create a {days}-day product marketing campaign for LinnuteeInnovations.
        Goal: {goal}
        Product profile:
        {product_payload}

        Return strict JSON with this shape:
        {{
          "product": "product name",
          "goal": "campaign goal",
          "summary": "plain one-paragraph campaign summary",
          "days": [
            {{
              "day": 1,
              "channel": "reddit",
              "angle": "specific posting angle",
              "cta": "specific call to action",
              "reply_focus": "what to listen for or answer",
              "objection_to_watch": "objection or doubt to track",
              "tracking_goal": "metric or signal to record"
            }}
          ],
          "notes": "short founder guidance"
        }}

        Requirements:
        - Use only supported channels: reddit, x_bluesky, indie_hackers, hacker_news, devto, email_update, direct_reply.
        - Make the plan usable for a founder with no large audience.
        - Keep the tone practical, honest, non-hypey, and review-first.
        - Include trust boundaries and limitations when they matter.
        - Do not imply anything will auto-post or happen without founder approval.
        """
    ).strip()


def build_posts_prompt(product_payload: dict[str, object], channel: str, count: int, goal: str | None = None) -> str:
    goal_text = goal or "Draft practical product marketing posts for the selected product."
    return dedent(
        f"""
        Draft {count} platform-native product marketing posts for {channel}.
        Goal: {goal_text}
        Channel guidance: {FORMAT_GUIDANCE[channel]}
        Product profile:
        {product_payload}

        Return strict JSON with this shape:
        {{
          "posts": [
            {{
              "topic": "one-line topic title",
              "hook": "channel-ready opening",
              "script_lines": ["short paragraph or line", "short paragraph or line"],
              "caption": "CTA, link note, or tracking label",
              "hashtags": ["#tag"],
              "platform_notes": "posting and response guidance",
              "retention_check": "one short sentence",
              "suggested_post_time": "afternoon"
            }}
          ]
        }}

        Requirements:
        - Make every draft specific to the product facts.
        - Adapt to the platform instead of sounding like generic AI marketing.
        - Keep public actions as drafts for founder review.
        - Use only morning, afternoon, or evening for suggested_post_time.
        """
    ).strip()


def build_reply_prompt(product_payload: dict[str, object], scenario: str, user_signal: str | None = None) -> str:
    signal = user_signal or "No exact user comment provided. Create a reusable reply template."
    return dedent(
        f"""
        Draft a natural public reply for LinnuteeInnovations.
        Reply scenario: {scenario}
        Scenario guidance: {REPLY_SCENARIO_GUIDANCE[scenario]}
        User signal or comment: {signal}
        Product profile:
        {product_payload}

        Return strict JSON with this shape:
        {{
          "product": "product name",
          "scenario": "{scenario}",
          "user_signal": "the objection, interest, or comment being answered",
          "reply": "the reply draft",
          "follow_up": "one useful follow-up question or next step",
          "tracking_note": "what to log if this comes up again"
        }}

        Requirements:
        - Sound like a practical founder, not a brand account.
        - Acknowledge fair concerns before explaining.
        - Do not pressure, dunk, exaggerate, or promise unsupported outcomes.
        - Keep it draft-first and human-approved.
        """
    ).strip()


def build_rewrite_prompt(post_payload: dict[str, object], *, safety_reasons: list[str] | None = None) -> str:
    reasons_text = "\n".join(f"- {reason}" for reason in (safety_reasons or [])) or "- Improve the draft while keeping Astra aligned."
    return dedent(
        f"""
        Rewrite this master draft only if it feels weak, generic, too academic, too preachy, too flat, too hypey, too defensive, or too long.
        Fix the following safety or alignment issues first:
        {reasons_text}
        Bring the draft back to Astra's LinnuteeInnovations PR marketer identity first.
        Tighten the hook around a real buyer problem, then add product clarity, trust boundaries, and a useful ask.
        Simplify the language.
        Calm down emotional, dramatic, alarmist, or aggressive phrasing.
        Reduce certainty on uncertain claims.
        Remove advocacy, pressure, manipulative framing, spam, and lecture energy.
        Make the wording natural, readable, and controlled rather than academic, robotic, poetic, or exaggerated.
        Remove dramatic, self-mythologizing, or fake traction lines.
        Make the caption useful as a CTA, tracking label, or short summary.
        Ensure platform_notes include 1 to 2 practical posting, response, or tracking directives.
        Remove ideological, edgy, rebellious, aggressive, fear-based, or dramatic language from platform_notes.

        Return strict JSON with the same schema as the input.
        Input:
        {post_payload}
        """
    ).strip()
