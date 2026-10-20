"""Извлечение формул профилей края из таблиц техзаданий «К-расчёту-профиля…» (DOCX).

Формулы в DOCX — объекты MathType (OLE) с превью в формате WMF. Мы читаем
таблицу document.xml (строка = отверстие, ячейки a, b, c, формула), находим
WMF-превью формулы в этой строке и восстанавливаем текст формулы по записям
TextOut (координаты MoveTo + шрифт Times/Symbol). Структура всех формул:

    h(n) = s · (b/π) · atan[ 2π · (K1·c − K2·n) · 1.893 / (a · 100) ] + d

где s = ±1, K1, K2, d — константы, своие для каждого отверстия (их и нужно
извлечь), a, b, c — из соседних ячеек таблицы. Ничего не реконструируется
«по догадке»: если в строке нет формулы — это фиксируется.
"""
from __future__ import annotations

import re
import struct
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

SYMBOL_MAP = {"Ч": "·", "p": "π", "й": "⎡", "к": "⎢", "л": "⎣", "щ": "⎤", "ъ": "⎥", "ы": "⎦", "-": "−"}


@dataclass
class WmfText:
    x: int
    y: int
    text: str
    font: str


def wmf_texts(data: bytes) -> list[WmfText]:
    """Тексты WMF (META_TEXTOUT) с позициями; поддержан placeable-заголовок."""
    off = 22 if struct.unpack("<I", data[:4])[0] == 0x9AC6CDD7 else 0
    p = off + struct.unpack("<H", data[off + 2:off + 4])[0] * 2
    objs: list = [None] * 256
    font = ("", 0)
    cp = None
    out = []
    while p + 6 <= len(data):
        size, fn = struct.unpack("<IH", data[p:p + 6])
        if size == 0:
            break
        rec = data[p + 6:p + size * 2]
        if fn == 0x02FB:  # CreateFontIndirect
            h = struct.unpack("<h", rec[:2])[0]
            name = rec[18:].split(b"\0")[0].decode("latin1")
            objs[objs.index(None)] = (name, h)
        elif fn in (0x00F8, 0x01F9, 0x02FA, 0x0142, 0x06FF, 0x01FC, 0x02FC, 0x06FC):
            objs[objs.index(None)] = ("x", 0)
        elif fn == 0x012D:  # SelectObject
            i = struct.unpack("<H", rec[:2])[0]
            if i < len(objs) and objs[i] and objs[i][0] != "x":
                font = objs[i]
        elif fn == 0x01F0:  # DeleteObject
            objs[struct.unpack("<H", rec[:2])[0]] = None
        elif fn == 0x0214:  # MoveTo
            y, x = struct.unpack("<hh", rec[:4])
            cp = (x, y)
        elif fn == 0x0521:  # TextOut
            n = struct.unpack("<h", rec[:2])[0]
            s = rec[2:2 + n].decode("cp1251")
            q = 2 + n + (n % 2)
            y, x = struct.unpack("<hh", rec[q:q + 4])
            if font[0].startswith("Symbol"):
                s = "".join(SYMBOL_MAP.get(c, c) for c in s)
            pos = (x, y) if (x, y) != (0, 0) else (cp or (0, 0))
            out.append(WmfText(pos[0], pos[1], s, font[0]))
            cp = None
        p += size * 2
    return out


