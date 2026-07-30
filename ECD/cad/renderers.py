"""
ECD/cad/renderers.py — Rendering engine for converting ezdxf Drawings to SVG, PNG, and PDF.
"""
import os
import sys
from pathlib import Path
from typing import Optional

def _get_cjk_font_face():
    """Find system CJK / Japanese font file and return an ezdxf FontFace object."""
    try:
        from ezdxf.fonts import font_manager
    except ImportError:
        return None

    candidates = []
    if sys.platform.startswith("win"):
        win_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
        candidates = [
            win_fonts / "msgothic.ttc",
            win_fonts / "msmincho.ttc",
            win_fonts / "meiryo.ttc",
            win_fonts / "yuanti.ttf",
            win_fonts / "arial.ttf",
        ]
    elif sys.platform == "darwin":
        candidates = [
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ]
    else: # Linux / POSIX
        candidates = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"),
        ]

    for path in candidates:
        if path.exists():
            try:
                return font_manager.get_ttf_font_face(Path(path))
            except Exception:
                pass
    return None

def render_doc_to_svg(doc) -> str:
    """Render an ezdxf Drawing object to an SVG string."""
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing.layout import Page

    msp = doc.modelspace()
    backend = SVGBackend()
    ctx = RenderContext(doc)
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    page = Page(width=0, height=0)
    return backend.get_string(page=page)

def render_doc_to_png(doc, png_path: str) -> None:
    """Render an ezdxf Drawing object to a high-resolution PNG image file."""
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams['font.sans-serif'] = ['MS Gothic', 'Yu Gothic', 'Meiryo', 'Noto Sans CJK JP', 'DejaVu Sans', 'sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False

    msp = doc.modelspace()
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    plt.close(fig)

def render_doc_to_pdf(doc, pdf_path: str) -> None:
    """Render an ezdxf Drawing object to a PDF file."""
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams['font.sans-serif'] = ['MS Gothic', 'Yu Gothic', 'Meiryo', 'Noto Sans CJK JP', 'DejaVu Sans', 'sans-serif']
    matplotlib.rcParams['axes.unicode_minus'] = False

    msp = doc.modelspace()
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)
    fig.savefig(pdf_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
