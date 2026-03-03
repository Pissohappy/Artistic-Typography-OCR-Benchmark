from __future__ import annotations

import subprocess
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


@dataclass
class RouteConfig:
    route_name: str
    canvas_width: int
    canvas_height: int
    background_type: str
    font_family: str


class CommandExecutor:
    def has_binary(self, name: str) -> bool:
        from shutil import which

        return which(name) is not None

    def run(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


class Renderer:
    route_name: str = "base"

    def __init__(self, executor: CommandExecutor, config: RouteConfig):
        self.executor = executor
        self.config = config

    def render(
        self,
        *,
        text: str,
        out_dir: Path,
        filename_stem: str,
        seed: int,
        layout_type: str,
        style_family: str,
        font_class: str,
        degradation_profile: str,
    ) -> RenderResult:
        raise NotImplementedError


class SvgTextRenderer(Renderer):
    """Real renderer that writes styled SVG text files."""

    route_name = "svg_text"

    def _build_lines(self, text: str, layout_type: str) -> list[str]:
        if layout_type == "single_line":
            return [text]
        words = text.split()
        if not words:
            return [text]
        max_words = 4 if layout_type == "multiline_block" else 3
        lines: list[str] = []
        buf: list[str] = []
        for w in words:
            buf.append(w)
            if len(buf) >= max_words:
                lines.append(" ".join(buf))
                buf = []
        if buf:
            lines.append(" ".join(buf))
        return lines or [text]

    def _style_for_family(self, style_family: str) -> tuple[str, str]:
        if style_family == "decorative":
            return "#f7f2e8", "#3a225d"
        if style_family == "poster":
            return "#141414", "#f5e663"
        if style_family == "graffiti":
            return "#0f1a2b", "#79f0ff"
        return "#ffffff", "#151515"

    def _svg_content(self, text: str, layout_type: str, style_family: str, width: int, height: int) -> str:
        bg, fg = self._style_for_family(style_family)
        lines = self._build_lines(text, layout_type)
        line_h = max(24, int(height / (len(lines) + 1)))
        y = line_h
        text_nodes: list[str] = []
        for line in lines:
            escaped = (
                line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            text_nodes.append(
                f"<text x=\"24\" y=\"{y}\" fill=\"{fg}\" font-family=\"{self.config.font_family}\" font-size=\"30\">{escaped}</text>"
            )
            y += line_h
        return (
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">"
            f"<rect width=\"100%\" height=\"100%\" fill=\"{bg}\" />"
            + "".join(text_nodes)
            + "</svg>"
        )

    def render(
        self,
        *,
        text: str,
        out_dir: Path,
        filename_stem: str,
        seed: int,
        layout_type: str,
        style_family: str,
        font_class: str,
        degradation_profile: str,
    ) -> RenderResult:
        _ = seed
        width = max(self.config.canvas_width, min(2200, len(text) * 16 + 120))
        height = self.config.canvas_height
        if layout_type == "single_line":
            height = 96
        elif layout_type == "svg_artistic":
            height = 280

        relpath = f"images/{filename_stem}.svg"
        image_path = out_dir / relpath
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_text(
            self._svg_content(text, layout_type, style_family, width, height),
            encoding="utf-8",
        )

        return RenderResult(
            image_relpath=relpath,
            width=width,
            height=height,
            format="svg",
            background_type=self.config.background_type,
            engine_primary=self.config.route_name,
            engine_secondary="svg-native",
            template_id="tpl_text_svg_v1",
            font_id=f"{font_class}_system",
            layout_meta={"layout_type": layout_type, "line_mode": "wrapped" if layout_type != "single_line" else "single"},
            style_meta={"style_family": style_family},
            degradation_meta={"profile": degradation_profile, "applied": "none"},
        )


class SvgImRenderer(SvgTextRenderer):
    """SVG route with optional bitmap post-process via ImageMagick/Inkscape."""

    route_name = "route_synthtiger_svg_im"

    def render(self, **kwargs) -> RenderResult:
        base = super().render(**kwargs)
        src_svg = kwargs["out_dir"] / base.image_relpath
        stem = Path(base.image_relpath).stem
        png_rel = f"images/{stem}.png"
        png_path = kwargs["out_dir"] / png_rel

        if self.executor.has_binary("inkscape"):
            self.executor.run(["inkscape", str(src_svg), "--export-type=png", f"--export-filename={png_path}"])
            base.image_relpath = png_rel
            base.format = "png"
            base.engine_secondary = "inkscape"
            base.degradation_meta = {"profile": kwargs["degradation_profile"], "applied": "inkscape_png"}
        elif self.executor.has_binary("magick"):
            self.executor.run(["magick", str(src_svg), "-quality", "92", str(png_path)])
            base.image_relpath = png_rel
            base.format = "png"
            base.engine_secondary = "imagemagick"
            base.degradation_meta = {"profile": kwargs["degradation_profile"], "applied": "imagemagick_png"}
        else:
            base.degradation_meta = {
                "profile": kwargs["degradation_profile"],
                "applied": "svg_only_no_external_converter",
            }
        return base


def build_renderer(route_name: str, executor: CommandExecutor) -> Renderer:
    if route_name == "route_trdg_basic":
        return SvgTextRenderer(
            executor,
            RouteConfig(route_name=route_name, canvas_width=320, canvas_height=96, background_type="solid", font_family="Arial"),
        )
    if route_name == "route_synthtiger_multiline":
        return SvgTextRenderer(
            executor,
            RouteConfig(route_name=route_name, canvas_width=768, canvas_height=220, background_type="textured_flat", font_family="Verdana"),
        )
    if route_name == "route_synthtiger_svg_im":
        return SvgImRenderer(
            executor,
            RouteConfig(route_name=route_name, canvas_width=1024, canvas_height=280, background_type="artistic", font_family="Impact"),
        )
    raise ValueError(f"Unknown route: {route_name}")
