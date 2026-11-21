# MiniWater impact animation

A 30-second, silent explainer of PLC/ICS root cause analysis. The looping GIF appears in the main README; the 1280 × 720 MP4 provides the full-resolution video at 24 frames per second. All graphics are drawn by the included Python renderer.

- [MP4 video](miniwater-impact.mp4)
- [Looping GIF](miniwater-impact.gif)
- [Static poster](miniwater-impact-poster.jpg)
- [WebVTT captions](miniwater-impact.vtt)
- [Renderer source](../../tools/render_impact_animation.py)

## Transcript and storyboard

| Time | Caption | Illustration |
| --- | --- | --- |
| 00:00–00:05 | A controller decision moves real water. | Normal inflow, a stable tank level, and an operating drainage pump. |
| 00:05–00:10 | One false input. The wrong command. | An altered process input leads to premature drainage-pump shutdown. |
| 00:10–00:15 | The consequence: tank overflow. | Inflow continues, water rises, and the tank spills. |
| 00:15–00:20 | Capture the decision path. | Instrumented OpenPLC collects evidence of calls, arguments, and values. Trace rows are illustrative. |
| 00:20–00:25 | Backtrack from symptom to cause. | The full ICSTracker framework connects overflow, pump shutdown, the control decision, and the false input. |
| 00:25–00:30 | Make the failure explainable. | Evidence supports targeted investigation and recovery. The closing card links viewers to the code and research. |

The scenario follows the causal chain in Table II, case #8 of [*ICSTracker: Backtracking Intrusions in Modern Industrial Control Systems*, IEEE/IFIP DSN 2025](https://doi.org/10.1109/DSN64029.2025.00031). This is a conceptual illustration of the MiniWater experiment, rather than live footage or a measured reproduction. It contains no measured sensor values, timing results, or claim of automated prevention or recovery. This repository supplies controller instrumentation; provenance analysis belongs to the full framework.

## Rebuild

Use an optional environment separate from the PLC runtime:

```bash
python3 -m venv /tmp/miniwater-animation-env
/tmp/miniwater-animation-env/bin/python -m pip install -r tools/requirements-animation.txt
/tmp/miniwater-animation-env/bin/python tools/render_impact_animation.py
```

The renderer uses DejaVu Sans, available in Debian's `fonts-dejavu-core` package. It uses a system FFmpeg executable when available and otherwise uses the executable supplied by `imageio-ffmpeg`. No PLC hardware, credentials, or network access are needed during rendering.

To inspect the six storyboard stills without encoding the video:

```bash
/tmp/miniwater-animation-env/bin/python tools/render_impact_animation.py \
    --preview-only --output /tmp/miniwater-impact-preview
```
