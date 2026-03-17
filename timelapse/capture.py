import time
from datetime import datetime
from pathlib import Path

import mss
from PIL import Image

from .config import Config
from .monitor import validate_monitor
from .video import generate_video


def _calc_diff(img_a: Image.Image, img_b: Image.Image) -> float:
    """두 이미지의 픽셀 차이 평균 계산 (축소 비교로 가볍게)."""
    size = (256, 144)
    a = img_a.resize(size, Image.NEAREST)
    b = img_b.resize(size, Image.NEAREST)
    pairs = zip(a.tobytes(), b.tobytes())
    total_diff = sum(abs(x - y) for x, y in pairs)
    return total_diff / (size[0] * size[1] * 3)


def run_capture(config: Config):
    """스크린 캡처 루프 실행."""
    monitor_index = config.capture.monitor
    if not validate_monitor(monitor_index):
        print(f"오류: 모니터 {monitor_index}번을 찾을 수 없습니다.")
        return

    base_path = Path(config.storage.base_path)
    interval = config.capture.interval
    quality = config.capture.quality
    skip_similar = config.capture.skip_similar
    diff_threshold = config.capture.diff_threshold

    print(f"캡처 시작 (모니터: {monitor_index}, 간격: {interval}초, 품질: {quality}%)")
    if skip_similar:
        print(f"유사 프레임 건너뛰기: ON (임계값: {diff_threshold})")
    print(f"저장 경로: {base_path}")
    print("종료: Ctrl+C\n")

    count = 0
    skipped = 0
    prev_img = None

    # 실행 시점의 날짜+시간으로 세션 폴더 생성
    session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_folder = base_path / session_name
    session_folder.mkdir(parents=True, exist_ok=True)
    print(f"세션 폴더: {session_folder}\n")

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_index]

            while True:
                start = time.monotonic()
                now = datetime.now()

                # 캡처
                raw = sct.grab(monitor)
                pil_img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

                # 유사 프레임 비교
                if skip_similar and prev_img is not None:
                    diff = _calc_diff(prev_img, pil_img)
                    if diff < diff_threshold:
                        skipped += 1
                        print(f"  [{now.strftime('%H:%M:%S')}] 건너뜀 (diff={diff:.2f}) 저장:{count} 스킵:{skipped}", end="\r")
                        elapsed = time.monotonic() - start
                        time.sleep(max(0, interval - elapsed))
                        continue

                # 저장
                filename = session_folder / f"{now.strftime('%H-%M-%S')}.jpg"
                pil_img.save(str(filename), "JPEG", quality=quality)
                prev_img = pil_img

                count += 1
                print(f"  [{now.strftime('%H:%M:%S')}] #{count} 저장: {filename.name} (스킵:{skipped})", end="\r")

                # 정확한 간격 유지
                elapsed = time.monotonic() - start
                sleep_time = max(0, interval - elapsed)
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print(f"\n\n캡처 종료. 총 {count}장 저장, {skipped}장 건너뜀.")

        if config.video.auto_generate and session_folder.exists():
            print("영상 자동 생성 중...")
            output = session_folder.parent / f"{session_name}.mp4"
            generate_video(str(session_folder), str(output), config.video.fps, config.video.crf)
