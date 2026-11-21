#!/usr/bin/env python3
"""Render the 30-second MiniWater explainer from original motion graphics.

Optional dependencies live in tools/requirements-animation.txt. No PLC, network,
or hardware access is performed. Diagram states and trace rows are illustrative.
"""

import argparse
from functools import lru_cache
import math
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, DURATION = 1280, 720, 30
BG = '#081722'
PANEL = '#102735'
BORDER = '#294553'
WHITE = '#f0f6f5'
MUTED = '#b4c7d1'
TEAL = '#4ae0bc'
BLUE = '#61c9ee'
RED = '#ff8f79'
WATER = '#166584'
STAGES = ['THE PROCESS', 'THE FALSE INPUT', 'THE PHYSICAL IMPACT',
          'THE EXECUTION EVIDENCE', 'THE CAUSAL EXPLANATION', 'THE PURPOSE']


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


@lru_cache(maxsize=64)
def font(size, weight='regular'):
    suffix = {'regular': '', 'bold': '-Bold', 'mono': 'Mono'}[weight]
    path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans' + suffix + '.ttf')
    if not path.is_file():
        path = Path(ImageFont.truetype('DejaVuSans' + suffix + '.ttf', size).path)
    return ImageFont.truetype(str(path), size)


def text(draw, xy, value, size=24, color=WHITE, weight='regular', spacing=10):
    draw.multiline_text(xy, value, font=font(size, weight), fill=color, spacing=spacing)


def label(draw, xy, value, color=TEAL):
    text(draw, xy, value, 15, color, 'mono')


def pill(draw, box, value, color=TEAL, size=15):
    draw.rounded_rectangle(box, radius=12, fill=PANEL, outline=BORDER, width=1)
    text(draw, (box[0] + 16, box[1] + 11), value, size, color, 'bold')


def arrow(draw, start, end, color=BORDER, width=3):
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    points = [end]
    for delta in (-0.55, 0.55):
        points.append((end[0] - 12 * math.cos(angle + delta),
                       end[1] - 12 * math.sin(angle + delta)))
    draw.polygon(points, fill=color)


def particles(draw, start, end, time, color=BLUE, count=4):
    for index in range(count):
        position = (time * 0.25 + index / count) % 1
        x = start[0] + (end[0] - start[0]) * position
        y = start[1] + (end[1] - start[1]) * position
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)


@lru_cache(maxsize=6)
def background(stage):
    canvas = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(canvas)
    for x in range(680, WIDTH, 40):
        for y in range(125, 640, 40):
            draw.ellipse((x, y, x + 1, y + 1), fill='#203440')
    # Original geometric water mark; no external artwork or logos.
    draw.rounded_rectangle((64, 38, 74, 62), radius=3, fill=TEAL)
    draw.rounded_rectangle((81, 30, 91, 62), radius=3, fill=BLUE)
    draw.rounded_rectangle((98, 44, 108, 62), radius=3, fill=TEAL)
    label(draw, (126, 40), 'MINIWATER / IMPACT IN 30 SECONDS', WHITE)
    label(draw, (1040, 40), '{:02d} / 06'.format(stage + 1), MUTED)
    draw.line((64, 88, 1216, 88), fill=BORDER, width=1)
    label(draw, (64, 121), STAGES[stage])
    draw.line((64, 654, 1216, 654), fill=BORDER, width=1)
    text(draw, (64, 679), 'Illustrative MiniWater scenario | not live footage', 14, MUTED)
    text(draw, (1000, 679), 'ICSTracker / DSN 2025', 14, MUTED)
    return canvas


def tank(draw, time, level=0.58, pump_on=True, altered=False, spill=0.0):
    draw.line((701, 284, 795, 284), fill=BORDER, width=14)
    particles(draw, (706, 284), (791, 284), time)
    label(draw, (701, 249), 'INFLOW', MUTED)
    draw.rounded_rectangle((795, 203, 1035, 475), radius=18, fill=PANEL)
    top = 460 - 242 * level
    wave = [(809 + x, top + 3 * math.sin(x / 23 + time * 2.4)) for x in range(213)]
    draw.polygon(wave + [(1021, 460), (809, 460)], fill=WATER)
    draw.line(wave, fill=BLUE, width=3)
    draw.rounded_rectangle((795, 203, 1035, 475), radius=18, outline=WHITE, width=3)
    for y in (250, 305, 360, 415):
        draw.line((1005, y, 1021, y), fill=BORDER, width=2)
    text(draw, (823, 491), 'PROCESS TANK', 18, MUTED, 'bold')
    if altered:
        pill(draw, (863, 148, 1113, 190), 'INPUT ALTERED', RED)
    draw.line((1036, 425, 1200, 425, 1200, 480), fill=BORDER, width=14)
    if pump_on:
        particles(draw, (1042, 425), (1197, 425), time, TEAL, 3)
    color = TEAL if pump_on else RED
    draw.ellipse((1104, 394, 1166, 456), fill=PANEL, outline=color, width=3)
    angle = time * 4 if pump_on else 0.6
    for offset in (0, math.pi, math.pi / 2, -math.pi / 2):
        a = angle + offset
        draw.line((1135, 425, 1135 + 20 * math.cos(a), 425 + 20 * math.sin(a)), fill=color, width=4)
    text(draw, (1083, 482), 'DRAIN / ' + ('ON' if pump_on else 'OFF'), 17, color, 'bold')
    if spill > 0:
        # Water escapes at the tank rim and visibly reaches the ground.
        end = 220 + 295 * ease(spill)
        draw.line((1029, 214, 1058, 231, 1069, end), fill=BLUE, width=8)
        for i in range(7):
            y = 235 + ((time * 150 + i * 41) % max(1, end - 235))
            if y < end:
                draw.ellipse((1072, y, 1077, y + 11), fill=BLUE)
        if end > 470:
            draw.ellipse((1048, 510, 1110 + spill * 48, 519 + spill * 8), fill=WATER)
    draw.rounded_rectangle((758, 539, 1059, 610), radius=12, fill=PANEL, outline=BORDER, width=2)
    draw.rounded_rectangle((777, 557, 809, 589), radius=5, outline=TEAL, width=2)
    for y in (563, 574, 585):
        draw.line((771, y, 777, y), fill=TEAL, width=2)
        draw.line((809, y, 815, y), fill=TEAL, width=2)
    text(draw, (834, 551), 'OpenPLC CONTROLLER', 16, WHITE, 'bold')
    text(draw, (834, 576), 'drain command: ' + ('ON' if pump_on else 'OFF'), 15, color, 'mono')


