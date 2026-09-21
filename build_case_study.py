#!/usr/bin/env python3
"""
Build a Reacher-branded customer case study PDF from a content JSON file.

Usage:
    python build_case_study.py content.json output.pdf

The JSON schema is documented in references/content-schema.md. Every number in the
PDF comes from the JSON; this script never computes or invents figures except the
month-over-month jump it highlights on the trend charts.
"""
import json
import os
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, KeepTogether, PageBreak, NextPageTemplate, Flowable, CondPageBreak,
)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "..", "assets", "fonts")

# ---------------------------------------------------------------- brand tokens
BRAND = colors.HexColor("#3559E9")
BRAND_DARK = colors.HexColor("#1E3AB8")
BRAND_TINT = colors.HexColor("#EEF2FE")
BRAND_SOFT = colors.HexColor("#A9BBF7")
INK = colors.HexColor("#101828")
TEXT = colors.HexColor("#344054")
MUTED = colors.HexColor("#475467")
FAINT = colors.HexColor("#667085")
BORDER = colors.HexColor("#E4E7EC")
BORDER_STRONG = colors.HexColor("#D0D5DD")
POS = colors.HexColor("#067647")
POS_TINT = colors.HexColor("#ECFDF3")
WHITE = colors.white
NAVY = colors.HexColor("#0B1533")

PAGE_W, PAGE_H = letter
MARGIN = 0.7 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------- fonts
def register_fonts():
    faces = {
        "Pop": "Poppins-Regular.ttf",
        "Pop-Light": "Poppins-Light.ttf",
        "Pop-Medium": "Poppins-Medium.ttf",
        "Pop-Bold": "Poppins-Bold.ttf",
        "Pop-Italic": "Poppins-Italic.ttf",
    }
    ok = True
    for name, f in faces.items():
        p = os.path.join(FONT_DIR, f)
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont(name, p))
            font_manager.fontManager.addfont(p)
        else:
            ok = False
    if not ok:  # fall back to built-ins so the build never fails on fonts
        return {"reg": "Helvetica", "light": "Helvetica", "med": "Helvetica-Bold",
                "bold": "Helvetica-Bold", "ital": "Helvetica-Oblique", "mpl": "DejaVu Sans"}
    return {"reg": "Pop", "light": "Pop-Light", "med": "Pop-Medium",
            "bold": "Pop-Bold", "ital": "Pop-Italic", "mpl": "Poppins"}

F = register_fonts()

def S(name, **kw):
    base = dict(fontName=F["reg"], fontSize=10, leading=15, textColor=TEXT)
    base.update(kw)
    return ParagraphStyle(name, **base)

ST = {
    "eyebrow": S("eyebrow", fontName=F["bold"], fontSize=8, leading=10, textColor=BRAND,
                 spaceAfter=4),
    "h2": S("h2", fontName=F["bold"], fontSize=20, leading=25, textColor=INK, spaceAfter=8),
    "h3": S("h3", fontName=F["bold"], fontSize=11.5, leading=15, textColor=INK, spaceAfter=3),
    "body": S("body", fontSize=10, leading=15.5, textColor=TEXT, spaceAfter=6),
    "small": S("small", fontSize=8.5, leading=12, textColor=MUTED),
    "tiny": S("tiny", fontSize=7.5, leading=10, textColor=FAINT),
    "quote": S("quote", fontName=F["ital"], fontSize=11.5, leading=17.5, textColor=INK),
    "kpi_val": S("kpi_val", fontName=F["bold"], fontSize=21, leading=24, textColor=BRAND),
    "kpi_lab": S("kpi_lab", fontName=F["med"], fontSize=8.8, leading=11.5, textColor=INK),
    "kpi_sub": S("kpi_sub", fontSize=7.6, leading=10, textColor=FAINT),
    "cell": S("cell", fontSize=8.6, leading=11, textColor=TEXT),
    "cell_b": S("cell_b", fontName=F["med"], fontSize=8.6, leading=11, textColor=INK),
    "cell_h": S("cell_h", fontName=F["bold"], fontSize=7.6, leading=10, textColor=MUTED),
}

def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def md(t):
    """Very small markup: **bold** -> <b>. Everything else escaped."""
    t = esc(t)
    parts = t.split("**")
    out = ""
    for i, p in enumerate(parts):
        out += (f"<font name='{F['bold']}'>{p}</font>" if i % 2 else p)
    return out

