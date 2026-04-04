import re
from datetime import datetime
from urllib.parse import quote


def _channel_color_pair(channel_name: str) -> tuple[str, str]:
    """Deterministically map a channel name to one of the app's avatar gradient pairs."""
    normalized = channel_name or "Channel"
    hash_value = 0
    for char in normalized:
        hash_value = ord(char) + ((hash_value << 5) - hash_value)

    colors = [
        ("FF6B6B", "FFE66D"),
        ("4ECDC4", "44A08D"),
        ("95E1D3", "38A169"),
        ("FA8072", "FFB347"),
        ("87CEEB", "4169E1"),
        ("DDA0DD", "BA55D3"),
        ("20B2AA", "00CED1"),
        ("FF69B4", "FF1493"),
    ]

    return colors[abs(hash_value) % len(colors)]


def format_views(count: int) -> str:
    """Format view count: 1234567 → '1.2M views'"""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M views"
    elif count >= 1_000:
        return f"{count // 1_000}K views"
    else:
        return f"{count} views"


def format_timestamp(publish_time: str) -> str:
    """Format ISO timestamp: '2017-11-29T20:30:03.000Z' → '1 year ago'"""
    try:
        pub_date = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
        now = datetime.now(pub_date.tzinfo)
        delta = now - pub_date
        days = delta.days

        if days < 1:
            hours = delta.seconds // 3600
            return f"{hours} hours ago" if hours > 0 else "Just now"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            return f"{days // 7} weeks ago"
        elif days < 365:
            return f"{days // 30} months ago"
        else:
            return f"{days // 365} years ago"
    except Exception:
        return "Unknown"


def generate_channel_avatar(channel_name: str) -> str:
    """Generate avatar URL using ui-avatars.com with a deterministic brand-like color palette."""
    start_color, end_color = _channel_color_pair(channel_name)
    return (
        f"https://ui-avatars.com/api/?name={quote(channel_name)}"
        f"&background={start_color}&color=fff&size=36"
    )


def generate_channel_handle(channel_name: str) -> str:
    """Generate a stable YouTube-like @handle from channel name."""
    base = re.sub(r"[^a-zA-Z0-9]", "", (channel_name or "channel").lower())
    if not base:
        base = "channel"
    return f"@{base[:24]}"


def generate_channel_description(channel_name: str) -> str:
    """Generate a generic but varied channel description from name tokens."""
    name = (channel_name or "This channel").strip()
    lowered = name.lower()

    topic_map = {
        "gaming": "gameplay highlights, walkthroughs, and live moments",
        "music": "music drops, sessions, and behind-the-scenes updates",
        "tech": "tech reviews, guides, and product breakdowns",
        "news": "daily updates, explainers, and quick analysis",
        "film": "cinema deep-dives, scenes, and creator commentary",
        "travel": "travel stories, city guides, and practical tips",
        "learn": "learning-focused explainers and practical tutorials",
        "edu": "learning-focused explainers and practical tutorials",
        "food": "food stories, recipes, and taste tests",
        "sport": "sports updates, reactions, and match highlights",
    }

    topic = "fresh videos, creator updates, and community favorites"
    for keyword, mapped in topic_map.items():
        if keyword in lowered:
            topic = mapped
            break

    templates = [
        f"{name} brings {topic}. New uploads regularly.",
        f"Welcome to {name}: {topic}. Subscribe for weekly drops.",
        f"Official home of {name}. Expect {topic} and more.",
    ]

    hash_value = 0
    for char in name:
        hash_value = ord(char) + ((hash_value << 5) - hash_value)

    return templates[abs(hash_value) % len(templates)]


def is_verified(views: int, likes: int) -> bool:
    """Heuristic: consider verified if high engagement"""
    return views > 100_000 or likes > 5_000