@dataclass
class ProfileFormula:
    hole_um: float
    a: float
    b: float
    c: float
    formula_present: bool
    sign: int | None = None
    K1: float | None = None
    K2: float | None = None
    scale: float | None = None      # множитель 1.893
    denom: float | None = None      # «a·100» → 100
    offset_d: float | None = None
    rendered: str = ""
    source_object: str = ""
    notes: list[str] = field(default_factory=list)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_formula(texts: list[WmfText]) -> dict:
    """Разбор формулы по геометрии: числитель/знаменатель внутренней дроби и хвост «+ d»."""
    ys = sorted({t.y for t in texts if t.font.startswith("Times")})
    # Внутренняя скобка: все символы между открывающей ⎡ (x≈47..52) и закрывающей ⎤ (вторая слева)
    left = sorted(t.x for t in texts if t.text == "⎡")
    right = sorted(t.x for t in texts if t.text == "⎤")
    if len(left) < 2 or len(right) < 2:
        raise ValueError("unexpected bracket structure")
    x_in0, x_in1 = left[1], right[0]
    inner = sorted((t for t in texts if x_in0 < t.x < x_in1 and t.text not in "⎡⎢⎣⎤⎥⎦"), key=lambda t: t.x)
    y_num = min(t.y for t in inner)
    y_den = max(t.y for t in inner)
    num = [t.text for t in inner if t.y == y_num]
    den = [t.text for t in inner if t.y == y_den]
    head = sorted((t for t in texts if t.x < x_in0 and t.text not in "⎡⎢⎣"), key=lambda t: t.x)
    tail = sorted((t for t in texts if t.x > right[-1] and t.text not in "⎤⎥⎦"), key=lambda t: t.x)
    sign = -1 if any(t.text == "−" for t in head) else 1
    nums_num = [_num(s) for s in num if re.fullmatch(r"[0-9.]+", s)]
    # числитель: 2 · π ( K1 · c − K2 · n ) · 1.893
    if len(nums_num) != 4 or nums_num[0] != 2:
        raise ValueError(f"unexpected numerator {num}")
    K1, K2, scale = nums_num[1], nums_num[2], nums_num[3]
    nums_den = [_num(s) for s in den if re.fullmatch(r"[0-9.]+", s)]
    d_sign = -1 if any(t.text == "−" for t in tail) else 1
    d_vals = [_num(t.text) for t in tail if re.fullmatch(r"[0-9.]+", t.text)]
    rendered = (f"h(n) = {'−' if sign < 0 else ''}(b/π)·atan[2π·({K1:g}·c − {K2:g}·n)·{scale:g}/(a·{nums_den[0]:g})]"
                f" {'−' if d_sign < 0 else '+'} {d_vals[0]:g}")
    return {"sign": sign, "K1": K1, "K2": K2, "scale": scale, "denom": nums_den[0],
            "offset_d": d_sign * d_vals[0], "rendered": rendered}


def extract_docx(path: Path) -> tuple[str, list[ProfileFormula], list[str]]:
    """Возвращает (описательный текст, формулы по строкам таблицы, предупреждения)."""
    z = zipfile.ZipFile(path)
    xml = z.read("word/document.xml").decode("utf8")
    rels = z.read("word/_rels/document.xml.rels").decode("utf8")
    rid = {}
    for m in re.finditer(r"<Relationship ([^>]*)/>", rels):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        rid[a["Id"]] = a["Target"]
    text = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml.split("<w:tbl>")[0]))
    rows = []
    warnings = []
    used = set()
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", xml, flags=re.S):
        cells = re.findall(r"<w:tc>.*?</w:tc>", tr, flags=re.S)
        vals = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", c)).strip() for c in cells]
        if not vals or not re.fullmatch(r"[0-9]+", vals[0] or ""):
            continue
        hole = float(vals[0])
        a, b, c = _num(vals[1]), _num(vals[2]), _num(vals[3])
        imgs = [rid[r] for r in re.findall(r'r:id="(rId\d+)"', cells[4] if len(cells) > 4 else "")
                if rid.get(r, "").endswith(".wmf")]
        pf = ProfileFormula(hole, a, b, c, bool(imgs))
        if imgs:
            used.add(imgs[0])
            pf.source_object = f"{path.name}:word/{imgs[0]}"
            try:
                pf.__dict__.update(parse_formula(wmf_texts(z.read("word/" + imgs[0]))))
            except Exception as e:  # noqa: BLE001
                pf.notes.append(f"формула не разобрана: {e}")
        else:
            pf.notes.append("в ячейке таблицы нет формулы (объект отсутствует)")
        rows.append(pf)
    orphans = sorted(n for n in z.namelist() if n.endswith(".wmf") and n.replace("word/", "") not in used)
    for o in orphans:
        try:
            f = parse_formula(wmf_texts(z.read(o)))
            warnings.append(f"в DOCX есть неиспользуемый в таблице объект {o}: {f['rendered']} — "
                            "к какому отверстию относится, не установлено")
        except Exception:  # noqa: BLE001
            warnings.append(f"неиспользуемый объект {o} (не разобран)")
    return text, rows, warnings


DOCS = {
    "be_200": "К-расчёту-профиля-бериллий 200 мкм.docx",
    "carbon_475": "К-расчёту-профиля-стеклоуглерод.docx",
    "sapphire_contact": "К-расчёту-профиля-лейкосапфир.docx",
    "sapphire_280mm": "К-расчёту-профиля-лейкосапфир-280мм-от-маски.docx",
}


def extract_all(doc_dir: Path) -> dict:
    out = {}
    for exp, fn in DOCS.items():
        text, rows, warns = extract_docx(doc_dir / fn)
        out[exp] = {"document": fn, "profiles": [asdict(r) for r in rows], "warnings": warns}
    return out
