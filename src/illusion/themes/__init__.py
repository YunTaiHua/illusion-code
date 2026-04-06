"""Theme system exports."""

from illusion.themes.loader import list_themes, load_custom_themes, load_theme
from illusion.themes.schema import (
    BorderConfig,
    ColorsConfig,
    IconConfig,
    LayoutConfig,
    ThemeConfig,
)

__all__ = [
    "BorderConfig",
    "ColorsConfig",
    "IconConfig",
    "LayoutConfig",
    "ThemeConfig",
    "list_themes",
    "load_custom_themes",
    "load_theme",
]
