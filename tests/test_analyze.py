from astra.analyze import summarize_performance
from astra.models import PerformanceRecord


def test_summarize_performance_mentions_top_patterns() -> None:
    summary = summarize_performance(
        [
            PerformanceRecord(
                topic="AI leverage",
                hook="AI got scary when it got useful.",
                platform="tiktok",
                views=1200,
                retention=0.71,
            ),
            PerformanceRecord(
                topic="Silence panic",
                hook="Silence exposes the thoughts you're dodging.",
                platform="youtube_shorts",
                views=900,
                retention=0.55,
            ),
        ]
    )
    assert "Most-viewed topic was 'AI leverage'" in summary
    assert "Best retention came from hook 'AI got scary when it got useful.'" in summary
