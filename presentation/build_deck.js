// Генератор презентации доклада (pptxgenjs). Всё на слайдах — родные объекты PowerPoint:
// текст, фигуры схем, таблицы и диаграммы редактируются, картинки перемещаются.
// Запуск: python presentation/prepare_data.py && node presentation/build_deck.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..");
const RES = path.join(ROOT, "results");
const OUT = path.join(HERE, "Доклад_мембраны_LIGA.pptx");
const D = JSON.parse(fs.readFileSync(path.join(HERE, "deck_data.json"), "utf8"));
const APPLY_THEME = process.env.APPLY_THEME_JS;

const THEME = {
  name: "LIGA Synchrotron",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B1F2A", lt1: "FFFFFF", dk2: "0F2B46", lt2: "EEF2F6",
    accent1: "E3A21A", accent2: "1F8A9E", accent3: "C8463D", accent4: "6C7A89",
    accent5: "7B5EA7", accent6: "3E7CB1", hlink: "1F8A9E", folHlink: "7B5EA7",
  },
};
// цвета материалов на схемах (как в «Схемы.pptx») и серий на графиках — hex
const MAT = { Be: "F39C3C", Al: "D5D9DF", membrane: "9B7BC8", Au: "E3A21A", Ti: "8A939E", kapton: "5BC8D6", pmma: "3E7CB1" };
const CFG_COLOR = { be_200: "F39C3C", carbon_475: "4A4F57", sapphire_contact: "B8327A", sapphire_280mm: "E68FB8", titanium_model: "8A939E" };
const CAT_COLOR = {
  direct: "3E7CB1", membrane_rayleigh_only: "B8327A", membrane_compton: "E68FB8", al_filter_scatter: "C9CED6",
  mask_support_scatter: "8A939E", other_scatter: "F2D08A", pmma_self_scatter: "9CC9D3", external_secondary: "C7881A",
};
const HEX = THEME.colors;

const W = 13.333, H = 7.5, MX = 0.6;
const TOP = 1.55; // начало содержимого под заголовком