# ---------------------------------------------------------------- images
def fit_crop(path, target_w, target_h, tmpdir, name):
    """Center-crop an image to the target aspect ratio and save a PNG."""
    im = Image.open(path)
    im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
    e = 2  # screenshots often carry a 1-2px border
    if im.size[0] > 40 and im.size[1] > 40:
        im = im.crop((e, e, im.size[0] - e, im.size[1] - e))
    tw, th = target_w, target_h
    r_t = tw / th
    w, h = im.size
    if w / h > r_t:
        nw = int(h * r_t); x0 = (w - nw) // 2
        im = im.crop((x0, 0, x0 + nw, h))
    else:
        nh = int(w / r_t); y0 = (h - nh) // 2
        im = im.crop((0, y0, w, y0 + nh))
    scale = min(1.0, 1600 / im.size[0])
    if scale < 1:
        im = im.resize((int(im.size[0] * scale), int(im.size[1] * scale)), Image.LANCZOS)
    elif im.size[0] < 900:  # upsample small screenshots so they print smoothly
        k = 900 / im.size[0]
        im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), Image.LANCZOS)
    out = os.path.join(tmpdir, name + ".png")
    im.save(out)
    return out

def fit_contain(path, box_w, box_h, tmpdir, name):
    """Return (png_path, draw_w, draw_h) scaled to fit inside the box."""
    im = Image.open(path).convert("RGBA")
    bbox = im.getbbox()  # trim transparent padding on logos
    if bbox:
        im = im.crop(bbox)
    # trim near-white padding too (logos pasted on white)
    from PIL import ImageChops
    rgb = Image.new("RGB", im.size, (255, 255, 255))
    rgb.paste(im, mask=im.split()[3])
    diff = ImageChops.difference(rgb, Image.new("RGB", im.size, (255, 255, 255)))
    diff = diff.convert("L").point(lambda x: 255 if x > 18 else 0)
    b2 = diff.getbbox()
    if b2:
        pad = 3
        im = im.crop((max(0, b2[0] - pad), max(0, b2[1] - pad),
                      min(im.size[0], b2[2] + pad), min(im.size[1], b2[3] + pad)))
    if im.size[0] < 600:
        k = 600 / im.size[0]
        im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), Image.LANCZOS)
    w, h = im.size
    s = min(box_w / w, box_h / h)
    out = os.path.join(tmpdir, name + ".png")
    im.save(out)
    return out, w * s, h * s

def rounded_image(c, img_path, x, y, w, h, r):
    c.saveState()
    p = c.beginPath()
    p.roundRect(x, y, w, h, r)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(img_path, x, y, w, h, mask="auto")
    c.restoreState()

