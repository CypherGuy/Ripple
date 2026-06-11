"""Shared display formatting helpers used across Ripple services."""


def format_cost(cost) -> str:
    """Normalise an estimated-cost value to a £-prefixed, comma-grouped string.

    Dynatrace bizEvents return the cost as a raw number string (e.g. "23000"),
    while webhook/demo payloads supply "£23,000". Format defensively wherever the
    value is rendered (MR body, dashboard incident panel) so it always reads
    "£23,000" regardless of the source.

    '23000' -> '£23,000'; 23000 -> '£23,000'; '£23,000' -> '£23,000';
    'unknown' -> 'unknown'; '' / None -> 'unknown'.
    """
    if cost is None:
        return "unknown"
    s = str(cost).strip()
    if not s:
        return "unknown"
    digits = s.replace("£", "").replace(",", "").strip()
    if digits.isdigit():
        return f"£{int(digits):,}"
    return s
