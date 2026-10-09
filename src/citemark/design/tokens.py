"""Design tokens (UI kit 3): `design/tokens.json` is the source, and `static/tokens.css` is
written from it by `citemark design build`.

The file was seeded on 2026-10-09 from the design-system artifact's `tokens.json`, byte for byte.
From then on the kit's copy is the truth (UI kit Q2).

- **Colors** have a light and a dark value, or point at another token, as `"{ink}"`. A reference
  is resolved for each theme, so an element in the other theme gets that theme's value.
- **Contrast:** the 25 text and control pairs the artifact checked, held to WCAG AA in both
  themes: 4.5:1 for text, 3:1 for borders and the focus ring.
- **Themes in CSS:** light unless the visitor prefers dark or an element says
  `data-theme="dark"`. Dark applies only on screen, so a page always prints in light, as
  reports get printed and forwarded (design system Q6).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KIT = Path(__file__).resolve().parents[3]
SOURCE = KIT / "design" / "tokens.json"
CSS = KIT / "static" / "tokens.css"
THEMES = ("light", "dark")
REFERENCE = re.compile(r"^\{([\w-]+)\}$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

TEXT, NON_TEXT = 4.5, 3.0  # WCAG 2.2 AA: 1.4.3 for text, 1.4.11 for controls and focus
PAIRS: list[tuple[str, str, float]] = [  # foreground, background, minimum: the artifact's 25
    *[(fg, bg, TEXT) for fg in ("text", "text-muted") for bg in ("ground", "surface", "surface-sunken")],
    ("ink", "ground", TEXT),
    ("ink", "surface", TEXT),
    ("ink", "ink-soft", TEXT),
    ("on-ink", "ink", TEXT),
    *[(state, bg, TEXT) for state in ("pass", "fail", "warn", "declined") for bg in ("surface", f"{state}-soft")],
    ("line-strong", "surface", NON_TEXT),
    ("line-strong", "ground", NON_TEXT),
    ("focus-ring", "surface", NON_TEXT),
    ("focus-ring", "ground", NON_TEXT),
    ("ink", "line", NON_TEXT),
    ("widget-accent", "surface", TEXT),
    ("on-widget-accent", "widget-accent", TEXT),
]
DURATIONS_REDUCED = "0ms"  # under prefers-reduced-motion, nothing moves
SURFACE = "{indent}color: var(--text);\n{indent}background-color: var(--ground);\n"


class TokenError(Exception):
    """The token file can't be read as tokens. The message is one plain sentence."""


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or SOURCE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TokenError(f"{path} can't be read as tokens: {exc}") from exc