# ---------------------------------------------------------------- wordmark
def reacher_wordmark(c, x, y, size, color=WHITE, mark=BRAND):
    """Neutral Reacher wordmark: a brand-blue rounded tile with an R, then the name.
    Used because the build environment has no network to load the live logo; if a
    Reacher logo file is supplied in the JSON it is used instead."""
    tile = size * 1.25
    c.setFillColor(mark)
    c.roundRect(x, y - tile * 0.22, tile, tile, tile * 0.28, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont(F["bold"], size * 0.9)
    c.drawCentredString(x + tile / 2, y + tile * 0.02, "R")
    c.setFillColor(color)
    c.setFont(F["bold"], size)
    c.drawString(x + tile + size * 0.4, y, "Reacher")
    return tile + size * 0.4 + pdfmetrics.stringWidth("Reacher", F["bold"], size)

def draw_logo_lockup(c, data, x, y, tmpdir, dark=True, height=26):
    """Brand logo x Reacher. Returns nothing; draws left-aligned at (x, y-baseline)."""
    brand = data["brand"]
    logo = brand.get("logo_path")
    cur = x
    if logo and os.path.exists(logo):
        iw, ih = Image.open(logo).size
        box_h = height if iw / ih > 2.2 else height * 1.9  # square-ish logos get more room
        png, dw, dh = fit_contain(logo, 130, box_h, tmpdir, "logo_lockup_%d" % int(y))
        pad = 7
        th = dh + 2 * pad
        tb = y + 8 - th / 2  # center the tile on the lockup's text line
        c.setFillColor(WHITE)
        c.roundRect(cur, tb, dw + 2 * pad, th, 8, stroke=0, fill=1)
        c.drawImage(png, cur + pad, tb + pad, dw, dh, mask="auto")
        cur += dw + 2 * pad + 12
    else:
        c.setFillColor(WHITE if dark else INK)
        c.setFont(F["bold"], 13)
        c.drawString(cur, y + 4, brand["name"])
        cur += pdfmetrics.stringWidth(brand["name"], F["bold"], 13) + 12
    c.setFillColor(BRAND_SOFT if dark else FAINT)
    c.setFont(F["light"], 14)
    c.drawString(cur, y + 4, "\u00d7")
    cur += 18
    rl = data.get("reacher_logo_path")
    if rl and os.path.exists(rl):
        png, dw, dh = fit_contain(rl, 110, height - 4, tmpdir, "rlogo_%d" % int(y))
        c.drawImage(png, cur, y, dw, dh, mask="auto")
    else:
        reacher_wordmark(c, cur, y + 4, 12.5, color=WHITE if dark else INK)

# ---------------------------------------------------------------- cover page
def draw_cover(c, data, tmpdir):
    brand = data["brand"]
    band_h = PAGE_H * 0.50
    band_y = PAGE_H - band_h

    # navy band with a soft brand glow
    c.setFillColor(NAVY)
    c.rect(0, band_y, PAGE_W, band_h, stroke=0, fill=1)
    c.saveState()
    clip = c.beginPath(); clip.rect(0, band_y, PAGE_W, band_h)
    c.clipPath(clip, stroke=0, fill=0)
    for i, a in enumerate([0.10, 0.07, 0.05, 0.03]):
        c.setFillColor(BRAND)
        c.setFillAlpha(a)
        r = 260 + i * 70
        c.circle(PAGE_W + 30, PAGE_H - 40, r, stroke=0, fill=1)
    c.restoreState()

    # lockup
    draw_logo_lockup(c, data, MARGIN, PAGE_H - MARGIN - 18, tmpdir, dark=True)

    # eyebrow
    y = PAGE_H - MARGIN - 70
    c.setFillColor(BRAND_SOFT)
    c.setFont(F["bold"], 8.5)
    label = data.get("eyebrow", "CUSTOMER STORY").upper()
    c.drawString(MARGIN, y, label)

    # headline
    head_style = S("cover_h", fontName=F["bold"], fontSize=31, leading=37, textColor=WHITE)
    p = Paragraph(esc(data["headline"]), head_style)
    w, h = p.wrap(CONTENT_W * 0.92, 300)
    if h > 160:  # long headline: step down
        head_style.fontSize, head_style.leading = 26, 31
        p = Paragraph(esc(data["headline"]), head_style)
        w, h = p.wrap(CONTENT_W * 0.92, 300)
    p.drawOn(c, MARGIN, y - 14 - h)
    y = y - 14 - h

    # summary note
    sum_style = S("cover_s", fontName=F["light"], fontSize=11, leading=16.5,
                  textColor=colors.HexColor("#D5DCF5"))
    ps = Paragraph(md(data["summary"]), sum_style)
    w2, h2 = ps.wrap(CONTENT_W * 0.86, 200)
    ps.drawOn(c, MARGIN, y - 14 - h2)

    # lower area: meta column + photo
    top = band_y - 28
    photo_w = CONTENT_W * 0.56
    photo_h = 2.55 * inch
    photo = brand.get("photo_path")
    if photo and os.path.exists(photo) and brand.get("photo_fit") == "natural":
        iw, ih = Image.open(photo).size
        photo_w = min(CONTENT_W * 0.56, photo_h * iw / ih)
    photo_x = PAGE_W - MARGIN - photo_w
    photo_y = top - photo_h
    if photo and os.path.exists(photo):
        cp = fit_crop(photo, photo_w, photo_h, tmpdir, "cover_photo")
        rounded_image(c, cp, photo_x, photo_y, photo_w, photo_h, 14)
    else:
        c.setFillColor(BRAND_TINT)
        c.roundRect(photo_x, photo_y, photo_w, photo_h, 14, stroke=0, fill=1)
        c.setFillColor(BRAND)
        c.setFont(F["med"], 11)
        c.drawCentredString(photo_x + photo_w / 2, photo_y + photo_h / 2, brand["name"])

    meta = [("Brand", brand["name"])]
    for key, lab in (("industry", "Industry"), ("category", "Product category"),
                     ("since", "On Reacher since"), ("period", "Results period")):
        if brand.get(key):
            meta.append((lab, brand[key]))
    my = top - 4
    col_w = CONTENT_W - photo_w - 22
    for lab, val in meta:
        c.setFillColor(FAINT)
        c.setFont(F["bold"], 7.2)
        c.drawString(MARGIN, my - 8, lab.upper())
        pv = Paragraph(esc(val), S("mv", fontName=F["med"], fontSize=10, leading=13,
                                   textColor=INK))
        _, hv = pv.wrap(col_w, 60)
        pv.drawOn(c, MARGIN, my - 12 - hv)
        my = my - 12 - hv - 12
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.6)
        c.line(MARGIN, my + 5, MARGIN + col_w, my + 5)

    # hero stat tiles
    stats = data.get("hero_stats", [])[:4]
    if stats:
        gap = 12
        tw = (CONTENT_W - gap * (len(stats) - 1)) / len(stats)
        th = 1.12 * inch
        ty = MARGIN + 18
        for i, s in enumerate(stats):
            tx = MARGIN + i * (tw + gap)
            c.setFillColor(BRAND if i == 0 else BRAND_TINT)
            c.roundRect(tx, ty, tw, th, 12, stroke=0, fill=1)
            c.setFillColor(WHITE if i == 0 else BRAND)
            vs = 30 if len(stats) <= 3 else 26
            while pdfmetrics.stringWidth(s["value"], F["bold"], vs) > tw - 32 and vs > 16:
                vs -= 1
            lp = Paragraph(esc(s["label"]), S("hl", fontName=F["med"], fontSize=9,
                           leading=11.5, textColor=WHITE if i == 0 else INK))
            _, lh = lp.wrap(tw - 32, 40)
            if lh > 12:
                vs = min(vs, 24)
            c.setFillColor(WHITE if i == 0 else BRAND)
            c.setFont(F["bold"], vs)
            c.drawString(tx + 16, ty + th - 16 - vs * 0.85, s["value"])
            lp.drawOn(c, tx + 16, ty + 12)
    # footer line
    c.setFillColor(FAINT)
    c.setFont(F["reg"], 7)
    c.drawString(MARGIN, MARGIN - 8, data.get("footnote_short", "Source: Reacher platform data."))
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 8, "reacherapp.com")

