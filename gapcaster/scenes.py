"""Shot boundaries with PySceneDetect (BSD-3)."""
import math
from scenedetect import AdaptiveDetector, detect


def shots(video_path, min_len: float = 0.6, max_len: float = 8.0):
    scenes = detect(str(video_path), AdaptiveDetector(), start_in_scene=True)  # a clip with no cuts is one shot
    merged = []
    for a, b in scenes:
        s, e = (a.seconds, b.seconds) if hasattr(a, "seconds") else (a.get_seconds(), b.get_seconds())
        if merged and e - s < min_len:          # fold flicker-length shots into the previous one
            merged[-1][1] = e
            continue
        merged.append([s, e])
    out = []
    for s, e in merged:
        # Subdivide long cut-free spans (e.g. documentary cross-dissolve montages) so each visual beat gets keyframes
        n = max(1, math.ceil((e - s) / max_len)) if max_len and e - s > max_len else 1
        step = (e - s) / n
        for k in range(n):
            a0, b0 = s + k * step, (e if k == n - 1 else s + (k + 1) * step)
            out.append({"id": f"S{len(out) + 1:03d}", "start": round(a0, 3), "end": round(b0, 3)})
    return out


def keyframe_times(shot, max_frames: int = 2):
    s, e = shot["start"], shot["end"]
    if e - s > 5.0 and max_frames > 1:
        return [s + (e - s) / 3, s + 2 * (e - s) / 3]
    return [(s + e) / 2]
