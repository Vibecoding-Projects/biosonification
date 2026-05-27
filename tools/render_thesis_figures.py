from __future__ import annotations

import math
import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "thesis_artifacts"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ["arialbd.ttf" if bold else "arial.ttf", "timesbd.ttf" if bold else "times.ttf"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT_TITLE = font(42, True)
FONT_HEAD = font(30, True)
FONT_BODY = font(24)
FONT_SMALL = font(20)


def canvas(width: int = 1800, height: int = 900) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (width, height), "white")
    return img, ImageDraw.Draw(img)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw:
            lines.append("")
            continue
        words = raw.split()
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_size(draw, candidate, fnt)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    lines: list[str],
    fnt: ImageFont.ImageFont,
    fill: str = "black",
    line_gap: int = 8,
) -> None:
    x1, y1, x2, y2 = box
    heights = [text_size(draw, line, fnt)[1] for line in lines]
    total = sum(heights) + line_gap * max(0, len(lines) - 1)
    y = y1 + (y2 - y1 - total) // 2
    for line, h in zip(lines, heights):
        w, _ = text_size(draw, line, fnt)
        draw.text((x1 + (x2 - x1 - w) // 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    body: str = "",
    dashed: bool = False,
    fill: str = "white",
) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=10, outline="black", width=3, fill=fill)
    if dashed:
        for x in range(x1, x2, 18):
            draw.line((x, y1, min(x + 9, x2), y1), fill="black", width=3)
            draw.line((x, y2, min(x + 9, x2), y2), fill="black", width=3)
        for y in range(y1, y2, 18):
            draw.line((x1, y, x1, min(y + 9, y2)), fill="black", width=3)
            draw.line((x2, y, x2, min(y + 9, y2)), fill="black", width=3)
    title_lines = wrap(draw, title, FONT_HEAD, x2 - x1 - 30)
    body_lines = wrap(draw, body, FONT_SMALL, x2 - x1 - 30) if body else []
    title_h = sum(text_size(draw, line, FONT_HEAD)[1] for line in title_lines) + 6 * (len(title_lines) - 1)
    body_h = sum(text_size(draw, line, FONT_SMALL)[1] for line in body_lines) + 5 * max(0, len(body_lines) - 1)
    total = title_h + (14 if body_lines else 0) + body_h
    y = y1 + (y2 - y1 - total) // 2
    for line in title_lines:
        w, h = text_size(draw, line, FONT_HEAD)
        draw.text((x1 + (x2 - x1 - w) // 2, y), line, font=FONT_HEAD, fill="black")
        y += h + 6
    if body_lines:
        y += 8
    for line in body_lines:
        w, h = text_size(draw, line, FONT_SMALL)
        draw.text((x1 + (x2 - x1 - w) // 2, y), line, font=FONT_SMALL, fill="black")
        y += h + 5


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], label: str = "") -> None:
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill="black", width=3)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 16
    points = [
        (x2, y2),
        (x2 - size * math.cos(angle - 0.45), y2 - size * math.sin(angle - 0.45)),
        (x2 - size * math.cos(angle + 0.45), y2 - size * math.sin(angle + 0.45)),
    ]
    draw.polygon(points, fill="black")
    if label:
        mid = ((x1 + x2) // 2, (y1 + y2) // 2)
        lines = wrap(draw, label, FONT_SMALL, 220)
        h = len(lines) * 22
        w = max(text_size(draw, line, FONT_SMALL)[0] for line in lines) + 14
        draw.rectangle((mid[0] - w // 2, mid[1] - h // 2 - 4, mid[0] + w // 2, mid[1] + h // 2 + 4), fill="white")
        centered_text(draw, (mid[0] - w // 2, mid[1] - h // 2, mid[0] + w // 2, mid[1] + h // 2), lines, FONT_SMALL, line_gap=3)


def title(draw: ImageDraw.ImageDraw, text: str, width: int) -> None:
    w, h = text_size(draw, text, FONT_TITLE)
    draw.text(((width - w) // 2, 50), text, font=FONT_TITLE, fill="black")


def save(img: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    diff = ImageChops.difference(img, Image.new("RGB", img.size, "white"))
    bbox = diff.getbbox()
    if bbox:
        margin = 45
        x1 = max(0, bbox[0] - margin)
        y1 = max(0, bbox[1] - margin)
        x2 = min(img.size[0], bbox[2] + margin)
        y2 = min(img.size[1], bbox[3] + margin)
        img = img.crop((x1, y1, x2, y2))
    img.save(OUT / name, "PNG", optimize=True)


def pipeline() -> None:
    img, draw = canvas()
    title(draw, "Архитектура BioSonification structured v2", 1800)
    boxes = {
        "fasta": (110, 350, 345, 470),
        "bio": (445, 350, 700, 470),
        "pair": (800, 350, 1055, 470),
        "harm": (1165, 235, 1420, 355),
        "mel": (1165, 465, 1420, 585),
        "midi": (1530, 350, 1765, 470),
    }
    box(draw, boxes["fasta"], "FASTA", "DNA / RNA / protein")
    box(draw, boxes["bio"], "Биологический энкодер", "features + vector")
    box(draw, boxes["pair"], "Pairing", "bio profile -> music descriptors")
    box(draw, boxes["harm"], "Harmony model", "аккорды по тактам")
    box(draw, boxes["mel"], "Melody model", "ноты поверх гармонии")
    box(draw, boxes["midi"], "MIDI renderer", "2 дорожки")
    arrow(draw, (345, 410), (445, 410))
    arrow(draw, (700, 410), (800, 410))
    arrow(draw, (1055, 410), (1165, 295), "условие")
    arrow(draw, (1055, 410), (1165, 525), "условие")
    arrow(draw, (1292, 355), (1292, 465), "harmony context")
    arrow(draw, (1420, 295), (1530, 390))
    arrow(draw, (1420, 525), (1530, 430))
    save(img, "pipeline_architecture.png")


def hierarchy() -> None:
    img, draw = canvas()
    title(draw, "Иерархическая генерация Bio -> Harmony -> Melody", 1800)
    box(draw, (120, 365, 360, 485), "FASTA", "последовательность")
    box(draw, (480, 330, 760, 520), "Биоэнкодер", "признаки\nembedding 256\ncontrol profile")
    box(draw, (910, 190, 1210, 330), "Control tokens", "tempo, density,\ncomplexity, mode")
    box(draw, (910, 555, 1210, 695), "Memory tokens", "контекст для\ncross-attention")
    box(draw, (1360, 190, 1620, 330), "Harmony model", "аккордовая\nпоследовательность")
    box(draw, (1360, 555, 1620, 695), "Melody model", "мелодия с учетом\nгармонии")
    box(draw, (1360, 755, 1620, 835), "MIDI", "harmony + melody")
    arrow(draw, (360, 425), (480, 425))
    arrow(draw, (760, 390), (910, 260), "profile")
    arrow(draw, (760, 460), (910, 625), "embedding")
    arrow(draw, (1210, 260), (1360, 260))
    arrow(draw, (1490, 330), (1490, 555), "harmony prefix")
    arrow(draw, (1210, 625), (1360, 625))
    arrow(draw, (1490, 695), (1490, 755))
    save(img, "hierarchical_generation_scheme.png")


def dataset_split() -> None:
    img, draw = canvas()
    title(draw, "Данные и разбиение выборок", 1800)
    box(draw, (105, 230, 405, 370), "RefSeq FASTA", "3746 bio fragments")
    box(draw, (105, 520, 405, 660), "POP909 MIDI", "25940 music segments")
    box(draw, (560, 365, 860, 505), "Предобработка", "features, descriptors,\n4-тактовые сегменты")
    box(draw, (1015, 365, 1315, 505), "Pairing", "15925 обучающих пар")
    box(draw, (1470, 180, 1730, 300), "Train", "обучение")
    box(draw, (1470, 390, 1730, 510), "Validation", "выбор checkpoint")
    box(draw, (1470, 600, 1730, 720), "Test", "итоговая проверка")
    arrow(draw, (405, 300), (560, 410))
    arrow(draw, (405, 590), (560, 460))
    arrow(draw, (860, 435), (1015, 435))
    arrow(draw, (1315, 435), (1470, 240))
    arrow(draw, (1315, 435), (1470, 450))
    arrow(draw, (1315, 435), (1470, 660))
    save(img, "dataset_and_split_overview.png")


def descriptor_pairing() -> None:
    img, draw = canvas()
    title(draw, "Pairing биологических и музыкальных сегментов", 1800)
    box(draw, (120, 230, 420, 370), "Bio fragment", "GC, entropy,\nprotein properties")
    box(draw, (120, 540, 420, 680), "Music segment", "tempo, density,\nregister, mode")
    box(draw, (610, 230, 910, 370), "Control profile", "6 управляющих\nпризнаков")
    box(draw, (610, 540, 910, 680), "Music descriptors", "6 музыкальных\nдескрипторов")
    box(draw, (1080, 365, 1380, 505), "Calibration", "нормализация\nпространства")
    box(draw, (1530, 365, 1760, 505), "Top-k matching", "bio-music pairs")
    arrow(draw, (420, 300), (610, 300))
    arrow(draw, (420, 610), (610, 610))
    arrow(draw, (910, 300), (1080, 410))
    arrow(draw, (910, 610), (1080, 460))
    arrow(draw, (1380, 435), (1530, 435))
    save(img, "descriptor_pairing_scheme.png")


def ablation() -> None:
    img, draw = canvas()
    title(draw, "Проверка влияния bio conditioning", 1800)
    box(draw, (140, 170, 420, 290), "Real bio", "настоящий embedding\nи profile")
    box(draw, (140, 390, 420, 510), "Shuffled bio", "условие перемешано\nмежду фрагментами")
    box(draw, (140, 610, 420, 730), "Neutral bio", "усредненное\nусловие")
    box(draw, (720, 390, 1040, 510), "Одна и та же модель", "фиксированные веса\nодинаковый протокол")
    box(draw, (1330, 300, 1670, 600), "Сравнение метрик", "valid MIDI rate\nchord-tone ratio\nself-similarity\nnote density")
    arrow(draw, (420, 230), (720, 430))
    arrow(draw, (420, 450), (720, 450))
    arrow(draw, (420, 670), (720, 470))
    arrow(draw, (1040, 450), (1330, 450))
    save(img, "bio_conditioning_ablation_scheme.png")


def axes(draw: ImageDraw.ImageDraw, origin: tuple[int, int], size: tuple[int, int]) -> None:
    x, y = origin
    w, h = size
    draw.line((x, y, x, y - h), fill="black", width=3)
    draw.line((x, y, x + w, y), fill="black", width=3)


def plot_line(
    draw: ImageDraw.ImageDraw,
    origin: tuple[int, int],
    size: tuple[int, int],
    values: list[float],
    min_v: float,
    max_v: float,
    fill: str,
    width: int = 4,
) -> None:
    x0, y0 = origin
    w, h = size
    pts = []
    for i, value in enumerate(values):
        x = x0 + int(w * i / (len(values) - 1))
        y = y0 - int(h * (value - min_v) / (max_v - min_v))
        pts.append((x, y))
    draw.line(pts, fill=fill, width=width)
    for pt in pts:
        draw.ellipse((pt[0] - 5, pt[1] - 5, pt[0] + 5, pt[1] + 5), fill=fill)


def training_plot() -> None:
    img, draw = canvas(1800, 950)
    title(draw, "Динамика validation loss актуальной модели", 1800)
    origin = (220, 760)
    size = (1280, 520)
    axes(draw, origin, size)
    harmony = [0.159, 0.145, 0.147, 0.146, 0.150, 0.156, 0.152, 0.156, 0.154, 0.156]
    melody = [0.202, 0.179, 0.171, 0.164, 0.161, 0.158, 0.157, 0.163, 0.157, 0.162, 0.169, 0.162, 0.162, 0.162, 0.169]
    min_v, max_v = 0.13, 0.22
    for val in [0.14, 0.16, 0.18, 0.20, 0.22]:
        y = origin[1] - int(size[1] * (val - min_v) / (max_v - min_v))
        draw.line((origin[0], y, origin[0] + size[0], y), fill="#d0d0d0", width=1)
        draw.text((120, y - 12), f"{val:.2f}", font=FONT_SMALL, fill="black")
    plot_line(draw, origin, size, harmony, min_v, max_v, "black")
    plot_line(draw, origin, size, melody, min_v, max_v, "#777777")
    draw.text((760, 810), "Эпоха", font=FONT_BODY, fill="black")
    draw.text((60, 450), "Loss", font=FONT_BODY, fill="black")
    draw.line((1540, 315, 1605, 315), fill="black", width=5)
    draw.text((1620, 300), "Harmony", font=FONT_BODY, fill="black")
    draw.line((1540, 365, 1605, 365), fill="#777777", width=5)
    draw.text((1620, 350), "Melody", font=FONT_BODY, fill="black")
    box(draw, (1500, 500, 1730, 635), "Лучшие значения", "Harmony 0.1454\nMelody 0.1566")
    save(img, "training_loss_curves.png")


def bar_group(draw: ImageDraw.ImageDraw, x: int, y: int, title_text: str, labels: list[str], values: list[float], scale: float) -> None:
    draw.text((x, y - 60), title_text, font=FONT_HEAD, fill="black")
    max_h = 280
    bar_w = 85
    gap = 35
    shades = ["black", "#666666", "#bbbbbb"]
    for i, (label, value) in enumerate(zip(labels, values)):
        h = int(max_h * value / scale)
        x1 = x + i * (bar_w + gap)
        draw.rectangle((x1, y + max_h - h, x1 + bar_w, y + max_h), fill=shades[i], outline="black")
        draw.text((x1, y + max_h + 18), label, font=FONT_SMALL, fill="black")
        text = f"{value:.3f}" if value < 2 else f"{value:.2f}"
        tw, _ = text_size(draw, text, FONT_SMALL)
        draw.text((x1 + (bar_w - tw) // 2, y + max_h - h - 30), text, font=FONT_SMALL, fill="black")


def evaluation_plot() -> None:
    img, draw = canvas(1800, 900)
    title(draw, "Сравнение метрик генерации", 1800)
    labels = ["act.", "prev.", "base"]
    bar_group(draw, 150, 250, "Chord-tone ratio", labels, [0.6710, 0.6073, 0.4043], 0.75)
    bar_group(draw, 710, 250, "Note density / bar", labels, [5.2083, 4.9167, 5.2917], 5.6)
    bar_group(draw, 1270, 250, "Self-similarity", labels, [0.1663, 0.1314, 0.1086], 0.18)
    draw.text((150, 760), "act. - актуальная модель; prev. - предыдущая версия; base - random baseline", font=FONT_BODY, fill="black")
    save(img, "evaluation_metric_comparison.png")


def midi_profile() -> None:
    img, draw = canvas(1800, 950)
    title(draw, "Профиль 12 сгенерированных MIDI-фрагментов", 1800)
    notes = [20, 24, 16, 25, 23, 20, 16, 26, 21, 21, 20, 18]
    ctr = [0.650, 0.708, 0.750, 0.800, 0.783, 0.800, 0.500, 0.538, 0.667, 0.762, 0.650, 0.444]
    x0, y0 = 180, 740
    w, h = 1360, 500
    axes(draw, (x0, y0), (w, h))
    bar_w = 58
    gap = 50
    for i, n in enumerate(notes):
        x = x0 + 40 + i * (bar_w + gap)
        bh = int(h * n / 30)
        draw.rectangle((x, y0 - bh, x + bar_w, y0), fill="#d0d0d0", outline="black", width=2)
        draw.text((x + 12, y0 + 20), str(i + 1), font=FONT_SMALL, fill="black")
    pts = []
    for i, value in enumerate(ctr):
        x = x0 + 40 + i * (bar_w + gap) + bar_w // 2
        y = y0 - int(h * value / 1.0)
        pts.append((x, y))
    draw.line(pts, fill="black", width=4)
    for x, y in pts:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill="black")
    draw.text((700, 810), "Номер фрагмента", font=FONT_BODY, fill="black")
    draw.text((60, 425), "Ноты / CTR", font=FONT_BODY, fill="black")
    draw.rectangle((1560, 305, 1605, 335), fill="#d0d0d0", outline="black")
    draw.text((1620, 300), "Количество нот", font=FONT_BODY, fill="black")
    draw.line((1560, 385, 1605, 385), fill="black", width=5)
    draw.text((1620, 370), "Chord-tone ratio", font=FONT_BODY, fill="black")
    save(img, "generated_midi_profile.png")


def main() -> None:
    pipeline()
    hierarchy()
    dataset_split()
    descriptor_pairing()
    ablation()
    training_plot()
    evaluation_plot()
    midi_profile()


if __name__ == "__main__":
    main()