# ---------------------------------------------------------------- inner pages
def make_inner_decor(data, tmpdir):
    def decor(c, doc):
        c.saveState()
        # header strip
        c.setFillColor(NAVY)
        c.rect(0, PAGE_H - 0.46 * inch, PAGE_W, 0.46 * inch, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont(F["bold"], 8.5)
        c.drawString(MARGIN, PAGE_H - 0.29 * inch, data["brand"]["name"] + "  \u00d7  Reacher")
        c.setFillColor(BRAND_SOFT)
        c.setFont(F["med"], 7.5)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.29 * inch,
                          data.get("eyebrow", "Customer Story").upper())
        # footer
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.6)
        c.line(MARGIN, 0.55 * inch, PAGE_W - MARGIN, 0.55 * inch)
        c.setFillColor(FAINT)
        c.setFont(F["reg"], 7)
        c.drawString(MARGIN, 0.38 * inch, "reacherapp.com")
        c.drawRightString(PAGE_W - MARGIN, 0.38 * inch, str(doc.page))
        c.restoreState()
    return decor

def section_head(eyebrow, title):
    return [Paragraph(esc(eyebrow).upper(), ST["eyebrow"]), Paragraph(esc(title), ST["h2"])]

class Gallery(Flowable):
    """Row of up to 3 rounded image tiles. item: {path, fit: cover|contain, bg}."""
    def __init__(self, items, tmpdir, h=1.75 * inch, w=CONTENT_W, gap=10):
        super().__init__()
        self.items = [i for i in items if os.path.exists(i["path"])][:3]
        self.tmpdir, self.h, self.w, self.gap = tmpdir, h, w, gap
    def wrap(self, *a):
        return self.w, (self.h if self.items else 0)
    def draw(self):
        n = len(self.items)
        if not n: return
        c = self.canv
        tw = (self.w - self.gap * (n - 1)) / n
        for i, it in enumerate(self.items):
            x = i * (tw + self.gap)
            if it.get("fit") == "contain":
                c.setFillColor(colors.HexColor(it.get("bg", "#F8F9FC")))
                c.setStrokeColor(BORDER); c.setLineWidth(0.7)
                c.roundRect(x, 0, tw, self.h, 12, stroke=1, fill=1)
                png, dw, dh = fit_contain(it["path"], tw - 20, self.h - 20, self.tmpdir,
                                          f"gal{i}")
                c.drawImage(png, x + (tw - dw) / 2, (self.h - dh) / 2, dw, dh, mask="auto")
            else:
                cp = fit_crop(it["path"], tw, self.h, self.tmpdir, f"gal{i}")
                rounded_image(c, cp, x, 0, tw, self.h, 12)

class Rule(Flowable):
    def __init__(self, w, color=BORDER, thick=0.7, space=6):
        super().__init__(); self.w, self.color, self.thick, self.space = w, color, thick, space
    def wrap(self, *a): return self.w, self.space * 2
    def draw(self):
        self.canv.setStrokeColor(self.color); self.canv.setLineWidth(self.thick)
        self.canv.line(0, self.space, self.w, self.space)