def headline(draw, first, second, second_color=WHITE, size=48):
    text(draw, (64, 176), first, size, WHITE, 'bold')
    text(draw, (64, 244), second, size, second_color, 'bold')


def scene(stage, local):
    canvas = background(stage).copy()
    draw = ImageDraw.Draw(canvas)
    if stage == 0:
        headline(draw, 'A controller decision', 'moves real water.', size=46)
        text(draw, (64, 355), 'Software commands change pumps,\nvalves, and physical processes.', 25, MUTED)
        pill(draw, (64, 477, 514, 524), 'PLC / ICS ROOT CAUSE ANALYSIS', size=16)
        text(draw, (64, 551), 'MiniWater water-treatment testbed', 20, WHITE)
        tank(draw, local)
    elif stage == 1:
        headline(draw, 'One false input.', 'The wrong command.', RED, 46)
        text(draw, (64, 355), 'False process data changes control flow.\nThe drainage pump stops too early.', 24, MUTED)
        pill(draw, (64, 479, 257, 526), 'ALTERED INPUT', RED)
        arrow(draw, (273, 503), (312, 503), RED)
        pill(draw, (328, 479, 535, 526), 'PUMP OFF', RED)
        tank(draw, local + 5, 0.58 + 0.27 * ease(local / 5), local < 0.65, local > 0.3)
    elif stage == 2:
        headline(draw, 'The consequence:', 'tank overflow.', RED)
        text(draw, (64, 355), 'The process keeps filling.\nThe failure becomes physical.', 25, MUTED)
        pill(draw, (64, 479, 543, 526), 'PHYSICAL PROCESS DISRUPTION', RED, 16)
        text(draw, (64, 552), 'Real stakes for water-system operations.', 20, WHITE)
        tank(draw, local + 10, 0.85 + 0.15 * ease(local / 1.4), False, True,
             ease((local - 1) / 1.2))
    elif stage == 3:
        headline(draw, 'Capture the', 'decision path.', TEAL)
        text(draw, (64, 355), 'Record function calls, arguments,\nand values inside the PLC runtime.', 25, MUTED)
        pill(draw, (64, 479, 557, 526), 'THIS REPO: CONTROLLER INSTRUMENTATION', size=14)
        text(draw, (64, 550), 'Execution evidence for investigation.', 21, WHITE)
        draw.rounded_rectangle((662, 183, 1216, 589), radius=18, fill=PANEL, outline=BORDER, width=2)
        label(draw, (688, 210), 'ILLUSTRATIVE EXECUTION TRACE', MUTED)
        draw.line((688, 247, 1190, 247), fill=BORDER, width=1)
        rows = ['input read', 'branch evaluated', 'drainage command: OFF', 'arguments + values captured']
        for index, row in enumerate(rows):
            y = 281 + 57 * index
            if local >= 0.3 + index * 0.75:
                color = RED if index == 2 else TEAL
                label(draw, (689, y + 2), '{:02d}'.format(index + 1), color)
                text(draw, (735, y), row, 20, WHITE, 'mono')
                if index < 3:
                    draw.line((703, y + 27, 703, y + 50), fill=BORDER, width=2)
        text(draw, (688, 547), 'Clang 14 + LLVM instrumentation', 18, TEAL)
    elif stage == 4:
        text(draw, (64, 176), 'Backtrack from symptom to cause.', 46, WHITE, 'bold')
        text(draw, (64, 252), 'ICSTracker connects execution evidence into a causal explanation.', 24, MUTED)
        nodes = ['False process\ninput', 'Control\ndecision', 'Drain pump\nstopped', 'Tank\noverflow']
        active = 3 - min(3, int(max(0, local - 0.4) / 0.8))
        for index, title in enumerate(nodes):
            x = 64 + index * 300
            reached = index >= active
            color = TEAL if reached else BORDER
            draw.rounded_rectangle((x, 330, x + 252, 464), radius=15, fill=PANEL, outline=color, width=3)
            label(draw, (x + 22, 348), 'CAUSE' if index == 0 else ('EFFECT' if index == 3 else 'CONTROL STATE'),
                  TEAL if reached else MUTED)
            text(draw, (x + 22, 383), title, 24, WHITE, 'bold', 4)
            if index < 3:
                arrow(draw, (x + 263, 398), (x + 288, 398), BORDER)
        arrow(draw, (1194, 513), (85, 513), TEAL, 2)
        dot_x = 1194 - 1109 * ((local / 3.2) % 1)
        draw.ellipse((dot_x - 6, 507, dot_x + 6, 519), fill=TEAL)
        label(draw, (445, 530), 'INVESTIGATION DIRECTION', TEAL)
        pill(draw, (64, 580, 584, 625), 'THIS REPO: TRACE COLLECTION', size=15)
        pill(draw, (630, 580, 1216, 625), 'FULL FRAMEWORK: CAUSAL ANALYSIS', size=15)
    else:
        text(draw, (64, 171), 'Make the failure', 64, WHITE, 'bold')
        text(draw, (64, 252), 'explainable.', 64, TEAL, 'bold')
        text(draw, (64, 365), 'Evidence for targeted investigation\nand recovery.', 26, MUTED)
        pill(draw, (64, 470, 714, 519), 'MiniWater / PLC + ICS root cause analysis', size=21)
        draw.rounded_rectangle((866, 184, 1216, 493), radius=18, fill=PANEL, outline=BORDER, width=2)
        text(draw, (894, 219), 'ICSTracker', 34, WHITE, 'bold')
        text(draw, (894, 280), 'IEEE/IFIP DSN 2025', 20, TEAL)
        draw.line((894, 330, 1188, 330), fill=BORDER, width=1)
        text(draw, (894, 356), 'Instrument.\nTrace. Investigate.', 25, WHITE, 'bold', 14)
        label(draw, (64, 568), 'EXPLORE THE CODE + READ THE RESEARCH', TEAL)
        text(draw, (64, 602), 'github.com/iotrustlab/miniwater-raspberry-pi-instrumentation', 20, WHITE, 'mono')
    return canvas


