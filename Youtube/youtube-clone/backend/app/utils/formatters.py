from datetime import datetime
from urllib.parse import quote


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
    """Generate avatar URL using ui-avatars.com"""
    return f"https://ui-avatars.com/api/?name={quote(channel_name)}&background=8B5CF6&color=fff&size=36"


def is_verified(views: int, likes: int) -> bool:
    """Heuristic: consider verified if high engagement"""
    return views > 100_000 or likes > 5_000
