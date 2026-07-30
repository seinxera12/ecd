"""
ECD/cad/layout_sections.py — Section extraction and layout group helpers.
"""
import ezdxf
from ezdxf.addons.drawing.svg import SVGBackend, SVGRenderBackend

class TransparentSVGRenderBackend(SVGRenderBackend):
    def __init__(self, page, settings):
        super().__init__(page, settings)
        self.background.set("fill", "none")
        self.background.set("fill-opacity", "0")

    def set_background(self, color):
        pass

class TransparentSVGBackend(SVGBackend):
    def make_backend(self, page, settings):
        return TransparentSVGRenderBackend(page, settings)

def render_entities_to_svg(doc, entities: list) -> str:
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.layout import Page
    from ezdxf.bbox import extents
    from ezdxf.math import BoundingBox2d
    try:
        from ECD.cad.renderers import _get_cjk_font_face
    except ImportError:
        from renderers import _get_cjk_font_face

    if not entities:
        return ""
    backend = TransparentSVGBackend()
    ctx = RenderContext(doc)
    cjk_face = _get_cjk_font_face()
    if cjk_face:
        for key in list(ctx.fonts.keys()):
            ctx.fonts[key] = cjk_face
    frontend = Frontend(ctx, backend)
    frontend.draw_entities(entities)

    try:
        bb = extents(entities)
        x_min, y_min = bb.extmin.x, bb.extmin.y
        x_max, y_max = bb.extmax.x, bb.extmax.y
        width = x_max - x_min
        height = y_max - y_min
        if width > 0 and height > 0:
            page = Page(width=width, height=height)
            bbox2d = BoundingBox2d([(x_min, y_min), (x_max, y_max)])
            return backend.get_string(page=page, render_box=bbox2d)
    except Exception as e:
        print("Failed to render with custom page box:", e)

    page = Page(width=0, height=0)
    return backend.get_string(page=page)

def get_group_entities(doc, group_name: str) -> list:
    """Classify modelspace entities into five groups: title_block, legend, load_schedule, generation_notes, main_diagram."""
    msp = doc.modelspace()
    entities = []
    for entity in msp:
        layer = entity.dxf.layer
        if layer == "PAGE_MARGIN":
            continue

        if layer == "TITLE":
            ent_group = "title_block"
        elif layer == "LEGEND":
            ent_group = "legend"
        elif layer == "LOAD_SCHEDULE":
            ent_group = "load_schedule"
        elif layer == "NOTES":
            ent_group = "generation_notes"
        else:
            ent_group = "main_diagram"

        if ent_group == group_name:
            entities.append(entity)

    return entities

def get_group_graphics_and_text(doc, group_name: str) -> tuple:
    entities = get_group_entities(doc, group_name)
    graphics = []
    text_entities = []
    for ent in entities:
        if ent.dxftype() in ("TEXT", "MTEXT"):
            text_entities.append(ent)
        else:
            graphics.append(ent)
    return graphics, text_entities

def get_per_symbol_graphics_and_text(doc) -> tuple:
    """
    Extract main_diagram entities into per-symbol maps (by component_id)
    and return (symbol_map, (static_graphics, static_texts)).
    """
    main_ents = get_group_entities(doc, "main_diagram")
    symbol_map = {}
    static_graphics = []
    static_texts = []

    for ent in main_ents:
        cid = getattr(ent, "component_id", None)
        if cid:
            if cid not in symbol_map:
                symbol_map[cid] = ([], [])
            if ent.dxftype() in ("TEXT", "MTEXT"):
                symbol_map[cid][1].append(ent)
            else:
                symbol_map[cid][0].append(ent)
        else:
            if ent.dxftype() in ("TEXT", "MTEXT"):
                static_texts.append(ent)
            else:
                static_graphics.append(ent)

    return symbol_map, (static_graphics, static_texts)
