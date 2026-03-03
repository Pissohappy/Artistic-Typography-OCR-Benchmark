from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RenderResult:
    image_relpath: str
    width: int
    height: int
    format: str
    background_type: str
    engine_primary: str
    engine_secondary: str
    template_id: str | None
    font_id: str | None
    layout_meta: dict
    style_meta: dict
    degradation_meta: dict


class CommandExecutor:
    def has_binary(self, name: str) -> bool:
        return shutil.which(name) is not None


class Renderer:
    route_name: str = "base"

    def __init__(self, executor: CommandExecutor):
        self.executor = executor

    def render(self, *, text: str, out_dir: Path, filename_stem: str, seed: int, layout_type: str, style_family: str, font_class: str, degradation_profile: str) -> RenderResult:
        raise NotImplementedError


def _write_ppm_placeholder(path: Path, width: int, height: int, seed: int) -> None:
    random.seed(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as f:
        f.write(f"P3\n{width} {height}\n255\n")
        for _y in range(height):
            row = []
            for _x in range(width):
                r = random.randint(180, 255)
                g = random.randint(180, 255)
                b = random.randint(180, 255)
                row.append(f"{r} {g} {b}")
            f.write(" ".join(row) + "\n")


class StubRenderer(Renderer):
    route_name = "stub"

    def __init__(self, executor: CommandExecutor, engine_primary: str, engine_secondary: str | None = None):
        super().__init__(executor)
        self._engine_primary = engine_primary
        self._engine_secondary = engine_secondary or "mock"

    def render(self, *, text: str, out_dir: Path, filename_stem: str, seed: int, layout_type: str, style_family: str, font_class: str, degradation_profile: str) -> RenderResult:
        width = max(128, min(1200, len(text) * 18 + 40))
        height = 64 if layout_type == "single_line" else 180
        if layout_type == "svg_artistic":
            height = 220
        relpath = f"images/{filename_stem}.ppm"
        img_path = out_dir / relpath
        _write_ppm_placeholder(img_path, width, height, seed)
        return RenderResult(
            image_relpath=relpath,
            width=width,
            height=height,
            format="ppm",
            background_type="solid_mock",
            engine_primary=self._engine_primary,
            engine_secondary=self._engine_secondary,
            template_id="tpl_mock_001",
            font_id=f"font_{font_class}_mock",
            layout_meta={"line_count": 1 if layout_type == "single_line" else 3},
            style_meta={"style_family": style_family},
            degradation_meta={"profile": degradation_profile},
        )


def build_renderer(route_name: str, executor: CommandExecutor) -> Renderer:
    if route_name == "route_trdg_basic":
        return StubRenderer(executor, "trdg", "mock")
    if route_name == "route_synthtiger_multiline":
        return StubRenderer(executor, "synthtiger", "mock")
    if route_name == "route_synthtiger_svg_im":
        return StubRenderer(executor, "synthtiger_svg", "imagemagick_mock")
    raise ValueError(f"Unknown route: {route_name}")