class QuoteBlock(Flowable):
    """Left brand bar + italic pull quote."""
    def __init__(self, text, attribution=None, w=CONTENT_W):
        super().__init__()
        self.p = Paragraph("\u201c" + esc(text) + "\u201d", ST["quote"])
        self.a = Paragraph(esc(attribution), ST["small"]) if attribution else None
        self.w = w
    def wrap(self, aw, ah):
        _, self.ph = self.p.wrap(self.w - 34, ah)
        self.ah = self.a.wrap(self.w - 34, ah)[1] + 4 if self.a else 0
        self.h = self.ph + self.ah + 24
        return self.w, self.h
    def draw(self):
        c = self.canv
        c.setFillColor(BRAND_TINT)
        c.roundRect(0, 0, self.w, self.h, 10, stroke=0, fill=1)
        c.setFillColor(BRAND)
        c.roundRect(0, 0, 5, self.h, 2.5, stroke=0, fill=1)
        self.p.drawOn(c, 22, self.h - 12 - self.ph)
        if self.a:
            self.a.drawOn(c, 22, 10)

def kpi_grid(kpis, cols=3):
    cells, row = [], []
    cw = CONTENT_W / cols
    for k in kpis:
        parts = [Paragraph(esc(k["value"]), ST["kpi_val"]), Spacer(1, 3),
                 Paragraph(esc(k["label"]), ST["kpi_lab"])]
        if k.get("sub"):
            parts += [Spacer(1, 2), Paragraph(esc(k["sub"]), ST["kpi_sub"])]
        row.append(parts)
        if len(row) == cols:
            cells.append(row); row = []
    if row:
        while len(row) < cols: row.append("")
        cells.append(row)
    t = Table(cells, colWidths=[cw] * cols)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 13 if len(cells) <= 3 else 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 13 if len(cells) <= 3 else 10),
        ("BOX", (0, 0), (-1, -1), 0.8, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.8, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
    ]
    t.setStyle(TableStyle(style))
    return t

def pillar_cards(pillars, start=0):
    cols = 2
    cw = (CONTENT_W - 12) / cols
    rows, row = [], []
    for i, p in enumerate(pillars):
        num = Table([[Paragraph(f"{start+i+1:02d}", S("n", fontName=F["bold"], fontSize=8,
                     leading=10, textColor=WHITE, alignment=TA_CENTER))]],
                    colWidths=[22], rowHeights=[16])
        num.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND),
                                 ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 2),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        num.hAlign = "LEFT"
        inner = [num, Spacer(1, 7), Paragraph(esc(p["title"]), ST["h3"]),
                 Paragraph(md(p["body"]), S("pb", fontSize=9, leading=13.5, textColor=TEXT))]
        if p.get("stat"):
            inner += [Spacer(1, 5), Paragraph(md(p["stat"]), S("ps", fontName=F["med"],
                      fontSize=8.5, leading=11.5, textColor=BRAND))]
        card = Table([[inner]], colWidths=[cw])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FC")),
            ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
            ("ROUNDEDCORNERS", [10, 10, 10, 10]),
            ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 13), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        row.append(card)
        if len(row) == cols:
            rows.append(row); row = []
    if row:
        row.append(""); rows.append(row)
    grid = Table(rows, colWidths=[cw + 6, cw + 6])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return grid

class BeforeAfter(Flowable):
    """Rows of: label | before value -> after value | multiplier chip, with bars."""
    def __init__(self, rows, caption=None, w=CONTENT_W):
        super().__init__(); self.rows, self.w, self.caption = rows, w, caption
        self.rh = 44
    def wrap(self, *a):
        self.h = len(self.rows) * self.rh + 8
        return self.w, self.h
    def draw(self):
        c = self.canv
        for i, r in enumerate(self.rows):
            y = self.h - (i + 1) * self.rh
            c.setFillColor(WHITE); c.setStrokeColor(BORDER); c.setLineWidth(0.7)
            c.roundRect(0, y + 4, self.w, self.rh - 8, 9, stroke=1, fill=1)
            c.setFillColor(INK); c.setFont(F["med"], 9.5)
            c.drawString(14, y + self.rh - 20, r["label"])
            c.setFillColor(FAINT); c.setFont(F["reg"], 7.8)
            c.drawString(14, y + 11, f"From {r['before']} to {r['after']}")
            # bars: label column + bar on the same line
            lx, lw = self.w * 0.38, 58
            bx, bw = lx + lw, self.w * 0.60 - lw - 90
            bv, av = float(r.get("before_num", 0) or 0), float(r.get("after_num", 0) or 0)
            mx = max(bv, av, 1)
            y1, y2 = y + self.rh - 21, y + 12
            c.setFillColor(FAINT); c.setFont(F["reg"], 6.8)
            c.drawRightString(lx + lw - 8, y1 + 1, r.get("before_label", "Before"))
            c.drawRightString(lx + lw - 8, y2 + 1, r.get("after_label", "With Reacher"))
            c.setFillColor(BORDER_STRONG)
            c.roundRect(bx, y1, max(8, bw * bv / mx), 7, 3.5, stroke=0, fill=1)
            c.setFillColor(BRAND)
            c.roundRect(bx, y2, max(8, bw * av / mx), 7, 3.5, stroke=0, fill=1)
            # chip
            chip = r["multiplier"]
            cw = pdfmetrics.stringWidth(chip, F["bold"], 12) + 20
            cx = self.w - 14 - cw
            c.setFillColor(POS_TINT)
            c.roundRect(cx, y + self.rh / 2 - 12, cw, 22, 11, stroke=0, fill=1)
            c.setFillColor(POS); c.setFont(F["bold"], 12)
            c.drawCentredString(cx + cw / 2, y + self.rh / 2 - 5, chip)

