"""ffmpeg 유틸리티 — 경로 탐색, 프레임 추출, 필터 생성, 인코딩."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def _get_ffmpeg() -> str:
    """내장 ffmpeg 경로 반환. 없으면 시스템 PATH의 ffmpeg 사용."""
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "ffmpeg.exe"
    else:
        bundled = Path(__file__).parent.parent / "vendor" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"


def _get_ffprobe() -> str:
    """ffprobe 경로. ffmpeg과 같은 디렉토리에서 찾는다."""
    ffmpeg = _get_ffmpeg()
    if ffmpeg != "ffmpeg":
        probe = Path(ffmpeg).parent / "ffprobe.exe"
        if probe.exists():
            return str(probe)
    return "ffprobe"


def extract_first_frame(video_path: str) -> Image.Image:
    """MP4에서 첫 프레임을 추출하여 PIL Image로 반환."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        cmd = [_get_ffmpeg(), "-i", video_path, "-vframes", "1",
               "-f", "image2", "-y", tmp_path]
        subprocess.run(cmd, capture_output=True, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return Image.open(tmp_path).convert("RGB").copy()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def get_video_info(video_path: str) -> dict:
    """영상 정보 반환: width, height, duration, codec."""
    cmd = [_get_ffprobe(), "-v", "quiet", "-print_format", "json",
           "-show_streams", "-show_format", video_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"width": 0, "height": 0, "duration": 0, "codec": "unknown"}

    info = {"width": 0, "height": 0, "duration": 0, "codec": "unknown"}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = int(stream.get("width", 0))
            info["height"] = int(stream.get("height", 0))
            info["codec"] = stream.get("codec_name", "unknown")
            break

    fmt = data.get("format", {})
    info["duration"] = float(fmt.get("duration", 0))
    return info


def build_filter_complex(regions: list[dict]) -> str:
    """영역 리스트로 ffmpeg filter_complex 문자열 생성."""
    if not regions:
        return ""

    filters = []
    prev = "0:v"

    for i, r in enumerate(regions):
        x, y, w, h, kind = r["x"], r["y"], r["w"], r["h"], r["kind"]
        out = f"s{i}"

        if kind == "fill":
            filters.append(f"[{prev}]drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill[{out}]")
        elif kind == "blur":
            base = f"base{i}"
            fork = f"fork{i}"
            blur = f"blur{i}"
            filters.append(f"[{prev}]split=2[{base}][{fork}]")
            filters.append(f"[{fork}]crop={w}:{h}:{x}:{y}[crop{i}]")
            filters.append(f"[crop{i}]gblur=sigma=20[{blur}]")
            filters.append(f"[{base}][{blur}]overlay={x}:{y}[{out}]")
        elif kind == "mosaic":
            base = f"base{i}"
            fork = f"fork{i}"
            pix = f"pix{i}"
            bw, bh = max(1, w // 16), max(1, h // 16)
            filters.append(f"[{prev}]split=2[{base}][{fork}]")
            filters.append(f"[{fork}]crop={w}:{h}:{x}:{y}[crop{i}]")
            filters.append(f"[crop{i}]scale={bw}:{bh}:flags=neighbor,scale={w}:{h}:flags=neighbor[{pix}]")
            filters.append(f"[{base}][{pix}]overlay={x}:{y}[{out}]")

        prev = out

    return ";".join(filters), prev


def apply_masks(video_path: str, output_path: str, regions: list[dict],
                progress_callback=None):
    """영상에 마스크를 적용하여 새 파일로 저장.

    progress_callback(percent: float) — 0.0~100.0
    반환: (success: bool, message: str)
    """
    filter_str, final_label = build_filter_complex(regions)
    if not filter_str:
        return False, "적용할 영역이 없습니다."

    cmd = [
        _get_ffmpeg(), "-y", "-i", video_path,
        "-filter_complex", filter_str,
        "-map", f"[{final_label}]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path,
    ]

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        info = get_video_info(video_path)
        total_dur = info["duration"] if info["duration"] > 0 else 1

        process = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, text=True,
            creationflags=flags,
        )

        for line in process.stderr:
            if progress_callback:
                match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
                if match:
                    h, m, s, cs = [int(x) for x in match.groups()]
                    current = h * 3600 + m * 60 + s + cs / 100
                    pct = min(100.0, (current / total_dur) * 100)
                    progress_callback(pct)

        process.wait()
        if process.returncode == 0:
            return True, f"완료: {output_path}"
        else:
            return False, f"ffmpeg 오류 (코드 {process.returncode})"
    except FileNotFoundError:
        return False, "ffmpeg을 찾을 수 없습니다."


def apply_crop(video_path: str, output_path: str, crop_region: dict,
               progress_callback=None):
    """영상을 크롭하여 새 파일로 저장.

    crop_region: {"x": int, "y": int, "w": int, "h": int}
    반환: (success: bool, message: str)
    """
    x, y, w, h = crop_region["x"], crop_region["y"], crop_region["w"], crop_region["h"]

    cmd = [
        _get_ffmpeg(), "-y", "-i", video_path,
        "-vf", f"crop={w}:{h}:{x}:{y}",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output_path,
    ]

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        info = get_video_info(video_path)
        total_dur = info["duration"] if info["duration"] > 0 else 1

        process = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, text=True,
            creationflags=flags,
        )

        for line in process.stderr:
            if progress_callback:
                match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
                if match:
                    h_, m_, s_, cs = [int(v) for v in match.groups()]
                    current = h_ * 3600 + m_ * 60 + s_ + cs / 100
                    pct = min(100.0, (current / total_dur) * 100)
                    progress_callback(pct)

        process.wait()
        if process.returncode == 0:
            return True, f"완료: {output_path}"
        else:
            return False, f"ffmpeg 오류 (코드 {process.returncode})"
    except FileNotFoundError:
        return False, "ffmpeg을 찾을 수 없습니다."


