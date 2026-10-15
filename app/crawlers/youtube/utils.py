import re

# Abbreviation suffixes YouTube uses for counts: English (hl=en) and Vietnamese
# (hl=vi, this crawler's default: "N" nghìn, "Tr" triệu, "T" tỷ).
_COUNT_UNITS = {
    "k": 1_000,
    "n": 1_000,
    "m": 1_000_000,
    "tr": 1_000_000,
    "b": 1_000_000_000,
    "t": 1_000_000_000,
    "tỷ": 1_000_000_000,
}
_COUNT_RE = re.compile(r"(\d[\d.,]*)\s*([^\d\s.,]*)")


def parse_count(text) -> int | None:
    """Parse a YouTube count ("1.234.567 lượt xem", "1,2 Tr lượt xem", "12K views",
    "3 video", 1234) into an int. Returns None when there's no number in it."""
    if text is None:
        return None
    if isinstance(text, int):
        return text
    match = _COUNT_RE.search(str(text).replace("\xa0", " "))
    if not match:
        return None
    number, unit = match.group(1), match.group(2).lower()
    multiplier = _COUNT_UNITS.get(unit)
    if multiplier is None:
        # Plain count: "." and "," are thousands separators ("1.234.567", "1,234,567").
        digits = re.sub(r"[.,]", "", number)
        return int(digits) if digits else None
    # Abbreviated count: the single separator is a decimal point ("1,2 Tr", "1.2M").
    try:
        return int(float(number.replace(",", ".")) * multiplier)
    except ValueError:
        return None


def parse_duration_seconds(text) -> int | None:
    """Parse "1:02:03" / "3:21" (or a seconds count like "201") into seconds."""
    if text is None or text == "":
        return None
    if isinstance(text, int):
        return text
    parts = str(text).strip().split(":")
    if not all(p.isdigit() for p in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def format_duration(seconds: int | None) -> str:
    """Seconds as YouTube's display format: "3:21", "1:02:03"."""
    if seconds is None:
        return ""
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