# ---------------------------------------------------------------- charts
def fmt_num(v, money=False, cur="$"):
    a = abs(v)
    if a >= 1e6: s = f"{v/1e6:.1f}M"
    elif a >= 1e3: s = f"{v/1e3:.1f}K" if a < 1e5 else f"{v/1e3:.0f}K"
    else: s = f"{v:,.0f}"
    s = s.replace(".0M", "M").replace(".0K", "K")
    return (cur + s) if money else s

def trend_charts(monthly, tmpdir, currency="$"):
    months = monthly["labels"]
    series = monthly["series"][:4]
    n = len(series)
    ncols = 2 if n > 1 else 1
    nrows = (n + 1) // 2
    plt.rcParams["font.family"] = F["mpl"]
    fig, axes = plt.subplots(nrows, ncols, figsize=(7.3, 1.75 * nrows), dpi=220,
                             squeeze=False)
    notes = []
    for idx, s in enumerate(series):
        ax = axes[idx // ncols][idx % ncols]
        vals = [float(v or 0) for v in s["values"]]
        money = s.get("money", False)
        # biggest month-over-month absolute jump
        jumps = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
        j = (jumps.index(max(jumps)) + 1) if jumps and max(jumps) > 0 else None
        if s.get("highlight_index") is not None:
            j = s["highlight_index"]
        cols = ["#C9D4FB"] * len(vals)
        if j is not None: cols[j] = "#3559E9"
        x = range(len(vals))
        if s.get("values2"):  # e.g. total shop GMV drawn behind affiliate GMV
            v2 = [float(t or 0) for t in s["values2"]]
            ax.bar(x, v2, color="#101828", alpha=0.10, width=0.8, zorder=2,
                   label=s.get("name2", "Total"))
            ax.bar(x, vals, color=cols, width=0.5, zorder=3, label=s.get("name1", s["name"]))
            k2 = max(range(len(v2)), key=lambda i: v2[i])
            ax.annotate(fmt_num(v2[k2], money, currency), (k2, v2[k2]),
                        textcoords="offset points", xytext=(0, 3), ha="center",
                        fontsize=7, fontweight="bold", color="#475467")
            ax.legend(fontsize=6.5, frameon=False, loc="upper left", handlelength=1,
                      labelcolor="#475467")
            if j is not None and abs(vals[j] - v2[k2]) / max(v2[k2], 1) < 0.25 and j == k2:
                s = dict(s, _skip_primary_label=True)
        else:
            ax.bar(x, vals, color=cols, width=0.68, zorder=3)
        ax.set_title(s["name"], loc="left", fontsize=9.5, fontweight="bold",
                     color="#101828", pad=8)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#D0D5DD")
        ax.tick_params(axis="both", labelsize=6.8, colors="#667085", length=0)
        ax.grid(axis="y", color="#EEF0F4", zorder=0)
        step = max(1, len(months) // 8)
        ax.set_xticks(list(x)[::step])
        ax.set_xticklabels(months[::step])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, p, m=money: fmt_num(v, m, currency)))
        if j is not None:
            if s.get("_skip_primary_label"):  # shares its bar with the total: label beside it
                ax.annotate(fmt_num(vals[j], money, currency), (j - 0.45, vals[j]),
                            textcoords="offset points", xytext=(-2, -4), ha="right",
                            fontsize=7, fontweight="bold", color="#3559E9")
            else:
                ax.annotate(fmt_num(vals[j], money, currency), (j, vals[j]),
                            textcoords="offset points", xytext=(0, 3), ha="center",
                            fontsize=7, fontweight="bold", color="#3559E9")
            prev = vals[j - 1] if j > 0 else 0
            notes.append((s["name"], months[j], prev, vals[j], money))
    for k in range(n, nrows * ncols):
        axes[k // ncols][k % ncols].axis("off")
    fig.tight_layout(h_pad=2.2, w_pad=2.5)
    out = os.path.join(tmpdir, "trends.png")
    fig.savefig(out, transparent=False, facecolor="white")
    plt.close(fig)
    return out, 7.3, 1.75 * nrows, notes

def monthly_table(monthly, currency="$"):
    labels = monthly["labels"]
    series = monthly.get("table_series") or monthly["series"]
    hr = ParagraphStyle("cell_hr", parent=ST["cell_h"], alignment=2)
    head = [Paragraph("MONTH", ST["cell_h"])] + [
        Paragraph(esc(s["name"]).upper(), hr) for s in series]
    rows = [head]
    for i, m in enumerate(labels):
        r = [Paragraph(esc(m), ST["cell_b"])]
        for s in series:
            v = s["values"][i]
            r.append(Paragraph("\u2013" if v is None else
                     (fmt_num(float(v), s.get("money"), currency) if s.get("compact")
                      else (f"{currency}{float(v):,.0f}" if s.get("money") else f"{float(v):,.0f}")),
                     S("c", fontSize=8.4, leading=11, textColor=TEXT, alignment=2)))
        rows.append(r)
    cw0 = 62
    cw = (CONTENT_W - cw0) / len(series)
    t = Table(rows, colWidths=[cw0] + [cw] * len(series), repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F7")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    hi = monthly.get("best_month_index")
    if hi is not None:
        style += [("BACKGROUND", (0, hi + 1), (-1, hi + 1), BRAND_TINT)]
    t.setStyle(TableStyle(style))
    return t

def wins_list(wins):
    rows = []
    for w in wins:
        chk = Table([[Paragraph("\u2713", S("ck", fontName="Helvetica-Bold", fontSize=9,
                     leading=10, textColor=WHITE, alignment=TA_CENTER))]],
                    colWidths=[16], rowHeights=[16])
        chk.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), POS),
                                 ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 1),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        rows.append([chk, Paragraph(md(w), S("w", fontSize=10, leading=14.5, textColor=TEXT))])
    t = Table(rows, colWidths=[26, CONTENT_W - 26])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t

