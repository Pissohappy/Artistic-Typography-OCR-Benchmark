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
        language: str = "en",
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
        language: str = "en",
    ) -> RenderResult:
        _ = seed, language  # SVG 渲染器不区分语言
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


class SynthTigerRenderer(Renderer):
    """真正的 SynthTiger 渲染器，通过 Python API 调用。"""

    route_name = "route_synthtiger_multiline"

    # 默认字体映射（可根据系统调整）
    DEFAULT_FONTS = {
        "en_sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "en_serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "en_display": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "zh_sans": "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    }

    def __init__(self, executor: CommandExecutor, config: RouteConfig, artistic: bool = False):
        super().__init__(executor, config)
        self.artistic = artistic

    def _get_font_path(self, font_class: str, language: str) -> str:
        key = f"{language}_{font_class}"
        return self.DEFAULT_FONTS.get(key, self.DEFAULT_FONTS["en_sans"])

    def _get_colors(self, style_family: str) -> tuple[tuple, tuple]:
        """返回 (背景色, 文本色)"""
        color_schemes = {
            "clean": ((255, 255, 255, 255), (21, 21, 21, 255)),
            "decorative": ((247, 242, 232, 255), (58, 34, 93, 255)),
            "poster": ((20, 20, 20, 255), (245, 230, 99, 255)),
            "graffiti": ((15, 26, 43, 255), (121, 240, 255, 255)),
        }
        return color_schemes.get(style_family, color_schemes["clean"])

    def _apply_artistic_effects(self, text_layer, style_family: str, seed: int):
        """应用艺术效果（边框、阴影、凸起等）"""
        if not self.artistic:
            return

        # 根据 style_family 添加不同效果
        if style_family == "poster":
            # 添加阴影效果
            text_layer.shadow = (2, 2, 4, (0, 0, 0, 128))
        elif style_family == "graffiti":
            # 添加边框效果
            text_layer.stroke = (2, (255, 255, 255, 200))

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
        language: str = "en",
    ) -> RenderResult:
        import random

        import numpy as np
        from PIL import Image

        from synthtiger import components, layers

        # 设置随机种子
        random.seed(seed)
        np.random.seed(seed)

        # 获取颜色配置
        bg_color, text_color = self._get_colors(style_family)

        # 创建文本层
        font_path = self._get_font_path(font_class, language)
        font_size = 32

        # 对于多行文本，按空格分割后创建多个文本层
        if layout_type == "multiline_block":
            words = text.split()
            text_layers = []
            for word in words:
                layer = layers.TextLayer(
                    text=word,
                    path=font_path,
                    size=font_size,
                    color=text_color,
                )
                text_layers.append(layer)

            # 创建图层组并应用流式布局
            group = layers.Group(text_layers)
            layout = components.FlowLayout(
                space=(4, 4),
                line_space=(8, 8),
                length=(self.config.canvas_width - 40, self.config.canvas_width - 40),
                align=("left", "left"),
            )
            layout.apply(group)

            # 合并图层组为单个图层
            text_layer = group.merge()
            text_layer.center = (self.config.canvas_width // 2, self.config.canvas_height // 2)
        else:
            # 单行文本
            text_layer = layers.TextLayer(
                text=text,
                path=font_path,
                size=font_size,
                color=text_color,
            )
            text_layer.center = (self.config.canvas_width // 2, self.config.canvas_height // 2)

        # 创建背景层
        bg_layer = layers.RectLayer(
            color=bg_color,
            size=(self.config.canvas_width, self.config.canvas_height)
        )

        # 应用艺术效果
        self._apply_artistic_effects(text_layer, style_family, seed)

        # 合成
        bg_layer.paste(text_layer)

        # 输出图像
        img_array = bg_layer.output()
        img = Image.fromarray(img_array.astype(np.uint8))

        # 应用后处理（模糊等）
        if degradation_profile in ("blur_low", "noise_medium"):
            from PIL import ImageFilter
            if degradation_profile == "blur_low":
                img = img.filter(ImageFilter.GaussianBlur(radius=1))

        # 保存
        relpath = f"images/{filename_stem}.png"
        img_path = out_dir / relpath
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(img_path)

        return RenderResult(
            image_relpath=relpath,
            width=img.width,
            height=img.height,
            format="png",
            background_type=self.config.background_type,
            engine_primary="synthtiger",
            engine_secondary="python-api",
            template_id="tpl_synthtiger_v1",
            font_id=f"{font_class}_synthtiger",
            layout_meta={"layout_type": layout_type},
            style_meta={"style_family": style_family, "language": language},
            degradation_meta={"profile": degradation_profile},
        )


class TrdgRenderer(Renderer):
    """真正的 TRDG 渲染器，通过 Python API 调用。"""

    route_name = "route_trdg_basic"

    # 语言映射表
    LANGUAGE_MAP = {
        "en": "en",
        "zh": "cn",
        "zh-cn": "cn",
        "zh-tw": "cn",
        "ja": "ja",
        "ko": "ko",
        "th": "th",
    }

    def _map_language(self, language: str) -> str:
        return self.LANGUAGE_MAP.get(language.lower(), "en")

    def _map_background(self, style_family: str) -> int:
        # TRDG: 0=高斯噪声, 1=白色, 2=准晶体, 3=图片
        mapping = {"clean": 1, "decorative": 0, "poster": 2, "graffiti": 0}
        return mapping.get(style_family, 1)

    def _get_blur_config(self, degradation_profile: str) -> tuple[int, bool]:
        # 根据降质配置返回模糊参数
        if degradation_profile == "clean":
            return 0, False
        if degradation_profile == "mild":
            return 2, True
        if degradation_profile == "heavy":
            return 4, True
        return 1, True

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
        language: str = "en",
    ) -> RenderResult:
        import random

        from trdg.generators import GeneratorFromStrings

        # TRDG 不支持 seed 参数，需要在外部设置随机种子
        random.seed(seed)

        blur, random_blur = self._get_blur_config(degradation_profile)

        generator = GeneratorFromStrings(
            strings=[text],
            size=self.config.canvas_height,
            blur=blur,
            random_blur=random_blur,
            background_type=self._map_background(style_family),
            language=self._map_language(language),
        )

        img, lbl = next(generator)
        _ = lbl  # label 不使用

        relpath = f"images/{filename_stem}.jpg"
        img_path = out_dir / relpath
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(img_path, quality=95)

        return RenderResult(
            image_relpath=relpath,
            width=img.width,
            height=img.height,
            format="jpg",
            background_type=self.config.background_type,
            engine_primary="trdg",
            engine_secondary="python-api",
            template_id="tpl_trdg_v1",
            font_id=f"{font_class}_trdg",
            layout_meta={"layout_type": layout_type},
            style_meta={"style_family": style_family, "language": language},
            degradation_meta={"profile": degradation_profile},
        )


def build_renderer(route_name: str, executor: CommandExecutor) -> Renderer:
    if route_name == "route_trdg_basic":
        try:
            import trdg
            _ = trdg  # 确认导入成功
        except ImportError:
            raise ImportError("TRDG 未安装。请运行: pip install trdg")
        return TrdgRenderer(
            executor,
            RouteConfig(route_name=route_name, canvas_width=320, canvas_height=96, background_type="generated", font_family="auto"),
        )
    if route_name == "route_synthtiger_multiline":
        try:
            import synthtiger
            _ = synthtiger
        except ImportError:
            raise ImportError("SynthTiger 未安装。请运行: pip install synthtiger")
        return SynthTigerRenderer(
            executor,
            RouteConfig(route_name=route_name, canvas_width=768, canvas_height=220, background_type="generated", font_family="auto"),
            artistic=False
        )
    if route_name == "route_synthtiger_svg_im":
        try:
            import synthtiger
            _ = synthtiger
        except ImportError:
            raise ImportError("SynthTiger 未安装。请运行: pip install synthtiger")
        return SynthTigerRenderer(
            executor,
            RouteConfig(route_name=route_name, canvas_width=1024, canvas_height=280, background_type="generated", font_family="auto"),
            artistic=True  # 启用艺术效果
        )
    raise ValueError(f"Unknown route: {route_name}")