def frame(time):
    stage = min(5, int(time / 5))
    local = time - stage * 5
    canvas = scene(stage, local)
    if stage > 0 and local < 0.35:
        canvas = Image.blend(scene(stage - 1, 4.999), canvas, ease(local / 0.35))
    draw = ImageDraw.Draw(canvas)
    for index in range(6):
        x = 64 + index * 193
        draw.rounded_rectangle((x, 638, x + 180, 641), radius=1, fill=BORDER)
        progress = max(0, min(1, (time - index * 5) / 5))
        if progress > 0:
            draw.rounded_rectangle((x, 638, x + 180 * progress, 641), radius=1, fill=TEAL)
    return canvas


def ffmpeg_executable(explicit):
    if explicit:
        return explicit
    installed = shutil.which('ffmpeg')
    if installed:
        return installed
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise SystemExit('Install tools/requirements-animation.txt or pass --ffmpeg /path/to/ffmpeg') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/media')
    parser.add_argument('--fps', type=int, default=24, choices=(12, 24, 30))
    parser.add_argument('--ffmpeg', help='optional ffmpeg executable')
    parser.add_argument('--preview-only', action='store_true', help='render six storyboard stills only')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.preview_only:
        for index in range(6):
            frame(index * 5 + 3).save(args.output / 'scene-{}.png'.format(index + 1))
        return
    mp4 = args.output / 'miniwater-impact.mp4'
    command = [ffmpeg_executable(args.ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '{}x{}'.format(WIDTH, HEIGHT),
               '-r', str(args.fps), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'medium',
               '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
        for index in range(DURATION * args.fps):
            encoder.stdin.write(frame(index / args.fps).tobytes())
            if index % (args.fps * 5) == 0:
                print('Rendered {} / 30 seconds'.format(index // args.fps), flush=True)
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise SystemExit('MP4 encoding failed')
    # ffmpeg uses one global palette to keep text and colors steady across scenes.
    gif = args.output / 'miniwater-impact.gif'
    subprocess.run([ffmpeg_executable(args.ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
                    '-i', str(mp4), '-filter_complex',
                    '[0:v]fps=10,scale=768:-1:flags=lanczos,split[a][b];'
                    '[a]palettegen=max_colors=128:stats_mode=diff[p];'
                    '[b][p]paletteuse=dither=bayer:bayer_scale=3',
                    '-loop', '0', str(gif)], check=True)
    frame(2.5).save(args.output / 'miniwater-impact-poster.jpg', quality=92)
    print('Created 30-second MP4, looping GIF, and static poster.', flush=True)


if __name__ == '__main__':
    main()