class CTABand(Flowable):
    def __init__(self, title, body, w=CONTENT_W):
        super().__init__()
        self.t = Paragraph(esc(title), S("ct", fontName=F["bold"], fontSize=15, leading=19,
                                         textColor=WHITE))
        self.b = Paragraph(md(body), S("cb", fontName=F["light"], fontSize=9.5, leading=14,
                                       textColor=colors.HexColor("#D5DCF5")))
        self.w = w
    def wrap(self, aw, ah):
        _, self.th = self.t.wrap(self.w - 48, ah)
        _, self.bh = self.b.wrap(self.w - 48, ah)
        self.h = self.th + self.bh + 36
        return self.w, self.h
    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.roundRect(0, 0, self.w, self.h, 14, stroke=0, fill=1)
        c.saveState()
        p = c.beginPath(); p.roundRect(0, 0, self.w, self.h, 14); c.clipPath(p, stroke=0)
        c.setFillColor(BRAND); c.setFillAlpha(0.18)
        c.circle(self.w - 20, self.h + 10, 120, stroke=0, fill=1)
        c.restoreState()
        self.t.drawOn(c, 24, self.h - 16 - self.th)
        self.b.drawOn(c, 24, 16)

# ---------------------------------------------------------------- assemble
def build(data, out_path):
    tmpdir = tempfile.mkdtemp()
    cur = data.get("currency_symbol", "$")

    doc = BaseDocTemplate(out_path, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=0.8 * inch, bottomMargin=0.75 * inch,
                          title=data["headline"], author="Reacher",
                          subject=f"{data['brand']['name']} customer story")
    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover")
    inner_frame = Frame(MARGIN, 0.75 * inch, CONTENT_W, PAGE_H - 0.8 * inch - 0.75 * inch - 0.1 * inch,
                        id="inner", leftPadding=0, rightPadding=0, topPadding=6, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame],
                     onPage=lambda c, d: draw_cover(c, data, tmpdir)),
        PageTemplate(id="Inner", frames=[inner_frame], onPage=make_inner_decor(data, tmpdir)),
    ])

    story = [NextPageTemplate("Inner"), Spacer(1, 1), PageBreak()]

    # --- By the numbers
    btn = data.get("by_the_numbers", {})
    story += section_head(btn.get("eyebrow", "By the numbers"),
                          btn.get("title", "Everything since joining Reacher"))
    if btn.get("intro"):
        story.append(Paragraph(md(btn["intro"]), ST["body"]))
    story.append(Spacer(1, 6))
    story.append(kpi_grid(data["kpis"]))
    if btn.get("note"):
        story += [Spacer(1, 5), Paragraph(esc(btn["note"]), ST["tiny"])]
    story.append(Spacer(1, 22))

    # --- About
    ab = data.get("about")
    if ab:
        blk = section_head(ab.get("eyebrow", "About " + data["brand"]["name"]), ab["title"])
        for para in ab["body"] if isinstance(ab["body"], list) else [ab["body"]]:
            blk.append(Paragraph(md(para), ST["body"]))
        if ab.get("gallery"):
            blk += [Spacer(1, 6), Gallery(ab["gallery"], tmpdir,
                                          h=ab.get("gallery_height", 1.75) * inch)]
        story.append(KeepTogether(blk))
        story.append(Spacer(1, 14))

    breaks = set(data.get("page_breaks_before", []))
    def brk(name):
        # break only if we're not already at the top of a fresh page
        if name in breaks:
            story.append(CondPageBreak(inner_frame._aH - 30))

    # --- Challenge
    ch = data.get("challenge")
    brk("challenge")
    if ch:
        block = section_head(ch.get("eyebrow", "The challenge"), ch["title"])
        for para in ch["body"] if isinstance(ch["body"], list) else [ch["body"]]:
            block.append(Paragraph(md(para), ST["body"]))
        story.append(KeepTogether(block))
        if ch.get("quote"):
            story += [Spacer(1, 6), QuoteBlock(ch["quote"], ch.get("quote_attribution"))]
        story.append(Spacer(1, 14))

    # --- Solution
    so = data.get("solution")
    brk("solution")
    if so:
        head = section_head(so.get("eyebrow", "The solution"), so["title"])
        if so.get("intro"):
            head.append(Paragraph(md(so["intro"]), ST["body"]))
        head.append(Spacer(1, 8))
        story.append(KeepTogether(head + [pillar_cards(so["pillars"][:2])]))
        if len(so["pillars"]) > 2:
            story.append(pillar_cards(so["pillars"][2:], start=2))
        if so.get("quote"):
            story += [Spacer(1, 4), QuoteBlock(so["quote"], so.get("quote_attribution"))]
        story.append(Spacer(1, 14))

    # --- Result
    rs = data.get("result")
    brk("result")
    if rs:
        blk = section_head(rs.get("eyebrow", "The result"), rs["title"])
        for para in rs["body"] if isinstance(rs["body"], list) else [rs["body"]]:
            blk.append(Paragraph(md(para), ST["body"]))
        if rs.get("wins"):
            blk += [Spacer(1, 6), Paragraph("WINS", ST["eyebrow"]), wins_list(rs["wins"])]
        story.append(KeepTogether(blk))
        if rs.get("quote"):
            story += [Spacer(1, 8), QuoteBlock(rs["quote"], rs.get("quote_attribution"))]
        story.append(Spacer(1, 18))

    # --- Before -> with Reacher
    ba = data.get("before_after")
    brk("before_after")
    if ba and ba.get("rows"):
        blk = section_head(ba.get("eyebrow", "Before vs. with Reacher"), ba["title"])
        if ba.get("intro"):
            blk.append(Paragraph(md(ba["intro"]), ST["body"]))
        blk += [Spacer(1, 4), BeforeAfter(ba["rows"])]
        if ba.get("note"):
            blk += [Spacer(1, 2), Paragraph(esc(ba["note"]), ST["tiny"])]
        story.append(KeepTogether(blk))
        story.append(Spacer(1, 16))

    # --- Month by month
    mo = data.get("monthly")
    brk("monthly")
    if mo and mo.get("labels"):
        png, wi, hi, notes = trend_charts(mo, tmpdir, cur)
        img_w = CONTENT_W
        img_h = img_w * hi / wi
        blk = section_head(mo.get("eyebrow", "Month by month"),
                           mo.get("title", "Where the program grew the most"))
        if mo.get("insight"):
            blk.append(Paragraph(md(mo["insight"]), ST["body"]))
        blk += [Spacer(1, 4), RLImage(png, width=img_w, height=img_h)]
        blk.append(Paragraph("Highlighted bar = the month with the largest month-over-month "
                             "increase for that metric.", ST["tiny"]))
        story.append(KeepTogether(blk))
        if mo.get("show_table", True):
            tbl = monthly_table(mo, cur)
            story += [Spacer(1, 8), KeepTogether([tbl]) if len(mo["labels"]) <= 14 else tbl]
        if mo.get("note"):
            story += [Spacer(1, 4), Paragraph(esc(mo["note"]), ST["tiny"])]
        story.append(Spacer(1, 12))

    # --- CTA
    cta = data.get("cta")
    if cta:
        story.append(KeepTogether([CTABand(cta["title"], cta["body"])]))

    if data.get("footnote"):
        story += [Spacer(1, 10), Paragraph(esc(data["footnote"]), ST["tiny"])]

    doc.build(story)
    return out_path

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    with open(sys.argv[1]) as fh:
        content = json.load(fh)
    print(build(content, sys.argv[2]))
