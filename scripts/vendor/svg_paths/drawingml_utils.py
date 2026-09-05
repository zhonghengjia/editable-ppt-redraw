"""Local unit adapter; the rest of the upstream utility module is not required."""


def px_to_emu(value: float) -> int:
    """Convert CSS pixels at 96 dpi into Office EMUs."""
    return round(value * 9525)