def compress_video(video_path: str, output_path: str, width: int = 480,
                   bitrate: str = "500k", mute: bool = True,
                   progress_callback=None):
    """영상 압축. 해상도 축소 + 비트레이트 제한 + 선택적 음소거.

    반환: (success: bool, message: str)
    """
    vf = f"scale={width}:-2"
    cmd = [
        _get_ffmpeg(), "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-b:v", bitrate, "-pix_fmt", "yuv420p",
    ]
    if mute:
        cmd.extend(["-an"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    cmd.append(output_path)

    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        info = get_video_info(video_path)
        total_dur = info["duration"] if info["duration"] > 0 else 1

        process = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, text=True,
            creationflags=flags,
        )

        for line in process.stderr:
            if progress_callback:
                match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
                if match:
                    h, m, s, cs = [int(v) for v in match.groups()]
                    current = h * 3600 + m * 60 + s + cs / 100
                    pct = min(100.0, (current / total_dur) * 100)
                    progress_callback(pct)

        process.wait()
        if process.returncode == 0:
            # 용량 비교
            import os
            orig_mb = os.path.getsize(video_path) / (1024 * 1024)
            comp_mb = os.path.getsize(output_path) / (1024 * 1024)
            ratio = (1 - comp_mb / orig_mb) * 100 if orig_mb > 0 else 0
            return True, f"완료: {output_path}\n{orig_mb:.1f}MB → {comp_mb:.1f}MB ({ratio:.0f}% 감소)"
        else:
            return False, f"ffmpeg 오류 (코드 {process.returncode})"
    except FileNotFoundError:
        return False, "ffmpeg을 찾을 수 없습니다."


def extract_frame_at(video_path: str, seconds: float) -> Image.Image:
    """영상에서 특정 시간(초)의 프레임을 추출."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        cmd = [_get_ffmpeg(), "-ss", f"{seconds:.3f}", "-i", video_path,
               "-vframes", "1", "-f", "image2", "-y", tmp_path]
        subprocess.run(cmd, capture_output=True, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return Image.open(tmp_path).convert("RGB").copy()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