async function icon(Comp, color = "FFFFFF") {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: "256" }));
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
async function imgSize(p) {
  const m = await sharp(p).metadata();
  return { w: m.width, h: m.height };
}
const fmt = (v, d = 1) => v.toFixed(d).replace(".", ",");

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = "Рассеяние СИ в мембранах рентгеношаблонов";
  pres.subject = "Станция LIGA ВЭПП-3, моделирование Geant4";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const S = pres.shapes;

  // ---------- Макеты (layouts) ----------
  const footer = { text: { text: "Станция LIGA · ВЭПП-3 · Geant4", options: { x: MX, y: 7.05, w: 6, h: 0.3, fontSize: 10, color: C.accent4, margin: 0 } } };
  pres.defineSlideMaster({
    title: "TITLE",
    background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "kicker", type: "body", x: MX, y: 1.2, w: 8.4, h: 0.4, fontSize: 14, bold: true, color: C.accent1, charSpacing: 2, margin: 0 }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 1.75, w: 8.4, h: 2.3, fontFace: THEME.headFontFace, fontSize: 40, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "subtitle", type: "body", x: MX, y: 4.2, w: 8.0, h: 1.0, fontSize: 18, color: "CADCFC", valign: "top", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "author", type: "body", x: MX, y: 5.9, w: 8.0, h: 0.8, fontSize: 16, color: C.background1, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    objects: [
      { placeholder: { options: { name: "kicker", type: "body", x: MX, y: 0.32, w: 10, h: 0.3, fontSize: 12, bold: true, color: C.accent2, charSpacing: 1.5, margin: 0 }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.62, w: W - 2 * MX, h: 0.75, fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.text2, valign: "top", align: "left", margin: 0 }, text: "" } },
      footer,
    ],
    slideNumber: { x: W - MX - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.accent4, align: "right" },
  });
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "kicker", type: "body", x: MX, y: 0.32, w: 10, h: 0.3, fontSize: 12, bold: true, color: C.accent1, charSpacing: 1.5, margin: 0 }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.62, w: W - 2 * MX, h: 0.75, fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - MX - 0.6, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: "CADCFC", align: "right" },
  });

  // ---------- общие элементы ----------
  const shadow = () => ({ type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 });
  function card(slide, x, y, w, h, opts = {}) {
    slide.addShape(S.ROUNDED_RECTANGLE, {
      x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill || C.background2 },
      line: { color: opts.line || C.background2, width: 0.75 }, shadow: opts.shadow ? shadow() : undefined,
      objectName: opts.name,
    });
  }
  function iconCircle(slide, x, y, d, data, color, name) {
    slide.addShape(S.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color, width: 0 }, objectName: name ? name + " — круг" : undefined });
    const p = d * 0.27;
    slide.addImage({ data, x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, objectName: name ? name + " — иконка" : undefined });
  }
  function text(slide, t, o) {
    slide.addText(t, Object.assign({ isTextBox: true, margin: 0, fontSize: 14, color: C.text1, valign: "top" }, o));
  }
  function arrowLine(slide, x1, y1, x2, y2, o = {}) {
    slide.addShape(S.LINE, {
      x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.max(Math.abs(x2 - x1), 0.001), h: Math.max(Math.abs(y2 - y1), 0.001),
      flipH: x2 < x1, flipV: y2 < y1,
      line: { color: o.color || HEX.dk1, width: o.width || 1.5, dashType: o.dash || "solid", endArrowType: o.end === undefined ? "triangle" : o.end, beginArrowType: o.begin },
      objectName: o.name,
    });
  }
  const content = (section, kicker, title) => {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    s.addText(kicker, { placeholder: "kicker" });
    s.addText(title, { placeholder: "title" });
    return s;
  };
  const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", valAxisTitleFontFace: "+mn-lt", catAxisTitleFontFace: "+mn-lt" };
  const axisStyle = () => ({
    catAxisLabelColor: "4A5568", valAxisLabelColor: "4A5568", catAxisLabelFontSize: 12, valAxisLabelFontSize: 12,
    valGridLine: { color: "E2E8F0", size: 0.75 }, catGridLine: { style: "none" }, catAxisLineShow: true, valAxisLineShow: false,
    dataLabelColor: "1B1F2A", dataLabelFontSize: 11, legendFontSize: 12, legendColor: "1B1F2A",
    valAxisTitleColor: "4A5568", valAxisTitleFontSize: 12, catAxisTitleColor: "4A5568", catAxisTitleFontSize: 12,
  });

  const I = {
    layers: await icon(fa.FaLayerGroup), atom: await icon(fa.FaAtom), ruler: await icon(fa.FaRulerHorizontal),
    balance: await icon(fa.FaBalanceScale), question: await icon(fa.FaQuestion), check: await icon(fa.FaCheck),
    times: await icon(fa.FaTimes), approx: await icon(fa.FaWaveSquare), arrow: await icon(fa.FaArrowRight),
    micro: await icon(fa.FaMicroscope), flask: await icon(fa.FaFlask), cogs: await icon(fa.FaCogs),
    warn: await icon(fa.FaExclamationTriangle), weight: await icon(fa.FaWeightHanging), expand: await icon(fa.FaExpandArrowsAlt),
    bolt: await icon(fa.FaBolt), cube: await icon(fa.FaCube), search: await icon(fa.FaSearch), chart: await icon(fa.FaChartLine),
  };

  const cfg = Object.fromEntries(D.configs.map((c) => [c.key, c]));
  const RA = D.runs_all;
  const wMin = Math.min(...RA.map((r) => r.width_10_90)), wMax = Math.max(...RA.map((r) => r.width_10_90));
  const [devMin, devMax] = D.development_lateral_width_um;
  const range = (a, b, d = 1) => `${fmt(a, d)}–${fmt(b, d)}`;
  const SEC = ["1. Задача", "2. Модель", "3. Ограничения", "4. Результаты", "5. Эксперимент", "6. Выводы", "Литература"];

  // ================= 1. Титул =================
  pres.addSection({ title: SEC[0] });
  {
    const s = pres.addSlide({ masterName: "TITLE", sectionTitle: SEC[0] });
    s.addText("СТАНЦИЯ LIGA · ВЭПП-3 · GEANT4", { placeholder: "kicker" });
    s.addText("Рассеяние синхротронного излучения мембранами масок для рентгенолитографии", { placeholder: "title" });
    s.addText("Моделирование Geant4 и эксперименты на ВЭПП-3: как материал, толщина и положение мембраны влияют на дозу в ПММА", { placeholder: "subtitle" });
    s.addText([{ text: "А. А. Неустроева, В. П. Назьмов, Б. Г. Гольденберг", options: { bold: true, breakLine: true } }, { text: "ИЯФ СО РАН · ЦКП «СКИФ» ИК СО РАН · ИХТТМ СО РАН · 2026", options: { fontSize: 13, color: "CADCFC" } }], { placeholder: "author" });
    // стилизованная маска: пучок → золото с окном → ПММА
    const x0 = 9.6;
    for (let i = 0; i < 7; i++) {
      const y = 2.0 + i * 0.5;
      s.addShape(S.LINE, { x: 9.0, y, w: 1.5, h: 0, line: { color: HEX.accent1, width: 2, transparency: 30 }, objectName: `Луч ${i + 1}` });
    }
    s.addShape(S.RECTANGLE, { x: x0 + 0.95, y: 1.6, w: 0.35, h: 1.6, fill: { color: MAT.Au }, line: { color: MAT.Au, width: 0 }, objectName: "Au верх" });
    s.addShape(S.RECTANGLE, { x: x0 + 0.95, y: 4.5, w: 0.35, h: 1.6, fill: { color: MAT.Au }, line: { color: MAT.Au, width: 0 }, objectName: "Au низ" });
    s.addShape(S.RECTANGLE, { x: x0 + 1.3, y: 1.6, w: 0.08, h: 4.5, fill: { color: MAT.Ti }, line: { color: MAT.Ti, width: 0 }, objectName: "Ti" });
    s.addShape(S.RECTANGLE, { x: x0 + 1.38, y: 1.6, w: 0.18, h: 4.5, fill: { color: MAT.kapton }, line: { color: MAT.kapton, width: 0 }, objectName: "Каптон" });
    s.addShape(S.RECTANGLE, { x: x0 + 1.56, y: 1.6, w: 0.5, h: 4.5, fill: { color: MAT.pmma }, line: { color: MAT.pmma, width: 0 }, objectName: "ПММА" });
    s.addShape(S.RECTANGLE, { x: x0 + 1.56, y: 3.2, w: 0.5, h: 1.3, fill: { color: "9CC9D3" }, line: { color: "9CC9D3", width: 0 }, objectName: "Экспонированная область" });
    s.addShape(S.LINE, { x: x0 + 0.9, y: 3.85, w: 1.8, h: 0, line: { color: HEX.accent1, width: 2.5, endArrowType: "triangle" }, objectName: "Прямой луч" });
    s.addShape(S.LINE, { x: x0 - 0.1, y: 3.6, w: 2.3, h: 1.6, line: { color: "F08080", width: 1.75, dashType: "dash", endArrowType: "triangle" }, objectName: "Рассеянный фотон" });
    s.addNotes("Здравствуйте. Тема доклада — рассеяние синхротронного излучения мембранами масок для рентгенолитографии на станции LIGA ВЭПП-3. Мы построили модель Geant4 экспериментов, сделанных у нас в лаборатории, и сравнили её с экспериментом. План: зачем это нужно, что моделировали, ограничения модели, результаты по материалам, эксперимент и сравнение, выводы и планы.");
  }

  // ================= 2. Мотивация =================
  {
    const s = content(SEC[0], "1 · ПОСТАНОВКА ЗАДАЧИ", "Материал маски влияет на качество структур");
    const items = [
      [I.layers, "Маска — ключевой элемент LIGA", "Рисунок из Au на прозрачной мембране; качество структуры задаёт контраст шаблона — отношение доз под открытыми и затенёнными участками [1, 2]."],
      [I.atom, "Мембрана меняет дозу в резисте", "Толщина, материал и структура мембраны (поры, кристалл, шероховатость) перераспределяют дозу за счёт рассеяния; вторичные процессы ограничивают разрешение [3, 4]."],
      [I.balance, "Выбор материала — компромисс", "Прозрачность против толщины, механической прочности и стабильности размеров: Be, C, Si, полимеры [2]; стеклоуглерод даёт гладкие стенки структур [5]."],
      [I.cube, "Маски делаем сами", "В РФ нет производства масок для глубокой рентгенолитографии, зарубежные — 10–20 тыс. евро [2]; в ИЯФ — маски на стеклоуглероде 450±50 мкм и Ti [2, 7]."],
    ];
    const cw = 3.95, ch = 2.45, gx = 0.3, gy = 0.3;
    items.forEach(([ic, h, b], i) => {
      const x = MX + (i % 2) * (cw + gx), y = TOP + Math.floor(i / 2) * (ch + gy);
      card(s, x, y, cw, ch, { name: `Карточка ${i + 1}` });
      iconCircle(s, x + 0.25, y + 0.25, 0.6, ic, C.accent2, `Иконка ${i + 1}`);
      text(s, h, { x: x + 1.0, y: y + 0.25, w: cw - 1.2, h: 0.65, fontSize: 16, bold: true, color: C.text2, valign: "middle" });
      text(s, b, { x: x + 0.25, y: y + 1.0, w: cw - 0.5, h: ch - 1.15, fontSize: 14 });
    });
    const qx = MX + 2 * cw + gx + 0.4, qw = W - MX - qx;
    s.addShape(S.ROUNDED_RECTANGLE, { x: qx, y: TOP, w: qw, h: 2 * ch + gy, rectRadius: 0.08, fill: { color: C.text2 }, line: { color: C.text2, width: 0 }, objectName: "Вопрос работы" });
    iconCircle(s, qx + 0.3, TOP + 0.35, 0.7, I.question, C.accent1, "Вопрос");
    text(s, "Вопрос работы", { x: qx + 0.3, y: TOP + 1.25, w: qw - 0.6, h: 0.5, fontSize: 20, bold: true, color: C.background1, fontFace: THEME.headFontFace });
    text(s, [
      { text: "Какой вклад в дозу ПММА даёт рассеяние в мембране маски и как он зависит от материала, толщины и положения мембраны?", options: { breakLine: true } },
      { text: " ", options: { breakLine: true, fontSize: 8 } },
      { text: "Модель отрабатываем на мембранах, уже исследованных в лаборатории, — затем даём рекомендации для проектирования масок.", options: { color: "CADCFC" } },
    ], { x: qx + 0.3, y: TOP + 1.85, w: qw - 0.6, h: 3.1, fontSize: 15, color: C.background1 });
    s.addNotes("Почему это важно. LIGA-технология и рентгеновская литография позволяют делать высокоаспектные микроструктуры с субмикронной точностью [1]. Ключевой элемент процесса — рентгеновская маска: рисунок из золота на мембране, прозрачной для излучения. Главная характеристика маски — контраст, то есть отношение доз в резисте под открытыми и под затенёнными участками [2]. Весь пучок проходит через мембрану, поэтому её толщина, материал и структура — поры стеклоуглерода, монокристалличность сапфира, шероховатость и поликристалличность бериллия — влияют на распределение дозы в резисте за счёт рассеяния; вторичные процессы вообще ограничивают разрешение рентгенолитографии [3, 4]. Выбор материала мембраны — компромисс между прозрачностью, толщиной, механической прочностью и стабильностью размеров [2]; стеклоуглерод, например, даёт гладкие стенки структур [5]. И практическая сторона: в России масок для глубокой рентгенолитографии не производят, зарубежные стоят порядка 10–20 тысяч евро, поэтому в ИЯФ маски делают сами — на стеклоуглероде и титане [2, 7]. Значит, нужен обоснованный выбор материала мембраны. Отсюда вопрос работы: какой вклад даёт рассеяние в мембране и как он зависит от материала, толщины и положения мембраны. Модель отрабатываем на мембранах, уже исследованных у нас, чтобы потом давать рекомендации для проектирования масок.");
  }

  // ================= 3. Задача и подход =================
  {
    const s = content(SEC[0], "1 · ПОСТАНОВКА ЗАДАЧИ", "Задача и подход");
    text(s, [
      { text: "Цель: ", options: { bold: true, color: C.accent2 } },
      { text: "количественно определить, какую часть дозы в ПММА формируют фотоны, рассеянные в мембране, и как материал, толщина и положение мембраны меняют дозу у краёв окон шаблона. " },
      { text: "Итог — рекомендации по материалу и толщине мембраны.", options: { bold: true } },
    ], { x: MX, y: TOP - 0.05, w: W - 2 * MX, h: 0.8, fontSize: 15 });
    const steps = [
      ["Эксперименты", "Be, стеклоуглерод, Al₂O₃ (2 положения); ПММА 10⁷ г/моль [8]"],
      ["Модель Geant4", "те же геометрия, фильтры, экспозиции"],
      ["Сравнение", "профили краёв углублений"],
      ["Прогноз", "новые материалы (Ti и др.)"],
    ];
    const sw = 2.95, sy = TOP + 0.85;
    steps.forEach(([h, b], i) => {
      const x = MX + i * (sw + 0.13);
      s.addShape(i === 0 ? S.PENTAGON : S.CHEVRON, { x, y: sy, w: sw, h: 1.2, fill: { color: i === 3 ? C.accent1 : C.text2 }, line: { color: C.background1, width: 0 }, objectName: `Шаг ${i + 1}` });
      text(s, [{ text: h, options: { bold: true, fontSize: 15, breakLine: true } }, { text: b, options: { fontSize: 12 } }],
        { x: x + (i === 0 ? 0.25 : 0.6), y: sy + 0.1, w: sw - (i === 0 ? 0.85 : 1.15), h: 1.0, color: C.background1, valign: "middle" });
    });
    const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } });
    const rows = [
      ["Мембрана", "Положение", "Al-фильтр", "Каптон", "Экспозиция", "Отверстия в Au, мкм", "Статус"].map(hdr),
      ["Be 200 мкм", "вплотную", "800 мкм", "25 мкм", "30 000 мА·мин", "20, 200, 300, 600", "эксперимент"],
      ["Стеклоуглерод 475 мкм", "вплотную", "450 мкм", "25 мкм", "30 000 мА·мин", "15, 129, 300, 600", "эксперимент"],
      ["Лейкосапфир Al₂O₃ 525 мкм", "вплотную", "300 мкм", "20 мкм", "37 000 мА·мин", "20, 60, 105, 300, 600", "эксперимент"],
      ["Лейкосапфир Al₂O₃ 525 мкм", "280 мм до маски", "300 мкм", "25 мкм", "30 000 мА·мин", "20, 60, 105, 300, 600", "эксперимент"],
      ["Ti 2,3 мкм", "вплотную", "450 мкм", "25 мкм", "30 000 мА·мин*", "15, 20, 300, 600", { text: "только расчёт", options: { color: HEX.accent3, bold: true } }],
    ];
    s.addTable(rows, { x: MX, y: TOP + 2.25, w: W - 2 * MX, colW: [2.9, 1.65, 1.15, 1.0, 1.65, 2.2, 1.58], fontSize: 13, fontFace: THEME.bodyFontFace, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "D5DBE3" }, fill: { color: "FFFFFF" }, rowH: 0.38, valign: "middle", objectName: "Таблица конфигураций" });
    text(s, "Общее для всех: Be-окна 500 мкм, 20,3 м до источника, сканирование ±15 мм, шаблон Au 22 мкм на Ti 2,3 мкм, ПММА 15 мкм, He 50 кПа.   * принятая нормировка, опыта нет", { x: MX, y: 6.35, w: W - 2 * MX, h: 0.5, fontSize: 12, color: C.accent4 });
    s.addNotes("Цель работы — количественно определить, какую часть поглощённой дозы в ПММА формируют фотоны, рассеянные в мембране, и как материал, толщина и положение мембраны влияют на дозу у краёв окон шаблона; практический итог — рекомендации по материалу и толщине мембран при проектировании масок. Подход: берём четыре эксперимента, сделанных у нас — бериллий 200 мкм, стеклоуглерод 475, лейкосапфир 525 вплотную к маске и тот же сапфир в 280 мм от маски, — моделируем их в Geant4 с теми же фильтрами и экспозициями, сравниваем с профилями углублений в сверхмолекулярном ПММА [8] и, если модель работает, применяем её к новым материалам и толщинам. Пятый вариант — титан 2,3 мкм — пока только расчётный. Параметры взяты из техзаданий к экспериментам и из «Схем»; все расхождения между документами зафиксированы отдельно.");
  }

  // ================= 4. Пучок =================
  pres.addSection({ title: SEC[1] });
  {
    const s = content(SEC[1], "2 · ЧТО МОДЕЛИРОВАЛИ", "Пучок станции LIGA: что приходит к маске");
    const sp = D.spectrum;
    const series = sp.series.map((x) => ({ name: x.name, labels: sp.energy_keV.map(String), values: x.values }));
    s.addChart(pres.charts.LINE, series, Object.assign({
      x: MX, y: TOP, w: 7.9, h: 5.25, objectName: "Спектр СИ",
      chartColors: ["9AA5B1", "F39C3C", "1F8A9E", "7B5EA7", "0F2B46"], lineSize: 2.25, lineDataSymbol: "none",
      valAxisLogScaleBase: 10, valAxisMinVal: 1e10, valAxisMaxVal: 1e16, valAxisLabelFormatCode: "0E+0",
      catAxisLabelFrequency: 5, showLegend: true, legendPos: "b",
      showValAxisTitle: true, valAxisTitle: "фотоны / (с·мрад·кэВ), 100 мА", showCatAxisTitle: true, catAxisTitle: "энергия фотона, кэВ",
      showTitle: true, title: "Спектр ВЭПП-3 (Швингер) и фильтры станции LIGA [6]", titleFontSize: 14, titleColor: "1B1F2A",
    }, axisStyle(), chartText));
    const sx = MX + 8.3, sw = W - MX - sx;
    const stats = [
      ["2 ГэВ, 2 Тл", "энергия электронов и поле → Eс = 5,3 кэВ"],
      ["20,3 м · ±15 мм", "до образца; вертикальное сканирование"],
      ["≈ 18–20 кэВ", "средняя энергия после Be 500 мкм + Al 300–800 мкм"],
      ["3,12 Вт/см²", "плотность мощности; в диссертации 3,1 Вт/см²"],
    ];
    stats.forEach(([big, small], i) => {
      const y = TOP + i * 1.33;
      card(s, sx, y, sw, 1.18, { name: `Параметр ${i + 1}` });
      text(s, big, { x: sx + 0.25, y: y + 0.12, w: sw - 0.4, h: 0.5, fontSize: 24, bold: true, color: i === 3 ? C.accent2 : C.text2, fontFace: THEME.headFontFace });
      text(s, small, { x: sx + 0.25, y: y + 0.65, w: sw - 0.4, h: 0.45, fontSize: 13, color: "4A5568" });
    });
    s.addNotes("Источник — поворотный магнит ВЭПП-3: 2 ГэВ, 2 Тл, критическая энергия 5,3 кэВ. Спектр считали по формуле Швингера с учётом поляризации. Пучок проходит бериллиевые окна 500 мкм и алюминиевый фильтр 300–800 мкм, поэтому мягкая часть полностью срезается и до маски доходит жёсткий спектр со средней энергией 18–20 кэВ. Это важно для всего дальнейшего: ПММА 15 мкм поглощает такие фотоны слабо, доза почти не меняется по глубине, а золото 22 мкм пропускает заметную долю жёстких фотонов. Нормировку проверили независимо: плотность мощности 3,12 Вт/см² против 3,1 в диссертации Гольденберга, время набора дозы 8,1 мин против 7′45″.");
  }

  // ================= 5. Схема =================
  {
    const s = content(SEC[1], "2 · ЧТО МОДЕЛИРОВАЛИ", "Схема эксперимента в модели");
    const yc = 3.75; // ось пучка
    // источник
    s.addShape(S.OVAL, { x: 0.65, y: yc - 0.42, w: 0.84, h: 0.84, fill: { color: C.text2 }, line: { color: C.text2, width: 0 }, objectName: "Источник" });
    text(s, "e⁻", { x: 0.65, y: yc - 0.42, w: 0.84, h: 0.84, fontSize: 20, bold: true, color: C.background1, align: "center", valign: "middle" });
    text(s, "ВЭПП-3\nповоротный\nмагнит", { x: 0.45, y: yc + 0.55, w: 1.25, h: 0.8, fontSize: 12, align: "center", color: "4A5568" });
    // пучок
    s.addShape(S.RIGHT_ARROW, { x: 1.5, y: yc - 0.3, w: 10.2, h: 0.6, fill: { color: C.accent1, transparency: 72 }, line: { color: C.accent1, width: 0, transparency: 100 }, objectName: "Пучок СИ" });
    text(s, "пучок СИ: полихроматический,\nполяризованный", { x: 2.8, y: yc + 0.4, w: 1.5, h: 0.5, fontSize: 11, italic: true, color: "8A6A10", align: "center" });
    const label = (t, x, y, w, o = {}) => text(s, t, Object.assign({ x, y, w, h: 0.32, fontSize: 13, align: "center" }, o));
    // Be-окна
    s.addShape(S.CUBE, { x: 2.0, y: yc - 0.55, w: 0.75, h: 1.1, fill: { color: MAT.Be }, line: { color: "B86E1F", width: 0.75 }, objectName: "Be-окна" });
    label("Be-окна", 1.7, yc - 1.0, 1.35, { bold: true });
    label("500 мкм\n(100+100+300)", 1.6, yc + 0.65, 1.55, { h: 0.55, fontSize: 12 });
    text(s, "≈ 20 м", { x: 3.25, y: yc - 0.16, w: 1.0, h: 0.32, fontSize: 13, bold: true, align: "center", color: "8A6A10" });
    // Al
    s.addShape(S.CUBE, { x: 4.55, y: yc - 0.55, w: 0.6, h: 1.1, fill: { color: MAT.Al }, line: { color: "9AA1AB", width: 0.75 }, objectName: "Al-фильтр" });
    label("Al-фильтр", 4.2, yc - 1.0, 1.35, { bold: true });
    label("300 / 450 /\n800 мкм", 4.4, yc + 0.65, 1.0, { h: 0.55, fontSize: 12 });
    // 20 см — над пучком
    arrowLine(s, 5.35, yc - 0.6, 7.1, yc - 0.6, { begin: "triangle", width: 1, name: "20 см" });
    label("20 см, He 50 кПа", 5.35, yc - 0.98, 1.75, { fontSize: 12, italic: true });
    // мембрана
    s.addShape(S.CUBE, { x: 7.2, y: yc - 0.7, w: 1.25, h: 1.4, fill: { color: MAT.membrane }, line: { color: "6E4FA0", width: 0.75 }, objectName: "Мембрана" });
    label("Мембрана", 7.0, yc - 1.15, 1.6, { bold: true, color: "5B3E8C" });
    text(s, "Be 200 · стеклоуглерод 475 ·\nAl₂O₃ 525 · Ti 2,3 мкм\n(Al₂O₃ также в 280 мм от маски)", { x: 6.45, y: yc + 0.8, w: 2.55, h: 0.85, fontSize: 12, align: "center", color: "5B3E8C" });
    // шаблон + резист (увеличено)
    const sx = 9.15, sh = 1.4, sy = yc - 0.7;
    const layers = [["Au", "22", MAT.Au, 0.5], ["Ti", "2,3", MAT.Ti, 0.16], ["Каптон", "25", MAT.kapton, 0.3], ["ПММА", "15", MAT.pmma, 0.4]];
    let lx = sx;
    layers.forEach(([n, t, col, w], i) => {
      s.addShape(S.RECTANGLE, { x: lx, y: sy, w, h: sh, fill: { color: col }, line: { color: "FFFFFF", width: 0.5 }, objectName: n });
      const tx = 8.85 + i * 0.7;
      text(s, [{ text: n, options: { bold: true, breakLine: true } }, { text: t + " мкм" }], { x: tx, y: sy - 0.9, w: 0.7, h: 0.5, fontSize: 11, align: "center" });
      s.addShape(S.LINE, { x: Math.min(tx + 0.35, lx + w / 2), y: sy - 0.38, w: Math.max(Math.abs(tx + 0.35 - (lx + w / 2)), 0.001), h: 0.36, flipH: tx + 0.35 > lx + w / 2, line: { color: "6C7A89", width: 0.75 }, objectName: `Выноска ${n}` });
      lx += w;
    });
    s.addShape(S.RECTANGLE, { x: sx, y: yc - 0.18, w: 0.5, h: 0.36, fill: { color: "FFFFFF" }, line: { color: "B8860B", width: 0.5 }, objectName: "Окно в Au" });
    // отверстия — под стопкой
    const holes = [15, 60, 105, 300, 600];
    const hy = sy + sh + 0.25;
    holes.forEach((hh, i) => {
      const bx = 9.0 + i * 0.62, bs = 0.5, inner = 0.08 + 0.32 * Math.sqrt(hh / 600);
      text(s, String(hh), { x: bx - 0.1, y: hy, w: bs + 0.2, h: 0.25, fontSize: 11, align: "center" });
      s.addShape(S.RECTANGLE, { x: bx, y: hy + 0.27, w: bs, h: bs, fill: { color: MAT.Au }, line: { color: "B8860B", width: 0.5 }, objectName: `Окно ${hh} мкм` });
      s.addShape(S.RECTANGLE, { x: bx + (bs - inner) / 2, y: hy + 0.27 + (bs - inner) / 2, w: inner, h: inner, fill: { color: "FFFFFF" }, line: { color: "B8860B", width: 0.5 } });
    });
    text(s, "квадратные окна в Au, мкм", { x: 9.0, y: hy + 0.82, w: 3.0, h: 0.26, fontSize: 11, italic: true, align: "center", color: "4A5568" });
    // сканирование
    arrowLine(s, 11.9, yc - 0.85, 11.9, yc + 0.85, { begin: "triangle", width: 1.5, color: C.text2, name: "Сканирование" });
    text(s, "скани-\nрование\n±15 мм", { x: 12.0, y: yc - 0.45, w: 0.75, h: 0.9, fontSize: 12, color: C.text2 });
    // этапы транспорта
    const by = 6.0;
    s.addShape(S.ROUNDED_RECTANGLE, { x: 1.6, y: by, w: 6.85, h: 0.85, rectRadius: 0.06, fill: { color: C.background2 }, line: { color: "C9D3DE", width: 0.75 }, objectName: "Этап 1" });
    text(s, [{ text: "Этап 1. ", options: { bold: true, color: C.accent2 } }, { text: "источник → Be (аналитически) → Al → (удалённый сапфир) → фазовое пространство перед мембраной/шаблоном; кэшируется для всех окон" }],
      { x: 1.8, y: by + 0.06, w: 6.5, h: 0.73, fontSize: 13, valign: "middle" });
    s.addShape(S.ROUNDED_RECTANGLE, { x: 8.65, y: by, w: W - MX - 8.65, h: 0.85, rectRadius: 0.06, fill: { color: C.background2 }, line: { color: "C9D3DE", width: 0.75 }, objectName: "Этап 2" });
    text(s, [{ text: "Этап 2. ", options: { bold: true, color: C.accent2 } }, { text: "мембрана + шаблон + ПММА; доза на сетке 0,25–5 мкм у края окна" }],
      { x: 8.85, y: by + 0.06, w: W - MX - 9.05, h: 0.73, fontSize: 13, valign: "middle" });
    s.addNotes("Это схема, по которой строится геометрия модели, — она соответствует «Схемам» из лаборатории. Пучок от поворотного магнита проходит бериллиевые окна 500 мкм, примерно через 20 м — алюминиевый фильтр, через 20 см в гелии — исследуемую мембрану, затем шаблон: золото 22 мкм с квадратным окном на титановой основе 2,3 мкм, каптон и ПММА 15 мкм. Окна в золоте от 15 до 600 мкм. Сборка сканируется вертикально на ±15 мм. Расчёт идёт в два этапа: сначала транспорт через фильтры до плоскости перед мембраной — он общий для всех отверстий и кэшируется; затем подробный транспорт в локальной стопке с регистрацией дозы на сетке до 0,25 мкм у края окна. Для варианта с сапфиром в 280 мм сапфир входит в первый этап.");
  }

  // ================= 6. Что считаем =================
  {
    const s = content(SEC[1], "2 · ЧТО МОДЕЛИРОВАЛИ", "Что считаем: откуда берётся доза в ПММА");
    const y0 = TOP + 0.35, y1 = 6.55, hy0 = 3.55, hy1 = 4.55;
    const xm = 1.35, wm = 1.3, xa = 3.55, wa = 0.45, xt = xa + wa, wt = 0.12, xk = xt + wt, wk = 0.3, xp = xk + wk, wp = 0.75;
    s.addShape(S.RECTANGLE, { x: xm, y: y0, w: wm, h: y1 - y0, fill: { color: MAT.membrane, transparency: 35 }, line: { color: MAT.membrane, width: 0 }, objectName: "Мембрана (сечение)" });
    s.addShape(S.RECTANGLE, { x: xa, y: y0, w: wa, h: hy0 - y0, fill: { color: MAT.Au }, line: { color: MAT.Au, width: 0 }, objectName: "Au верх (сечение)" });
    s.addShape(S.RECTANGLE, { x: xa, y: hy1, w: wa, h: y1 - hy1, fill: { color: MAT.Au }, line: { color: MAT.Au, width: 0 }, objectName: "Au низ (сечение)" });
    s.addShape(S.RECTANGLE, { x: xt, y: y0, w: wt, h: y1 - y0, fill: { color: MAT.Ti }, line: { color: MAT.Ti, width: 0 }, objectName: "Ti (сечение)" });
    s.addShape(S.RECTANGLE, { x: xk, y: y0, w: wk, h: y1 - y0, fill: { color: MAT.kapton }, line: { color: MAT.kapton, width: 0 }, objectName: "Каптон (сечение)" });
    s.addShape(S.RECTANGLE, { x: xp, y: y0, w: wp, h: y1 - y0, fill: { color: MAT.pmma }, line: { color: MAT.pmma, width: 0 }, objectName: "ПММА (сечение)" });
    [["мембрана", xm, wm], ["Au", xa, wa], ["Ti", xt - 0.1, wt + 0.2], ["каптон", xk - 0.2, wk + 0.4], ["ПММА", xp, wp]].forEach(([t, x, w], i) =>
      text(s, t, { x: x - 0.1, y: y0 - (i % 2 ? 0.55 : 0.3), w: w + 0.2, h: 0.26, fontSize: 11, bold: true, align: "center" }));
    // падающий пучок
    [2.25, 3.0, 3.85, 4.25, 5.6].forEach((y, i) => arrowLine(s, 0.6, y, xm - 0.05, y, { color: HEX.accent1, width: 2.25, name: `Падающий фотон ${i + 1}` }));
    // прямой через окно
    arrowLine(s, xm + wm, 4.05, xp + wp - 0.1, 4.05, { color: HEX.accent1, width: 2.5, name: "Прямой фотон через окно" });
    // поглощён золотом
    arrowLine(s, xm + wm, 2.25, xa - 0.02, 2.25, { color: HEX.accent1, width: 2, end: "oval", name: "Поглощён в Au" });
    // рассеяние в мембране → тень
    arrowLine(s, xm + 0.75, 3.0, xp + 0.45, 5.35, { color: "C8463D", width: 2, dash: "dash", name: "Рассеяние в мембране" });
    s.addShape(S.OVAL, { x: xm + 0.68, y: 2.93, w: 0.14, h: 0.14, fill: { color: "C8463D" }, line: { color: "C8463D", width: 0 } });
    // флуоресценция Au
    arrowLine(s, xa + 0.25, 5.6, xp + 0.5, 6.25, { color: "8A5A00", width: 1.75, dash: "sysDot", name: "Флуоресценция Au/Ti" });
    s.addShape(S.OVAL, { x: xa + 0.18, y: 5.53, w: 0.14, h: 0.14, fill: { color: "8A5A00" }, line: { color: "8A5A00", width: 0 } });
    // фотоэлектрон в ПММА у края
    arrowLine(s, xp + 0.2, 4.15, xp + 0.55, 4.75, { color: "FFFFFF", width: 1.5, name: "Фотоэлектрон" });
    // области
    const rx = xp + wp + 0.12;
    [["тень", y0, hy0 - 0.05], ["открыто", hy0 + 0.05, hy1 - 0.05], ["тень", hy1 + 0.05, y1]].forEach(([t, a, b], i) => {
      s.addShape(S.RIGHT_BRACKET, { x: rx, y: a, w: 0.12, h: b - a, line: { color: "4A5568", width: 1 }, objectName: `Скобка ${t} ${i}` });
      text(s, t, { x: rx + 0.18, y: (a + b) / 2 - 0.15, w: 0.85, h: 0.3, fontSize: 12, color: "4A5568" });
    });
    // легенда механизмов
    const lx = 7.0, lw = W - MX - lx;
    const leg = [
      [HEX.accent1, "solid", "прямые фотоны: доза под окном"],
      ["C8463D", "dash", "рассеяние в мембране (рэлей, комптон) — главный объект"],
      ["8A5A00", "sysDot", "флуоресценция шаблона: Au L 9,7–11,4 кэВ, Ti K 4,5 кэВ"],
      [HEX.dk2, "solid", "фото-, оже-электроны: пробег до ~7 мкм в ПММА"],
    ];
    text(s, "Механизмы", { x: lx, y: TOP + 0.05, w: lw, h: 0.35, fontSize: 16, bold: true, color: C.text2 });
    leg.forEach(([col, dash, t], i) => {
      const y = TOP + 0.6 + i * 0.52;
      s.addShape(S.LINE, { x: lx, y: y + 0.15, w: 0.6, h: 0, line: { color: col, width: 2.25, dashType: dash } });
      text(s, t, { x: lx + 0.8, y, w: lw - 0.8, h: 0.4, fontSize: 14, valign: "middle" });
    });
    card(s, lx, 4.3, lw, 2.3, { name: "Классификация историй" });
    text(s, [
      { text: "Классификация историй", options: { bold: true, color: C.text2, fontSize: 16, breakLine: true } },
      { text: "Каждый трек несёт битовую маску «где и как рассеивался»; вторичные частицы наследуют её. Энерговыделение раскладывается на 9 непересекающихся категорий (сумма = полная доза).", options: { breakLine: true } },
      { text: " ", options: { fontSize: 6, breakLine: true } },
      { text: "f", options: { bold: true, italic: true } }, { text: "мембр", options: { bold: true, subscript: true } },
      { text: " = доля дозы от историй с рассеянием в мембране; «тень» — под Au дальше 20 мкм от края." },
    ], { x: lx + 0.25, y: 4.42, w: lw - 0.5, h: 2.1, fontSize: 14 });
    s.addNotes("Что именно считаем. Слева — сечение у края окна. Прямые фотоны проходят через окно и создают основную дозу. Часть фотонов рассеивается в мембране — рэлеевски или комптоновски — и может попасть в ПММА под золотом; это и есть основной объект исследования. Но есть конкуренты: золото и титан при поглощении жёстких фотонов испускают флуоресценцию, а фото- и оже-электроны размазывают энергию на несколько микрон. Чтобы разделить эти вклады, каждая история в Geant4 несёт маску, где и как фотон рассеивался, вторичные частицы её наследуют. В итоге доза раскладывается на непересекающиеся категории, и мы получаем долю дозы от историй с рассеянием в мембране отдельно для открытой области и для тени.");
  }

  // ================= 7. Модель Geant4 =================
  {
    const s = content(SEC[1], "2 · ЧТО МОДЕЛИРОВАЛИ", "Модель Geant4: физика, ускорения, проверка");
    const cw = 3.85, ch = 5.15;
    const cols = [
      [I.atom, "Физика", [
        "Livermore (EPDL/EEDL/EADL): фотоэффект, рэлей, комптон с доплеровским уширением",
        "атомная релаксация: флуоресценция и оже-каскад",
        "поляризация СИ (89 % σ); контроль: Penelope, option4",
        "пороги рождения 0,3–1 мкм (до 100 эВ)",
      ]],
      [I.cogs, "Ускорения", [
        "двухэтапный транспорт с кэшем фазового пространства",
        "принудительное взаимодействие в ПММА, мембране, каптоне — выигрыш ×150",
        "выборка по значимости у края окна",
        "отсечение электронов, не достающих до ПММА; многопоточность",
      ]],
    ];
    cols.forEach(([ic, h, items], i) => {
      const x = MX + i * (cw + 0.3);
      card(s, x, TOP, cw, ch, { name: h });
      iconCircle(s, x + 0.25, TOP + 0.25, 0.6, ic, C.accent2, h);
      text(s, h, { x: x + 1.0, y: TOP + 0.3, w: cw - 1.2, h: 0.5, fontSize: 18, bold: true, color: C.text2, valign: "middle" });
      text(s, items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1, paraSpaceAfter: 8 } })),
        { x: x + 0.25, y: TOP + 1.05, w: cw - 0.5, h: ch - 1.25, fontSize: 14 });
    });
    const vx = MX + 2 * (cw + 0.3), vw = W - MX - vx;
    text(s, "Проверки", { x: vx, y: TOP, w: vw, h: 0.4, fontSize: 18, bold: true, color: C.text2 });
    const checks = [
      ["≤ 4,8 %", "μ Geant4 против NIST XCOM, 5–30 кэВ, все материалы"],
      ["0,5–4 %", "поток и время экспозиции против диссертации"],
      ["≤ 2 %", "разброс дозы между моделями ЭМ-физики"],
      ["36 / 0", "автоматических проверок / провалов"],
    ];
    checks.forEach(([b, t], i) => {
      const y = TOP + 0.55 + i * 1.15;
      text(s, b, { x: vx, y, w: 1.9, h: 0.6, fontSize: 28, bold: true, color: C.accent2, fontFace: THEME.headFontFace, valign: "middle" });
      text(s, t, { x: vx + 2.0, y, w: vw - 2.0, h: 0.95, fontSize: 14, valign: "middle" });
    });
    s.addNotes("Физика — пакет Livermore: фотоэффект, рэлеевское и комптоновское рассеяние, атомная релаксация с флуоресценцией и оже-электронами. Поляризацию СИ генератор учитывает; для контроля сравнивали с Penelope и Standard option4 — разброс дозы не больше 2 %. Поскольку ПММА поглощает лишь доли процента фотонов, прямой расчёт неэффективен; поэтому используем двухэтапный транспорт, принудительное взаимодействие — оно даёт выигрыш эффективности примерно в 150 раз и проверено на несмещённость, — выборку по значимости у края и отсечение электронов. Все ускорения проверены сравнением с аналоговым расчётом. Коэффициенты ослабления Geant4 совпадают с NIST в пределах 4,8 %, нормировка — с диссертацией в пределах 0,5–4 %. Автоматическая валидация: 36 проверок, провалов нет.");
  }

  // ================= 8. Ограничения: материалы =================
  pres.addSection({ title: SEC[2] });
  {
    const s = content(SEC[2], "3 · ОГРАНИЧЕНИЯ МОДЕЛИ", "Чего нет в модели материалов");
    const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } });
    const no = { text: "нет", options: { bold: true, color: HEX.accent3 } };
    const part = (t) => ({ text: t, options: { bold: true, color: "B7791F" } });
    const rows = [
      [hdr("Эффект"), hdr("Учтён?"), hdr("Что это может изменить")],
      ["Монокристалличность Al₂O₃: брэгговская дифракция", no, "рефлексы под большими углами — дополнительная «рассеянная» доза; ориентация кристалла неизвестна, Geant4 этого не умеет"],
      ["Поликристалличность Be, Ti: зёрна, текстура", no, "когерентное рассеяние перераспределяется в кольца Дебая–Шеррера; в модели — свободные атомы"],
      ["Поры стеклоуглерода, границы зёрен Be (SAXS)", no, "углы ~мрад → смещение ~0,5 мкм на толщине мембраны — меньше пробега электронов"],
      ["Шероховатость, разнотолщинность мембран", no, "локальные вариации пропускания"],
      ["Подложка ПММА, зазоры, ориентация шаблона", part("параметры есть"), "подложка — рост дозы у дна; прогоны чувствительности ещё не сделаны"],
      ["Проявление ПММА (кинетика R(D))", part("феноменологически"), "доза ≠ рельеф; без калибровки R(D) — только качественное сравнение"],
    ];
    s.addTable(rows, { x: MX, y: TOP, w: 8.6, colW: [2.85, 1.95, 3.8], fontSize: 13, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "D5DBE3" }, fill: { color: "FFFFFF" }, valign: "middle", rowH: 0.62, objectName: "Таблица ограничений" });
    const qx = MX + 8.95, qw = W - MX - qx;
    card(s, qx, TOP, qw, 5.0, { name: "Следствие" });
    iconCircle(s, qx + 0.3, TOP + 0.3, 0.65, I.warn, C.accent3, "Внимание");
    text(s, "Что это значит для результатов", { x: qx + 0.3, y: TOP + 1.1, w: qw - 0.6, h: 0.75, fontSize: 16, bold: true, color: C.text2 });
    text(s, [
      { text: "Все мембраны описаны как однородные аморфные слои с табличной плотностью.", options: { breakLine: true } },
      { text: " ", options: { fontSize: 6, breakLine: true } },
      { text: "Для лейкосапфира вклад рассеяния — оценка снизу: брэгговские рефлексы монокристалла нужно оценить отдельно.", options: { bold: true } },
    ], { x: qx + 0.3, y: TOP + 1.9, w: qw - 0.6, h: 2.9, fontSize: 14 });
    s.addNotes("Ограничения модели я ставлю до результатов, чтобы было понятно, к чему относятся числа. Geant4 описывает мембраны как однородные аморфные слои с табличной плотностью и атомными сечениями свободных атомов. Не учтены: монокристалличность сапфира и брэгговская дифракция; поликристалличность бериллия и титана — зёрна и текстура, когерентное рассеяние в реальности собирается в кольца Дебая–Шеррера; малоугловое рассеяние на порах стеклоуглерода — оно сместит фотоны на доли микрона, это меньше пробега электронов; шероховатость. Подложка, зазоры и ориентация шаблона — параметры в модели есть, но прогоны чувствительности ещё не сделаны. Проявление ПММА описано только феноменологически. Главное следствие: для сапфира наш вклад рассеяния — скорее оценка снизу.");
  }

  // ================= 9. Ограничения: частицы vs волны =================
  {
    const s = content(SEC[2], "3 · ОГРАНИЧЕНИЯ МОДЕЛИ", "Частицы вместо волн: что теряем и что получаем");
    const cw = 4.4, ch = 4.0, y = TOP;
    const cols = [
      [I.approx, C.accent3, "Теряем (волновые эффекты)", [
        "френелевскую дифракцию на краю окна Au",
        "интерференцию когерентного рассеяния: брэгговские рефлексы, кольца Дебая–Шеррера, SAXS",
        "фазовый контраст на границах слоёв",
        "частичную когерентность пучка СИ",
      ]],
      [I.check, C.accent2, "Получаем (Geant4)", [
        "полный каскад: фото-, оже-, комптон-электроны, флуоресценция Au L и Ti K",
        "3D-транспорт в многослойной стопке, любая геометрия",
        "абсолютную дозу (Дж/см³) и её разложение по историям",
        "полихроматический спектр и поляризацию СИ",
      ]],
    ];
    cols.forEach(([ic, col, h, items], i) => {
      const x = MX + i * (cw + 0.3);
      card(s, x, y, cw, ch, { name: h });
      iconCircle(s, x + 0.25, y + 0.25, 0.6, ic, col, h);
      text(s, h, { x: x + 1.0, y: y + 0.3, w: cw - 1.2, h: 0.5, fontSize: 18, bold: true, color: C.text2, valign: "middle" });
      text(s, items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1, paraSpaceAfter: 8 } })),
        { x: x + 0.25, y: y + 1.05, w: cw - 0.5, h: ch - 1.2, fontSize: 14 });
    });
    const qx = MX + 2 * (cw + 0.3), qw = W - MX - qx;
    s.addShape(S.ROUNDED_RECTANGLE, { x: qx, y, w: qw, h: ch, rectRadius: 0.08, fill: { color: C.text2 }, line: { color: C.text2, width: 0 }, objectName: "Оценка Френеля" });
    text(s, "Почему частиц достаточно", { x: qx + 0.3, y: y + 0.3, w: qw - 0.6, h: 0.4, fontSize: 16, bold: true, color: C.accent1 });
    text(s, "√(λz) ≈\n0,05 мкм", { x: qx + 0.3, y: y + 0.8, w: qw - 0.6, h: 0.95, fontSize: 22, bold: true, color: C.background1, fontFace: THEME.headFontFace });
    text(s, `зона Френеля при 20 кэВ (λ = 0,062 нм) и z ≈ 42 мкм от Au до дна ПММА — в 100 раз меньше ширины края по дозе (${range(wMin, wMax)} мкм) и пробега фотоэлектронов (до 7 мкм).`,
      { x: qx + 0.3, y: y + 1.85, w: qw - 0.6, h: 2.1, fontSize: 13, color: "CADCFC" });
    card(s, MX, y + ch + 0.3, W - 2 * MX, 0.95, { fill: "FDF3DC", line: "F2D08A", name: "Вывод" });
    text(s, [{ text: "Итог: ", options: { bold: true } }, { text: "для края окна волновые эффекты пренебрежимы; существенны они только внутри кристаллических и пористых мембран — это оцениваем отдельно (брэгг, SAXS)." }],
      { x: MX + 0.3, y: y + ch + 0.4, w: W - 2 * MX - 0.6, h: 0.75, fontSize: 15, valign: "middle" });
    s.addNotes(`Второе принципиальное ограничение — Geant4 корпускулярный: фотон — частица, фаз нет. Мы теряем френелевскую дифракцию на краю окна, интерференцию когерентного рассеяния — брэгговские рефлексы, кольца, малоугловое рассеяние — и фазовый контраст. Зато получаем то, чего волновой подход не даёт: полный каскад вторичных электронов и флуоресценции, трёхмерный транспорт в многослойной стопке, абсолютную дозу и её разложение по механизмам. Оценка справа показывает, почему для края этого достаточно: ширина зоны Френеля при 20 кэВ на расстоянии 42 мкм — около 0,05 мкм, а ширина дозового края в модели ${range(wMin, wMax)} мкм; её задают электроны. Волновые эффекты существенны только внутри кристаллических и пористых мембран, их надо оценивать отдельно.`);
  }

  // ================= 10. Вклад рассеяния =================
  pres.addSection({ title: SEC[3] });
  {
    const c = D.configs;
    const s = content(SEC[3], "4 · СРАВНЕНИЕ МАТЕРИАЛОВ", "Вклад рассеяния в мембране: сапфир вплотную — лидер");
    const labels = c.map((x) => x.label).reverse();
    s.addChart(pres.charts.BAR, [
      { name: "под окном (открыто)", labels, values: c.map((x) => +x.membrane_open_pct.toFixed(2)).reverse() },
      { name: "под золотом (тень)", labels, values: c.map((x) => +x.membrane_shadow_pct.toFixed(2)).reverse() },
    ], Object.assign({
      x: MX, y: TOP, w: 8.2, h: 5.0, barDir: "bar", barGrouping: "clustered", barGapWidthPct: 60, objectName: "Доля рассеяния по материалам",
      chartColors: ["9CC9D3", "0F2B46"], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#",
      showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisLabelFormatCode: "0",
      showValAxisTitle: true, valAxisTitle: "доля дозы от историй с рассеянием в мембране, %",
      showTitle: true, title: `f мембр, %: окно ${c[0].hole_um.toFixed(0)} мкм`, titleFontSize: 14, titleColor: "1B1F2A",
    }, axisStyle(), chartText));
    const sc = cfg.sapphire_contact, sf = cfg.sapphire_280mm;
    const others = ["be_200", "carbon_475", "titanium_model"].map((k) => cfg[k]);
    const othOpen = Math.max(...others.map((x) => x.membrane_open_pct)), othShadow = Math.max(...others.map((x) => x.membrane_shadow_pct));
    const ratio = Math.round(sc.membrane_shadow_pct / sf.membrane_shadow_pct);
    const sx = MX + 8.6, sw = W - MX - sx;
    const callouts = [
      [`${fmt(sc.membrane_open_pct)} / ${fmt(sc.membrane_shadow_pct)} %`, "Al₂O₃ 525 мкм вплотную: открыто / тень", C.accent3],
      [`×${ratio}`, "меньше в тени, если тот же сапфир отнести на 280 мм", C.accent2],
      [`< ${Math.ceil(othOpen)} %`, `открыто для Be, стеклоуглерода и Ti; в тени < ${Math.ceil(othShadow)} %`, C.text2],
    ];
    callouts.forEach(([b, t, col], i) => {
      const y = TOP + i * 1.62;
      card(s, sx, y, sw, 1.45, { name: `Вывод ${i + 1}` });
      text(s, b, { x: sx + 0.25, y: y + 0.15, w: sw - 0.4, h: 0.6, fontSize: 28, bold: true, color: col, fontFace: THEME.headFontFace });
      text(s, t, { x: sx + 0.25, y: y + 0.78, w: sw - 0.4, h: 0.6, fontSize: 13, color: "4A5568" });
    });
    text(s, `Профиль ${c[0].profile}: ${(c[0].n_histories / 1e6).toFixed(0)}·10⁶ историй на окно; доза за экспозицию опыта; f — доля энерговыделения историй с рассеянием в мембране.`,
      { x: MX, y: 6.6, w: W - 2 * MX, h: 0.35, fontSize: 11, color: C.accent4 });
    s.addNotes(`Главный результат по материалам — для окна ${c[0].hole_um.toFixed(0)} мкм, оно есть во всех опытах. По горизонтали — доля дозы, которую дают истории с рассеянием в мембране, отдельно под окном и под золотом. Под окном рассеяние добавляет мало: меньше ${Math.ceil(othOpen)} % у бериллия, стеклоуглерода и титана. В тени — там, где доза должна быть минимальной, — его доля выше, потому что прямой дозы там мало. Явный лидер — лейкосапфир вплотную к маске: ${fmt(sc.membrane_open_pct)} % под окном и ${fmt(sc.membrane_shadow_pct)} % в тени. Если тот же сапфир отнести на 280 мм, вклад в тени падает примерно в ${ratio} раз. Статистика — профиль quick, 2 млн историй на окно.`);
  }

  // ================= 10b. Зависимость от размера окна =================
  {
    const s = content(SEC[3], "4 · СРАВНЕНИЕ МАТЕРИАЛОВ", "Чем больше окно, тем больше вклад рассеяния");
    const holes = [...new Set(RA.map((r) => r.hole_um))].sort((a, b) => a - b);
    const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 }, align: "center" } });
    const maxSh = Math.max(...RA.map((r) => r.membrane_shadow_pct));
    const heat = (v) => {
      const t = Math.min(1, Math.sqrt(v / maxSh));
      const mix = (a, b) => Math.round(a + (b - a) * t).toString(16).padStart(2, "0");
      return (mix(0xff, 0xe6) + mix(0xff, 0x8f) + mix(0xff, 0xb8)).toUpperCase();
    };
    const rows = [[hdr("Мембрана  \\  окно, мкм"), ...holes.map((h) => hdr(String(h)))]];
    D.configs.forEach((c) => {
      const row = [{ text: c.label, options: { bold: true } }];
      holes.forEach((h) => {
        const r = RA.find((x) => x.key === c.key && x.hole_um === h);
        row.push(r ? { text: `${fmt(r.membrane_open_pct, 2)} / ${fmt(r.membrane_shadow_pct, 2)}`, options: { fill: { color: heat(r.membrane_shadow_pct) }, align: "center" } }
                   : { text: "—", options: { color: "A0AEC0", align: "center" } });
      });
      rows.push(row);
    });
    const tw = W - 2 * MX, c0 = 2.6;
    s.addTable(rows, { x: MX, y: TOP, w: tw, colW: [c0, ...holes.map(() => (tw - c0) / holes.length)], fontSize: 13, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "D5DBE3" }, fill: { color: "FFFFFF" }, valign: "middle", rowH: 0.48, objectName: "f мембр по окнам" });
    text(s, "f мембр, %: под окном / в тени; цвет — доля в тени", { x: MX, y: TOP + 0.48 * 6 + 0.08, w: tw, h: 0.3, fontSize: 11, color: C.accent4 });
    const pick = (k) => RA.filter((r) => r.key === k);
    const sc = pick("sapphire_contact"), cc = pick("carbon_475"), sf = pick("sapphire_280mm");
    const first = (a) => a[0], last = (a) => a[a.length - 1];
    const cards = [
      [I.expand, "Почему растёт", `В точку под окном рассеянные фотоны приходят из конуса, который «вырезает» окно в золоте: шире окно — больше площадь мембраны, видимая из ПММА. Al₂O₃ вплотную: ${fmt(first(sc).membrane_open_pct)} → ${fmt(last(sc).membrane_open_pct)} % под окном (${first(sc).hole_um}→${last(sc).hole_um} мкм); стеклоуглерод: ${fmt(first(cc).membrane_open_pct, 2)} → ${fmt(last(cc).membrane_open_pct)} %.`],
      [I.ruler, "Почему не растёт в 280 мм", `Рассеянные фотоны от удалённого сапфира приходят к маске почти равномерным фоном — окно их не «собирает»: ${fmt(Math.min(...sf.map((r) => r.membrane_open_pct)), 2)}–${fmt(Math.max(...sf.map((r) => r.membrane_open_pct)), 2)} % при любом размере окна.`],
    ];
    const cw = (tw - 0.3) / 2, cy = TOP + 0.48 * 6 + 0.5;
    cards.forEach(([ic, h, b], i) => {
      const x = MX + i * (cw + 0.3);
      card(s, x, cy, cw, 6.85 - cy, { name: h });
      iconCircle(s, x + 0.2, cy + 0.2, 0.55, ic, C.accent2, h);
      text(s, h, { x: x + 0.9, y: cy + 0.2, w: cw - 1.05, h: 0.55, fontSize: 16, bold: true, color: C.text2, valign: "middle" });
      text(s, b, { x: x + 0.2, y: cy + 0.85, w: cw - 0.4, h: 6.85 - cy - 0.95, fontSize: 14 });
    });
    s.addNotes(`После полного прогона у нас есть все 22 окна. В таблице — доля дозы от историй с рассеянием в мембране: первое число под окном, второе в тени; цвет — величина в тени. Видна закономерность: чем больше окно, тем больше вклад рассеяния. Объяснение геометрическое: в точку ПММА под окном рассеянные фотоны приходят из конуса, ограниченного краями окна в золоте; чем шире окно, тем большая площадь мембраны «видна» из ПММА. У сапфира вплотную вклад под окном растёт от ${fmt(first(sc).membrane_open_pct)} до ${fmt(last(sc).membrane_open_pct)} %, у стеклоуглерода — от ${fmt(first(cc).membrane_open_pct, 2)} до ${fmt(last(cc).membrane_open_pct)} %. Для сапфира в 280 мм зависимости нет: рассеянные фотоны приходят к маске почти равномерным фоном, и доля остаётся на уровне десятых процента. Практический вывод: для крупных окон требования к мембране жёстче.`);
  }

  // ================= 11. Почему так =================
  {
    const s = content(SEC[3], "4 · СРАВНЕНИЕ МАТЕРИАЛОВ", "Почему так: масса, состав и расстояние");
    const why = D.why_20keV;
    const name = { be_200: "Be 200 мкм", carbon_475: "Стеклоуглерод 475 мкм", sapphire_contact: "Al₂O₃ 525 мкм", titanium_model: "Ti 2,3 мкм" };
    const labels = why.map((w) => name[w.key]).reverse();
    s.addChart(pres.charts.BAR, [
      { name: "рэлеевское", labels, values: why.map((w) => +w.p_rayleigh_pct.toFixed(2)).reverse() },
      { name: "комптоновское", labels, values: why.map((w) => +w.p_compton_pct.toFixed(2)).reverse() },
    ], Object.assign({
      x: MX, y: TOP, w: 6.0, h: 2.85, barDir: "bar", barGrouping: "stacked", barGapWidthPct: 50, objectName: "Вероятность рассеяния 20 кэВ",
      chartColors: ["B8327A", "E68FB8"], showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisLabelFormatCode: "0",
      showTitle: true, title: "Вероятность рассеяния фотона 20 кэВ в мембране, %", titleFontSize: 13, titleColor: "1B1F2A",
    }, axisStyle(), chartText));
    const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } });
    const rows = [[hdr("Мембрана"), hdr("ρd, мг/см²"), hdr("T(20 кэВ)"), hdr("P расс."), hdr("f мембр, тень")]];
    why.forEach((w) => rows.push([name[w.key], fmt(w.mass_thickness_mg_cm2, w.mass_thickness_mg_cm2 < 10 ? 1 : 0), `${fmt(w.transmission_pct, 0)} %`,
      `${fmt(w.p_rayleigh_pct + w.p_compton_pct, 2)} %`, `${fmt(cfg[w.key].membrane_shadow_pct, 2)} %`]));
    s.addTable(rows, { x: MX + 6.3, y: TOP + 0.1, w: W - 2 * MX - 6.3, colW: [1.95, 0.98, 0.95, 0.98, 0.97], fontSize: 13, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "D5DBE3" }, fill: { color: "FFFFFF" }, valign: "middle", rowH: 0.42, align: "center", objectName: "Таблица материалов" });
    const scc = cfg.sapphire_contact.shadow_categories_pct;
    const ray = scc.membrane_rayleigh_only, comp = scc.membrane_compton;
    const exps = [
      [I.weight, "Масса на пути пучка", "Сапфир 209 мг/см² — в 3–6 раз больше Be и стеклоуглерода; Ti 2,3 мкм — всего 1 мг/см². Вероятность рассеяния ∝ ρd."],
      [I.atom, "Z и рэлеевское рассеяние", `У Al₂O₃ (Z = 8, 13) рэлей — половина рассеяния; он направлен вперёд и доходит до края окна: в тени ${fmt(ray)} % из ${fmt(ray + comp)} % «мембранных».`],
      [I.expand, "Расстояние до маски", "В 280 мм рассеянные фотоны расходятся по площади ~(L·θ)² — до окрестности окна доходит в десятки раз меньше."],
    ];
    const ew = (W - 2 * MX - 0.6) / 3;
    exps.forEach(([ic, h, b], i) => {
      const x = MX + i * (ew + 0.3), y = 4.65;
      card(s, x, y, ew, 2.05, { name: h });
      iconCircle(s, x + 0.2, y + 0.2, 0.55, ic, C.accent2, h);
      text(s, h, { x: x + 0.9, y: y + 0.2, w: ew - 1.05, h: 0.55, fontSize: 15, bold: true, color: C.text2, valign: "middle" });
      text(s, b, { x: x + 0.2, y: y + 0.85, w: ew - 0.4, h: 1.15, fontSize: 13 });
    });
    s.addNotes(`Почему сапфир выделяется. Первая причина — масса на пути пучка: у сапфира 525 мкм поверхностная плотность 209 мг/см², у бериллия 37, у стеклоуглерода 71, у титановой плёнки — 1. Вероятность рассеяния пропорциональна этой величине и сечению: при 20 кэВ фотон рассеивается в сапфире с вероятностью около 6 %, в бериллии — меньше 1 %. Вторая причина — состав: у сапфира кислород и алюминий, рэлеевское сечение растёт примерно как Z², и у сапфира рэлей даёт половину рассеяния. Рэлеевское рассеяние направлено вперёд под малыми углами, поэтому такие фотоны доходят до ПММА рядом с краем окна — в тени у сапфира рэлей даёт ${fmt(ray)} % из ${fmt(ray + comp)} % «мембранного» вклада. Третья причина — расстояние: если мембрана в 280 мм от маски, рассеянные фотоны расходятся по большой площади, и до окрестности окна доходит в десятки раз меньше. Отдельно: сапфир пропускает лишь около 60 % при 20 кэВ, то есть ещё и заметно снижает полезную дозу. Поскольку вклад пропорционален ρd, толщину мембраны можно подбирать под допустимый уровень рассеяния — это следующий шаг моделирования.`);
  }

  // ================= 12. Доза в тени =================
  {
    const s = content(SEC[3], "4 · СРАВНЕНИЕ МАТЕРИАЛОВ", "Доза под золотом создаёт в основном сам шаблон");
    const labels = D.configs.map((x) => x.label).reverse();
    const series = D.categories.map((cat) => ({ name: cat.label, labels, values: D.configs.map((x) => +x.shadow_categories_pct[cat.key].toFixed(2)).reverse() }));
    s.addChart(pres.charts.BAR, series, Object.assign({
      x: MX, y: TOP, w: 7.4, h: 4.6, barDir: "bar", barGrouping: "percentStacked", barGapWidthPct: 45, objectName: "Разложение дозы в тени",
      chartColors: D.categories.map((cat) => CAT_COLOR[cat.key]), showLegend: true, legendPos: "b", legendFontSize: 11,
      valAxisLabelFormatCode: "0%", showTitle: true, title: `Разложение дозы в тени по историям, окно ${D.configs[0].hole_um.toFixed(0)} мкм`, titleFontSize: 14, titleColor: "1B1F2A",
    }, axisStyle(), chartText));
    const scfg = cfg.sapphire_contact;
    const pic = path.join(RES, "runs", "sapphire_contact", `hole_${scfg.hole_um.toFixed(0)}um_${scfg.profile}`, "analysis", "edge_profile_categories.png");
    if (fs.existsSync(pic)) {
      const sz = await imgSize(pic);
      const pw = W - MX - (MX + 7.7), ph = pw * sz.h / sz.w;
      s.addImage({ path: pic, x: MX + 7.7, y: TOP, w: pw, h: ph, objectName: "Профиль дозы у края, сапфир вплотную" });
      text(s, `Профиль дозы поперёк края, Al₂O₃ вплотную, окно ${scfg.hole_um.toFixed(0)} мкм (лог. шкала)`, { x: MX + 7.7, y: TOP + ph + 0.05, w: pw, h: 0.4, fontSize: 11, color: C.accent4 });
    }
    const ext = D.configs.map((x) => x.shadow_categories_pct.external_secondary);
    const extR = `${Math.round(Math.min(...ext))}–${Math.round(Math.max(...ext))}`;
    const direct = D.configs.map((x) => x.shadow_categories_pct.direct);
    card(s, MX, 6.25, W - 2 * MX, 0.7, { fill: "FDF3DC", line: "F2D08A", name: "Вывод" });
    text(s, [
      { text: `Вторичное излучение шаблона — ${extR} % дозы в тени`, options: { bold: true } },
      { text: ` (Au L, Ti K, фотоэлектроны каптона); ширина края ${range(wMin, wMax)} мкм ≈ пробег фотоэлектронов, а не рассеяние в мембране.` },
    ], { x: MX + 0.25, y: 6.3, w: W - 2 * MX - 0.5, h: 0.6, fontSize: 14, valign: "middle" });
    s.addNotes(`Важный побочный результат: откуда вообще берётся доза под золотом. ${Math.round(Math.min(...direct))}–${Math.round(Math.max(...direct))} % — прямые жёсткие фотоны, прошедшие через 22 мкм золота: при 20–30 кэВ золото пропускает от 3 до 30 %. Ещё ${extR} % — вторичное излучение самого шаблона: L-флуоресценция золота, K-флуоресценция титана, фотоэлектроны каптона. Рассеяние в мембране даже у сапфира — несколько процентов. Справа — профиль дозы поперёк края для сапфира вплотную: полная доза падает примерно в ${Math.round(scfg.dose_open / scfg.dose_shadow)} раз на нескольких микронах, вклад мембраны на порядок ниже флуоресценции. Ширина края ${range(wMin, wMax)} мкм определяется пробегом фотоэлектронов, а не рассеянием в мембране.`);
  }

  // ================= 13. Эксперимент =================
  pres.addSection({ title: SEC[4] });
  {
    const s = content(SEC[4], "5 · ЭКСПЕРИМЕНТ", "Эксперимент: экспонирование и интерферометрия");
    const steps = [
      ["Экспонирование", "станция LIGA ВЭПП-3, 30 000–37 000 мА·мин, сканирование ±15 мм; мембрана + шаблон с окнами 15–600 мкм"],
      ["Проявление", "ПММА 15 мкм (сверхмолекулярный, 10⁷ г/моль); 1 мин в диэтиленгликольмонобутиловом эфире"],
      ["Измерение рельефа", "напыление Au; микроинтерферометр МИИ-4, 0,27 мкм на полосу; 106 снимков"],
      ["Обработка", "профили края аппроксимированы arctg; наша независимая обработка: 2 метода, 63 из 106 кадров дают относительный профиль"],
    ];
    const lw = 5.3;
    steps.forEach(([h, b], i) => {
      const y = TOP + i * 1.28;
      s.addShape(S.OVAL, { x: MX, y, w: 0.55, h: 0.55, fill: { color: C.accent2 }, line: { color: C.accent2, width: 0 }, objectName: `Шаг ${i + 1}` });
      text(s, String(i + 1), { x: MX, y, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: C.background1, align: "center", valign: "middle" });
      text(s, [{ text: h, options: { bold: true, fontSize: 16, color: C.text2, breakLine: true } }, { text: b, options: { fontSize: 13 } }],
        { x: MX + 0.75, y: y - 0.03, w: lw - 0.75, h: 1.2 });
    });
    const pic = path.join(RES, "interferometry", "qa", "7b46a665a8.png");
    if (fs.existsSync(pic)) {
      const sz = await imgSize(pic);
      const px = MX + lw + 0.3, pw = W - MX - px, ph = pw * sz.h / sz.w;
      s.addImage({ path: pic, x: px, y: TOP, w: pw, h: ph, objectName: "Обработка интерферограммы" });
      text(s, "Leikosaphire_25/27u28(100): исходный скриншот, полосы, отслеживание полос, маска качества, фаза (Фурье), относительная высота",
        { x: px, y: TOP + ph + 0.08, w: pw, h: 0.55, fontSize: 11, color: C.accent4 });
    }
    s.addNotes("Теперь эксперимент. Образцы экспонировались на станции LIGA через исследуемую мембрану и шаблон с окнами от 15 до 600 мкм, экспозиции 30–37 тысяч мА·мин. Резист — сверхмолекулярный ПММА 15 мкм, проявление 1 минута. Рельеф измерялся микроинтерферометром МИИ-4 после напыления золота, всего в архиве 106 снимков. Профили краёв были аппроксимированы функцией арктангенса. Мы дополнительно сделали независимую обработку архива двумя методами — отслеживанием полос и фурье-методом; справа пример: относительный профиль глубины удаётся получить для 63 кадров из 106.");
  }

  // ================= 14. Недостатки эксперимента =================
  {
    const s = content(SEC[4], "5 · ЭКСПЕРИМЕНТ", "Недостатки эксперимента, мешающие сравнению");
    const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } });
    const rows = [
      [hdr("Проблема"), hdr("Как мешает сходимости")],
      ["Нет калибровки мкм/пиксель и карты отверстий", "профили только в пикселях; кадр нельзя надёжно приписать отверстию"],
      ["Скриншоты JPEG вместо исходных кадров; один кадр без сдвига фазы", "фаза по модулю 2π: глубина неоднозначна (до ~55 периодов на 15 мкм), знак не определяется"],
      ["Единицы аппроксимаций не ясны: b до 112 «мкм» при ПММА 15 мкм", "ширины краёв сравниваются только условно"],
      ["Рельеф ≠ доза: кинетика растворения R(D), боковое проявление", "без калибровки R(D) и режима проявления сравнение качественное [9]"],
      ["Расчётная доза 0,5–1,3 кДж/см³ ниже порога ПММА 2 кДж/см³", "вопрос к экспозициям/фильтрам или к порогу сверхмолекулярного ПММА"],
      ["Расхождения документов: Be 200/220 мкм, каптон 20/25 мкм; нет данных о подложке и зазорах", "систематика ~10 % по рассеянию и не оценённые эффекты"],
    ];
    s.addTable(rows, { x: MX, y: TOP, w: W - 2 * MX, colW: [6.0, W - 2 * MX - 6.0], fontSize: 14, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "D5DBE3" }, fill: { color: "FFFFFF" }, valign: "middle", rowH: 0.66, objectName: "Таблица недостатков" });
    text(s, "Несмотря на это, сравнить модель с экспериментом можно на уровне ширин переходов — следующий слайд.", { x: MX, y: 6.45, w: W - 2 * MX, h: 0.4, fontSize: 14, italic: true, color: C.accent2 });
    s.addNotes("Честно о недостатках эксперимента — они прямо влияют на возможность сходимости. Первое: нет горизонтальной калибровки и карты отверстий, поэтому профили есть только в пикселях и кадр нельзя надёжно приписать конкретному отверстию. Второе: в архиве скриншоты в JPEG, а не исходные кадры, и одиночный кадр определяет фазу только по модулю 2π — глубина через крутую стенку неоднозначна. Третье: в аппроксимациях высоты до 112 «мкм» при толщине резиста 15 мкм — единицы явно не микроны. Четвёртое: измеряется рельеф, а не доза; между ними — кинетика растворения, которую мы не знаем. Пятое: расчётная доза под окном ниже табличного порога ПММА, хотя углубления есть — вопрос либо к записанным экспозициям, либо к порогу для сверхмолекулярного ПММА. И расхождения в документах. Тем не менее сравнение на уровне ширин переходов сделать можно.");
  }

  // ================= 15. Сравнение =================
  {
    const s = content(SEC[4], "5 · ЭКСПЕРИМЕНТ", "Сравнение с моделью: ширина края по окнам");
    const short = { be_200: "Be", carbon_475: "СУ", sapphire_contact: "Al₂O₃ к.", sapphire_280mm: "Al₂O₃ 280" };
    const pairs = [];
    Object.keys(short).forEach((k) => (D.approximations[k] || []).forEach((a) => {
      const r = RA.find((x) => x.key === k && x.hole_um === a.hole_um);
      if (r && a.width_10_90 != null) pairs.push({ key: k, hole: a.hole_um, model: r.width_10_90, approx: a.width_10_90 });
    }));
    const labels = pairs.map((p) => `${short[p.key]} · ${p.hole.toFixed(0)}`).reverse();
    s.addChart(pres.charts.BAR, [
      { name: "Geant4: ширина 10–90 % дозы, мкм", labels, values: pairs.map((p) => +p.model.toFixed(2)).reverse() },
      { name: "аппроксимация ТЗ того же окна, «мкм»", labels, values: pairs.map((p) => +p.approx.toFixed(2)).reverse() },
    ], Object.assign({
      x: MX, y: TOP - 0.05, w: 7.9, h: 4.95, barDir: "bar", barGrouping: "clustered", barGapWidthPct: 35, objectName: "Сравнение ширин по окнам",
      chartColors: ["0F2B46", "1F8A9E"], catAxisLabelFontSize: 11, showLegend: true, legendPos: "b", valAxisMinVal: 0, valAxisMajorUnit: 5,
      showValAxisTitle: true, valAxisTitle: "ширина перехода 10–90 %, мкм",
      showTitle: true, title: "Ширина края для одного и того же окна (мембрана · окно, мкм)", titleFontSize: 13, titleColor: "1B1F2A",
    }, axisStyle(), chartText));
    const pm = pairs.map((p) => p.model), pa = pairs.map((p) => p.approx);
    const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
    const corr = (() => { const mx = mean(pm), my = mean(pa); let sxy = 0, sxx = 0, syy = 0; pm.forEach((x, i) => { sxy += (x - mx) * (pa[i] - my); sxx += (x - mx) ** 2; syy += (pa[i] - my) ** 2; }); return sxy / Math.sqrt(sxx * syy); })();
    const within = pairs.filter((p) => p.approx >= 0.5 * p.model && p.approx <= 2 * p.model).length;
    const be = pairs.filter((p) => p.key === "be_200").map((p) => p.approx);
    const sx = MX + 8.3, sw = W - MX - sx;
    const pts = [
      [I.check, C.accent2, "Порядок совпадает", `модель ${range(Math.min(...pm), Math.max(...pm))} мкм, аппроксимации ${fmt(Math.min(...pa), 2)}–${fmt(Math.max(...pa), 0)} «мкм»; в пределах ×2 — ${within} из ${pairs.length} окон`],
      [I.warn, "B7791F", "Связи по окнам нет", `модель почти не зависит от окна, аппроксимации скачут (Be: ${range(Math.min(...be), Math.max(...be))}); коэффициент корреляции ${fmt(corr, 2)}`],
      [I.flask, C.text2, "С моделью проявления", `Geant4 + эйкональное проявление (R(D) не калибрована): ${range(devMin, devMax)} мкм`],
    ];
    pts.forEach(([ic, col, h, b], i) => {
      const y = TOP + i * 1.62;
      card(s, sx, y, sw, 1.45, { name: h });
      iconCircle(s, sx + 0.2, y + 0.2, 0.5, ic, col, h);
      text(s, h, { x: sx + 0.85, y: y + 0.2, w: sw - 1.0, h: 0.5, fontSize: 15, bold: true, color: C.text2, valign: "middle" });
      text(s, b, { x: sx + 0.2, y: y + 0.75, w: sw - 0.4, h: 0.65, fontSize: 13 });
    });
    text(s, "Сравниваются разные величины: ширина дозового профиля и ширина аппроксимации рельефа; единицы аппроксимаций не подтверждены. Окна без формулы в ТЗ (Be 600, Al₂O₃ вплотную 300) не показаны.",
      { x: MX, y: 6.6, w: W - 2 * MX, h: 0.4, fontSize: 11, color: C.accent4 });
    s.addNotes(`Сравнение по окнам: для каждого окна, где есть и расчёт, и аппроксимация из техзадания, — ${pairs.length} пар. Тёмные столбцы — ширина перехода дозы от 10 до 90 % в модели, бирюзовые — ширина аппроксимации того же окна. Порядок величин совпадает — единицы микрон, в пределах двух раз совпадают ${within} из ${pairs.length} окон. Но связи по окнам нет: модель почти не зависит от размера окна (${range(Math.min(...pm), Math.max(...pm))} мкм), а аппроксимации скачут — у бериллия от ${fmt(Math.min(...be))} до ${fmt(Math.max(...be))} «мкм», у сапфира в 280 мм есть 0,15 мкм — ниже разрешения микроинтерферометра; коэффициент корреляции ${fmt(corr, 2)}. Доза так сильно между окнами не меняется, значит этот разброс дают проявление и измерение. Если пропустить дозу через простую модель проявления с боковым травлением, получаем ${range(devMin, devMax)} мкм — тот же порядок. Подчеркну: сравниваются разные величины, и единицы аппроксимаций не подтверждены, поэтому говорить о хорошем количественном согласии пока нельзя.`);
  }

  // ================= 16. Выводы =================
  pres.addSection({ title: SEC[5] });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: SEC[5] });
    s.addText("6 · ВЫВОДЫ", { placeholder: "kicker" });
    s.addText("Выводы: сходимость модели и эксперимента", { placeholder: "title" });
    const sc = cfg.sapphire_contact;
    const othOpen = Math.max(...["be_200", "carbon_475", "titanium_model"].map((k) => cfg[k].membrane_open_pct));
    const scAll = RA.filter((r) => r.key === "sapphire_contact");
    const rows = [
      [I.check, C.accent2, "Модель проверена независимо", "спектр и нормировка совпали с диссертацией (0,5–4 %), коэффициенты ослабления — с NIST (≤ 4,8 %), 36 проверок без провалов"],
      [I.approx, C.accent1, "Качественная сходимость есть", `ширины краёв одного порядка (единицы мкм), но по отдельным окнам модель и аппроксимации не коррелируют; край формируют электроны и флуоресценция шаблона`],
      [I.times, C.accent3, "Количественной сходимости пока нет", "не хватает калибровок эксперимента: масштаб X, единицы аппроксимаций, R(D); доза ниже табличного порога"],
      [I.arrow, "5BC8D6", "Для выбора материала", `рассеяние в мембране (окно ${sc.hole_um.toFixed(0)} мкм): < ${Math.ceil(othOpen)} % под окном у Be, стеклоуглерода, Ti и ${fmt(sc.membrane_open_pct)} / ${fmt(sc.membrane_shadow_pct)} % у сапфира вплотную (до ${fmt(Math.max(...scAll.map((r) => r.membrane_shadow_pct)))} % у окна 600 мкм); удаление на 280 мм убирает эффект`],
    ];
    rows.forEach(([ic, col, h, b], i) => {
      const y = TOP + 0.05 + i * 1.3;
      iconCircle(s, MX, y + 0.1, 0.75, ic, col, h);
      text(s, h, { x: MX + 1.05, y, w: W - 2 * MX - 1.05, h: 0.45, fontSize: 20, bold: true, color: C.background1, fontFace: THEME.headFontFace });
      text(s, b, { x: MX + 1.05, y: y + 0.48, w: W - 2 * MX - 1.05, h: 0.7, fontSize: 15, color: "CADCFC" });
    });
    s.addNotes("Выводы. Первое: сама модель проверена независимо от наших экспериментов — по диссертации и по NIST. Второе: качественная сходимость с экспериментом есть — ширины краёв одного порядка, и понятно, что их формирует. Третье: количественной сходимости пока нет, и это ограничение данных, а не модели: нет калибровки масштаба, единиц аппроксимаций и зависимости скорости растворения от дозы. Четвёртое, практическое: рассеяние в мембране под окном мало для бериллия, стеклоуглерода и титана; у сапфира вплотную оно заметно, особенно в тени и для крупных окон, и убирается, если сапфир отнести от маски. Отсюда рекомендация: для масок вплотную к резисту — лёгкие мембраны (Be, стеклоуглерод, Ti), сапфир — только на расстоянии.");
  }

  // ================= 17. Дальше =================
  {
    const s = content(SEC[5], "6 · ВЫВОДЫ", "Как улучшить эксперимент и что моделировать дальше");
    const cw = (W - 2 * MX - 0.3) / 2;
    const cols = [
      [I.micro, C.accent2, "Эксперимент", [
        "калибровка мкм/пиксель (эталон), карта отверстий, журнал кадров",
        "исходные кадры камеры, серии со сдвигом фазы → однозначная глубина",
        "независимый профиль: профилометр, СЭМ скола",
        "калибровка R(D): ступени доз на одном образце, фиксированные t и T проявления",
        "записать подложку, зазоры, ориентацию шаблона, реальные толщины",
      ]],
      [I.chart, C.accent1, "Моделирование", [
        "скан толщин мембран → допустимые диапазоны толщин для рекомендаций",
        "статистика standard; чувствительность: зазоры, ориентация шаблона, подложка",
        "брэгговские рефлексы сапфира (по ориентации кристалла) и SAXS стеклоуглерода вне Geant4",
        "уровень B: доза → R(D) → рельеф, проверка leave-one-hole-out",
        "новые кандидаты мембран (Si₃N₄, SiC, алмаз, Si, полиимид) тем же конвейером",
      ]],
    ];
    cols.forEach(([ic, col, h, items], i) => {
      const x = MX + i * (cw + 0.3);
      card(s, x, TOP, cw, 5.25, { name: h });
      iconCircle(s, x + 0.25, TOP + 0.25, 0.6, ic, col, h);
      text(s, h, { x: x + 1.0, y: TOP + 0.3, w: cw - 1.2, h: 0.5, fontSize: 18, bold: true, color: C.text2, valign: "middle" });
      text(s, items.map((t, k) => ({ text: t, options: { bullet: { type: "number" }, breakLine: k < items.length - 1, paraSpaceAfter: 14 } })),
        { x: x + 0.3, y: TOP + 1.1, w: cw - 0.55, h: 4.0, fontSize: 16 });
    });
    s.addNotes("Что делать дальше. Для эксперимента: самое важное — калибровка горизонтального масштаба и карта отверстий, без этого кадры не привязать. Дальше — исходные кадры камеры и серии со сдвигом фазы, чтобы снять неоднозначность глубины; независимый метод измерения профиля, например профилометр или СЭМ скола; калибровка скорости растворения от дозы на одном образце при фиксированных времени и температуре проявления; и фиксировать в журнале подложку, зазоры, толщины. Для моделирования: набрать рабочую статистику, сделать прогоны чувствительности, отдельно оценить брэгговские рефлексы в сапфире и малоугловое рассеяние в стеклоуглероде, построить сквозную цепочку доза — проявление — рельеф с честной проверкой на отложенных отверстиях, и прогнать тем же конвейером новые кандидаты мембран. Отдельно — скан толщин мембран: вклад рассеяния растёт пропорционально массе на пути пучка, и скан даст допустимые диапазоны толщин, которые нужны для практических рекомендаций.");
  }

  // ================= 18. Литература =================
  pres.addSection({ title: SEC[6] });
  {
    const s = content(SEC[6], "ЛИТЕРАТУРА", "Источники");
    const refs = [
      "Saile V., Wallrabe U., Tabata O., Korvink J. G. (eds.) LIGA and its applications. Wiley-VCH, 2009.",
      "Гольденберг Б. Г. Диссертация (2011): рентгеношаблоны для глубокой рентгенолитографии, станция LIGA ВЭПП-3.",
      "Zumaqué H., Kohring G. A., Hormes J. Simulational studies of energy deposition and secondary processes in deep X-ray lithography // J. Micromech. Microeng. 1997. Vol. 7.",
      "Faisal A., Beckenbach T., Mohr J., Meyer P. Influence of secondary effects in the fabrication of submicron resist structures using deep X-ray lithography // J. Micro/Nanolith. MEMS MOEMS. 2019. Vol. 18, No. 2. 023502.",
      "Vitreous carbon mask substrate for X-ray lithography. Patent US 7608367 B1 (Sandia National Laboratories).",
      "Goldenberg B. G., Lemzyakov A. G., Nazmov V. P., Pindyurin V. F. Multifunctional X-ray lithography station at VEPP-3 // Physics Procedia. 2016. Vol. 84.",
      "Lemzyakov A. G. et al. Manufacturing of high resolution X-ray masks for LIGA technology in SSTRC // SFR-2016, ИЯФ СО РАН.",
      "Назьмов В. П., Варанд А. В., Михайленко М. А. и др. Полиметилметакрилат с молекулярной массой 10⁷ г/моль для рентгеновской литографии // Поверхность. 2023. № 6. С. 27–31.",
      "Pantenburg F. J., Achenbach S., Mohr J. Influence of developer temperature and resist material on the structure quality in deep X-ray lithography // J. Vac. Sci. Technol. B. 1998. Vol. 16. P. 3547.",
      "Agostinelli S. et al. Geant4 — a simulation toolkit // NIM A 506 (2003) 250; Allison J. et al. // IEEE TNS 53 (2006) 270; NIM A 835 (2016) 186.",
      "Hubbell J. H., Seltzer S. M. Tables of X-ray mass attenuation coefficients, NISTIR 5632.",
    ];
    text(s, refs.map((t, k) => ({ text: t, options: { bullet: { type: "number" }, breakLine: k < refs.length - 1, paraSpaceAfter: 8 } })),
      { x: MX, y: TOP - 0.1, w: W - 2 * MX, h: 5.45, fontSize: 13 });
    s.addNotes("Список источников. [1] — LIGA в целом; [2] — диссертация Гольденберга: маски, контраст, параметры станции; [3, 4] — вторичные процессы в глубокой рентгенолитографии; [5] — стеклоуглерод как основа маски; [6, 7] — станция LIGA на ВЭПП-3 и маски ЦКП; [8] — сверхмолекулярный ПММА; [9] — влияние проявления; [10] — Geant4; [11] — NIST.");
  }

  await pres.writeFile({ fileName: OUT });
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("записано", OUT);
}

main().catch((e) => { console.error(e); process.exit(1); });