def colors(tokens: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Every color token's value in each theme, with references resolved."""
    raw = {token["name"]: token["value"] for token in tokens["color"]["tokens"]}

    def value(name: str, theme: str, seen: tuple[str, ...] = ()) -> str:
        if name not in raw:
            raise TokenError(f"{seen[-1] if seen else 'A token'} points at {name}, which isn't a color token.")
        if name in seen:
            raise TokenError(f"The color tokens {' → '.join((*seen, name))} point at each other in a loop.")
        given = raw[name][theme] if isinstance(raw[name], dict) else raw[name]
        if match := REFERENCE.match(given):
            return value(match.group(1), theme, (*seen, name))
        if not HEX.match(given):
            raise TokenError(f"{name} in the {theme} theme is {given}, not a #rrggbb color.")
        return given.lower()

    return {name: {theme: value(name, theme) for theme in THEMES} for name in raw}


def luminance(color: str) -> float:
    """Relative luminance, as WCAG 2 defines it."""

    def channel(byte: int) -> float:
        c = byte / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@dataclass(frozen=True)
class Pair:
    theme: str
    foreground: str
    background: str
    ratio: float
    minimum: float

    @property
    def passes(self) -> bool:
        return self.ratio >= self.minimum


def pairs(tokens: dict[str, Any]) -> list[Pair]:
    """The 25 checked pairs in both themes, each with its contrast ratio."""
    resolved = colors(tokens)
    return [
        Pair(theme, fg, bg, contrast(resolved[fg][theme], resolved[bg][theme]), minimum)
        for theme in THEMES
        for fg, bg, minimum in PAIRS
    ]


# --- The CSS ---


def _declarations(values: dict[str, str], indent: str) -> str:
    return "".join(f"{indent}--{name}: {value};\n" for name, value in values.items())


def _themed(tokens: dict[str, Any], theme: str) -> dict[str, str]:
    """The tokens that change with the theme: colors and the raised shadow."""
    values = {name: by_theme[theme] for name, by_theme in colors(tokens).items()}
    for token in tokens["shadow"]["tokens"]:
        values[token["name"]] = token["value"][theme] if isinstance(token["value"], dict) else token["value"]
    return values


def _fixed(tokens: dict[str, Any]) -> dict[str, str]:
    """The tokens that don't: fonts, the type styles, space, radius, layers, motion and sizes."""
    values = {f"font-{name}": family for name, family in tokens["type"]["families"].items()}
    for group in tokens["type"]["groups"]:
        for style in group["styles"]:
            prefix = f"type-{style['name']}"
            values[f"{prefix}-family"] = f"var(--font-{group['family']})"
            values[f"{prefix}-size"] = style["fontSize"]
            values[f"{prefix}-line"] = style["lineHeight"]
            values[f"{prefix}-weight"] = str(style["fontWeight"])
            if "letterSpacing" in style:
                values[f"{prefix}-tracking"] = style["letterSpacing"]
    for group in ("spacing", "radius", "zIndex", "duration", "size"):
        values |= {token["name"]: token["value"] for token in tokens[group]["tokens"]}
    return values


def _role(style: dict[str, Any]) -> str:
    """A type role's class, such as `.cm-type-label`, made of its style's variables."""
    name = style["name"]
    declarations = [
        f"font-family: var(--type-{name}-family)",
        f"font-size: var(--type-{name}-size)",
        f"line-height: var(--type-{name}-line)",
        f"font-weight: var(--type-{name}-weight)",
    ]
    if "letterSpacing" in style:
        declarations.append(f"letter-spacing: var(--type-{name}-tracking)")
    return f".cm-type-{name} {{ {'; '.join(declarations)}; }}\n"


def css(tokens: dict[str, Any]) -> str:
    light, dark = _themed(tokens, "light"), _themed(tokens, "dark")
    durations = {token["name"]: DURATIONS_REDUCED for token in tokens["duration"]["tokens"]}
    roles = "".join(_role(style) for group in tokens["type"]["groups"] for style in group["styles"])
    return (
        "/* Written by `citemark design build` from design/tokens.json. Edit that file, not this one. */\n\n"
        ":root {\n  color-scheme: light;\n" + _declarations(light, "  ") + _declarations(_fixed(tokens), "  ") + "}\n\n"
        "/* Dark only on screen, so every page prints in light (design system Q6). */\n"
        "@media screen and (prefers-color-scheme: dark) {\n"
        '  :root:not([data-theme="light"]) {\n    color-scheme: dark;\n' + _declarations(dark, "    ") + "  }\n}\n\n"
        "/* A theme set on an element brings its own text and ground, not only its variables. */\n"
        "@media screen {\n"
        '  [data-theme="dark"] {\n    color-scheme: dark;\n'
        + _declarations(dark, "    ")
        + f"{SURFACE.format(indent='    ')}  }}\n}}\n\n"
        '[data-theme="light"] {\n  color-scheme: light;\n'
        + _declarations(light, "  ")
        + f"{SURFACE.format(indent='  ')}}}\n\n"
        "@media (prefers-reduced-motion: reduce) {\n  :root {\n" + _declarations(durations, "    ") + "  }\n}\n\n"
        "/* Type roles */\n" + roles
    )


def build(source: Path | None = None, target: Path | None = None) -> bool:
    """Write the CSS. Returns whether it changed."""
    target = target or CSS
    written = css(load(source))
    if target.is_file() and target.read_text(encoding="utf-8") == written:
        return False
    target.write_text(written, encoding="utf-8")
    return True


def stale(source: Path | None = None, target: Path | None = None) -> bool:
    """Whether the committed CSS no longer matches the tokens."""
    target = target or CSS
    return not target.is_file() or target.read_text(encoding="utf-8") != css(load(source))
