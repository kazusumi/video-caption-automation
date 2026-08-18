#!/usr/bin/env python3
"""Transcribe Japanese speech and burn layered ASS captions into a video."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


TERM_CORRECTIONS = {
    "フィグマ": "Figma",
    "フォトショップ": "Photoshop",
    "フォトピー": "Photopea",
    "エスブイジー": "SVG",
    "ユーアイユーエックス": "UI/UX",
    "アドラスターグラフィックス": "Add Raster Graphics",
}
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/delagothicone/DelaGothicOne-Regular.ttf"
TARGET_BYTES = 90_000_000


@dataclass
class Caption:
    start: float
    end: float
    text: str


def run(command: list[str]) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, check=True)


def correct_terms(text: str) -> str:
    for wrong, right in TERM_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return re.sub(r"\s+([、。！？])", r"\1", text).strip()


def transcribe(source: Path, model_name: str, device: str, compute_type: str):
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        str(source), language="ja", word_timestamps=True, vad_filter=True
    )
    return list(segments)


def make_captions(segments) -> tuple[str, list[Caption]]:
    raw_parts: list[str] = []
    captions: list[Caption] = []
    for segment in segments:
        raw_parts.append(segment.text.strip())
        words = [word for word in (segment.words or []) if word.start is not None]
        if not words:
            captions.append(Caption(segment.start, segment.end, correct_terms(segment.text)))
            continue
        group = []
        for word_index, word in enumerate(words):
            group.append(word)
            text = "".join(item.word for item in group).strip()
            duration = group[-1].end - group[0].start
            pause = 0 if word_index == len(words) - 1 else words[word_index + 1].start - word.end
            boundary = bool(re.search(r"[。！？、]$", text))
            if (boundary and len(text) >= 12) or len(text) >= 34 or duration >= 7 or pause >= 0.7:
                captions.append(Caption(group[0].start, group[-1].end, correct_terms(text)))
                group = []
        if group:
            captions.append(Caption(group[0].start, group[-1].end, correct_terms("".join(w.word for w in group))))
    return "".join(raw_parts), [caption for caption in captions if caption.text]


def wrap_japanese(text: str, width: int = 22) -> str:
    if len(text) <= width:
        return text
    candidates = [i + 1 for i, char in enumerate(text[:-1]) if char in "、。！？"]
    split = min(candidates or range(1, len(text)), key=lambda i: abs(i - len(text) / 2))
    return text[:split] + "\n" + text[split:]


def srt_time(value: float) -> str:
    millis = round(value * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def ass_time(value: float) -> str:
    centis = round(value * 100)
    hours, centis = divmod(centis, 360_000)
    minutes, centis = divmod(centis, 6_000)
    seconds, centis = divmod(centis, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centis:02}"


def write_srt(path: Path, captions: list[Caption]) -> None:
    blocks = []
    for index, caption in enumerate(captions, 1):
        blocks.append(f"{index}\n{srt_time(caption.start)} --> {srt_time(caption.end)}\n{wrap_japanese(caption.text)}")
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8-sig")


def ass_escape(text: str) -> str:
    return wrap_japanese(text).replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def write_ass(path: Path, captions: list[Caption]) -> None:
    header = """[Script Info]
Title: Japanese captions
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shadow,Dela Gothic One,42,&H003BD4FF,&H003BD4FF,&H003BD4FF,&H003BD4FF,0,0,0,0,100,100,0,0,1,0,0,2,70,70,38,1
Style: Outer,Dela Gothic One,42,&H009A5307,&H009A5307,&H009A5307,&H009A5307,0,0,0,0,100,100,0,0,1,9,0,2,70,70,44,1
Style: Inner,Dela Gothic One,42,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,5,0,2,70,70,44,1
Style: Body,Dela Gothic One,42,&H00FFB72B,&H00FFB72B,&H00FFB72B,&H00FFB72B,0,0,0,0,100,100,0,0,1,0,0,2,70,70,44,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for caption in captions:
        start, end, text = ass_time(caption.start), ass_time(caption.end), ass_escape(caption.text)
        events.extend([
            f"Dialogue: 0,{start},{end},Shadow,,0,0,0,,{{\\pos(646,682)}}{text}",
            f"Dialogue: 1,{start},{end},Outer,,0,0,0,,{{\\pos(640,676)}}{text}",
            f"Dialogue: 2,{start},{end},Inner,,0,0,0,,{{\\pos(640,676)}}{text}",
            f"Dialogue: 3,{start},{end},Body,,0,0,0,,{{\\pos(640,676)}}{text}",
        ])
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


def ensure_font(output_dir: Path) -> Path:
    windows_font = Path.home() / "AppData/Local/Microsoft/Windows/Fonts/DelaGothicOne-Regular.ttf"
    if windows_font.exists():
        return windows_font.parent
    font_dir = output_dir / "fonts"
    font_dir.mkdir(exist_ok=True)
    font = font_dir / "DelaGothicOne-Regular.ttf"
    if not font.exists():
        urllib.request.urlretrieve(FONT_URL, font)
    return font_dir


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def ass_filter(ass: Path, fonts: Path) -> str:
    def escape(path: Path) -> str:
        return path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    return f"subtitles='{escape(ass)}':fontsdir='{escape(fonts)}'"


def encode(source: Path, ass: Path, fonts: Path, destination: Path) -> None:
    common = ["ffmpeg", "-y", "-i", str(source), "-vf", ass_filter(ass, fonts), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
    run(common + ["-crf", "23", "-preset", "medium", str(destination)])
    if destination.stat().st_size < TARGET_BYTES:
        return
    video_rate = max(300, int(((TARGET_BYTES * 8 / duration(source)) - 128_000) / 1000 * 0.96))
    temporary = destination.with_name("captioned_video_2pass.mp4")
    passlog = destination.parent / "ffmpeg2pass"
    run(["ffmpeg", "-y", "-i", str(source), "-vf", ass_filter(ass, fonts), "-c:v", "libx264", "-b:v", f"{video_rate}k", "-pass", "1", "-passlogfile", str(passlog), "-an", "-f", "null", "NUL"])
    run(common + ["-b:v", f"{video_rate}k", "-pass", "2", "-passlogfile", str(passlog), str(temporary)])
    temporary.replace(destination)
    for log in destination.parent.glob("ffmpeg2pass*"):
        log.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"Input does not exist: {args.input}")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe must be available on PATH")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    segments = transcribe(args.input, args.model, args.device, args.compute_type)
    raw, captions = make_captions(segments)
    corrected = "".join(caption.text for caption in captions)
    (args.output_dir / "transcript_raw.txt").write_text(raw + "\n", encoding="utf-8")
    (args.output_dir / "transcript_corrected.txt").write_text(corrected + "\n", encoding="utf-8")
    srt = args.output_dir / "subtitles_corrected.srt"
    ass = args.output_dir / "subtitles_styled.ass"
    write_srt(srt, captions)
    write_ass(ass, captions)
    encode(args.input, ass, ensure_font(args.output_dir), args.output_dir / "captioned_video.mp4")


if __name__ == "__main__":
    main()
