"""FNB58 리더 — OpenFNB58(GPLv3, vendored) 프로토콜 구현을 감싸는 얇은 어댑터.

이전 버전은 FNB58 HID 프로토콜을 자체 추정치로 구현했으나, 실제로는
https://github.com/yeckel/OpenFNB58 에 리버스엔지니어링으로 검증된 구현이
이미 있다. 그 코드를 pi/vendor/openfnb58/fnb58.py 에 그대로 복사해 두고
(pi/vendor/openfnb58/ORIGIN.md — 출처·라이선스 GPLv3), 여기서는 그 모듈의
공개 함수(find_hidraw/open_hid/hid_write/hid_read/decode_packet 등)를 호출해
우리 PowerReader 인터페이스에 맞춰주기만 한다. 디코딩 로직 자체는 건드리지 않았다.

USB HID(`/dev/hidraw*`) 전용이라 Linux(Raspberry Pi OS)에서만 동작한다.
사용자를 `plugdev` 그룹에 넣어야 root 없이 접근 가능 (pi/README.md 참고).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from .base import PowerReader, Sample

_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor" / "openfnb58"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

import fnb58 as openfnb58  # noqa: E402 — vendored OpenFNB58 (GPLv3)


class FNB58Reader(PowerReader):
    """OpenFNB58의 USB HID 프로토콜로 FNB58을 읽는다.

    read()는 60ms 이내에 새 데이터가 없으면 None을 반환한다(호출 쪽에서
    다음 루프까지 기다리면 됨) — main.py의 "샘플 없으면 이번 틱은 건너뜀"
    루프와 맞춘 논블로킹 동작.

    재초기화 감시: 실기에서 FNB58이 수 분 뒤 USB 연결은 유지한 채 데이터 전송만
    멈추는 현상이 있었다(CMD_POLL에 응답 없음, 재초기화하면 즉시 재개).
    stall_timeout_s 동안 데이터 패킷이 없으면 아래 순서로 단계적으로 복구한다.
    OpenFNB58의 read_once()와 같은 순서 — aa81(INIT1)은 기기 재부팅 위험이
    있어 가벼운 방법이 실패했을 때만 쓴다.
      0. drain + INIT2×2            (가벼운 재시작)
      1. drain + INIT1 + INIT2×2    (전체 초기화)
      2. fd 닫고 hidraw 다시 찾아 열기 (USB 재열거로 노드가 바뀐 경우)
    데이터가 다시 들어오면 단계는 0으로 돌아간다.

    로그: 실기(Zero W)는 오버레이 파일시스템이라 journald 로그도 RAM에 쌓인다.
    끊김이 몇 분마다 반복될 수 있으므로 단계 0 복구는 처음 1회만 찍고 이후엔
    summary_interval_s(기본 1시간)마다 횟수 요약 한 줄만 남긴다. 드문 단계 1·2는
    매번 찍는다.
    """

    def __init__(
        self,
        poll_interval_s: float = 1.0,
        stall_timeout_s: float = 10.0,
        summary_interval_s: float = 3600.0,
    ) -> None:
        self.poll_interval_s = poll_interval_s
        self.stall_timeout_s = stall_timeout_s
        self.summary_interval_s = summary_interval_s
        self._fd: int | None = None
        self._next_poll = 0.0
        self._queue: list[dict] = []
        self._last_data = 0.0
        self._recovery_step = 0
        self._stalled = False
        self._logged_first_stall = False
        self._recoveries = 0  # 마지막 요약 이후 복구(끊김→재개) 횟수
        self._last_summary = time.monotonic()

    def open(self) -> None:
        path = openfnb58.find_hidraw()
        self._fd = openfnb58.open_hid(path)
        if not openfnb58._hid_init(self._fd):  # noqa: SLF001 — vendored helper, drain+INIT1+INIT2×2
            raise RuntimeError("FNB58 초기화 명령 전송 실패 — 연결/권한을 확인하세요")
        self._next_poll = time.time()
        self._last_data = time.monotonic()

    def _recover(self) -> None:
        """데이터가 끊긴 지 stall_timeout_s가 지났을 때 한 단계씩 복구를 시도한다."""
        step = self._recovery_step
        if step > 0 or not self._logged_first_stall:
            print(f"[fnb58] {self.stall_timeout_s:g}초간 데이터 없음 — 복구 단계 {step} 시도")
        self._stalled = True
        self._queue = []
        if step == 0:
            openfnb58.hid_drain(self._fd)
            ok = openfnb58.hid_write(self._fd, openfnb58.CMD_INIT2)
            time.sleep(0.05)
            ok = openfnb58.hid_write(self._fd, openfnb58.CMD_INIT2) and ok
        elif step == 1:
            ok = openfnb58._hid_init(self._fd)  # noqa: SLF001
        else:
            self.close()
            self.open()  # find_hidraw()가 장치를 못 찾으면 sys.exit → systemd가 서비스 재시작
            ok = True
        if not ok:
            print("[fnb58] 명령 전송 실패 — 다음 단계로")
        self._recovery_step = (step + 1) % 3
        self._next_poll = time.time()
        self._last_data = time.monotonic()  # 다음 단계까지 다시 stall_timeout_s 기다림

    def _maybe_log_summary(self) -> None:
        now = time.monotonic()
        if now - self._last_summary < self.summary_interval_s:
            return
        if self._recoveries:
            mins = (now - self._last_summary) / 60.0
            print(f"[fnb58] 최근 {mins:.0f}분간 재초기화 복구 {self._recoveries}회")
        self._recoveries = 0
        self._last_summary = now

    def read(self) -> Sample | None:
        if self._fd is None:
            raise RuntimeError("open()을 먼저 호출해야 합니다")

        if self._queue:
            s = self._queue.pop(0)
            return Sample(voltage_v=s["voltage_V"], current_a=s["current_A"])

        if time.monotonic() - self._last_data >= self.stall_timeout_s:
            self._recover()

        now = time.time()
        if now >= self._next_poll:
            openfnb58.hid_write(self._fd, openfnb58.CMD_POLL)
            self._next_poll = now + self.poll_interval_s

        timeout = max(0.05, min(1.0, self._next_poll - time.time()))
        data = openfnb58.hid_read(self._fd, timeout=timeout)
        if data is None:
            return None

        samples = openfnb58.decode_packet(data)
        if not samples:
            return None

        if self._stalled:
            if not self._logged_first_stall:
                print("[fnb58] 데이터 수신 재개 — 이후 단계 0 복구는 요약으로만 기록")
                self._logged_first_stall = True
            self._recoveries += 1
            self._stalled = False
        self._recovery_step = 0
        self._maybe_log_summary()
        self._last_data = time.monotonic()
        self._queue = samples
        s = self._queue.pop(0)
        return Sample(voltage_v=s["voltage_V"], current_a=s["current_A"])

    def close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


if __name__ == "__main__":
    # 단독 실행 시 빠른 연결 확인용. 좀 더 자세한 디버깅(raw 패킷 덤프,
    # BLE 모드, 트리거 등)은 vendor/openfnb58/fnb58.py를 직접 실행:
    #   python pi/vendor/openfnb58/fnb58.py --once
    with FNB58Reader() as reader:
        print("FNB58 측정 시작 (Ctrl+C로 종료)")
        try:
            while True:
                sample = reader.read()
                if sample is not None:
                    print(f"V={sample.voltage_v:.3f}V  I={sample.current_a:.3f}A  P={sample.power_w:.3f}W")
        except KeyboardInterrupt:
            pass
