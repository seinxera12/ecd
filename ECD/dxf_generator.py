"""
Shim module forwarding all dxf_generator functions to ECD.cad.dxf_generator.
"""
from ECD.cad.dxf_generator import *
from ECD.cad.renderers import render_doc_to_svg, render_doc_to_png, render_doc_to_pdf
from ECD.cad.layout_sections import get_group_graphics_and_text, get_per_symbol_graphics_and_text, render_entities_to_svg, get_group_entities