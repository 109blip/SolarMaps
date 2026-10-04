"""SolarMaps Pi 노드 — FNB58에서 읽은 전력 데이터를 Firestore로 올린다.

흐름 (docs/DATA_SPEC.md 기준):
  1초마다        FNB58(또는 시뮬레이터)에서 전압/전류 샘플링
  station_update_interval_s마다   solar_stations/{station_id} 최신 상태로 갱신 (지도 마커용)
  log_interval_s(기본 60s)마다    그 구간 평균/최고/누적을 solar_logs에 1건 추가 (차트용)

실행:
  python main.py [config.json 경로, 기본값 ./config.json]
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from firestore_client import FirestoreClient
from readers import FNB58Reader, Sample, SimulatorReader
from telemetry import cpu_temp_c, wifi_rssi_dbm

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state.json"


def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(
            f"설정 파일을 찾을 수 없습니다: {path}\n"
            f"{path.parent / 'config.example.json'}을 config.json으로 복사한 뒤 값을 채워주세요."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_reader(device_cfg: dict, sample_interval_s: float):
    mode = device_cfg.get("mode", "simulator")
    if mode == "fnb58":
        # VID/PID(2e3c:5558)는 vendor/openfnb58/fnb58.py에 고정돼 있어 설정할 필요 없음.
        return FNB58Reader(
            poll_interval_s=sample_interval_s,
            stall_timeout_s=device_cfg.get("stall_timeout_s", 10.0),
        )
    if mode == "simulator":
        return SimulatorReader()
    sys.exit(f"알 수 없는 device.mode: {mode!r} (fnb58 | simulator)")


def load_today_energy(today: str) -> float:
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if saved.get("date") == today:
                return float(saved.get("today_energy_wh", 0.0))
        except (json.JSONDecodeError, ValueError):
            pass
    return 0.0


def save_today_energy(today: str, wh: float) -> None:
    STATE_FILE.write_text(json.dumps({"date": today, "today_energy_wh": wh}), encoding="utf-8")


def main() -> None:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = load_config(config_path)

    station_cfg = cfg["station"]
    wifi_interface = cfg["device"].get("wifi_interface", "wlan0")

    sample_interval_s = cfg["timing"].get("sample_interval_s", 1.0)
    log_interval_s = cfg["timing"].get("log_interval_s", 60)
    station_update_interval_s = cfg["timing"].get("station_update_interval_s", 5)

    fs = FirestoreClient(
        service_account_path=cfg["firebase"]["service_account_path"],
        project_id=cfg["firebase"].get("project_id"),
    )
    reader = build_reader(cfg["device"], sample_interval_s)

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_energy_wh = load_today_energy(today_str)

    window: list[Sample] = []
    last_station_update = 0.0
    last_log_flush = time.monotonic()

    print(f"[main] station_id={station_cfg['station_id']} mode={cfg['device'].get('mode')} — 시작")

    with reader:
        try:
            while True:
                loop_start = time.monotonic()
                sample = reader.read()

                now = datetime.now()
                new_today = now.strftime("%Y-%m-%d")
                if new_today != today_str:
                    # 자정 넘어감 — 금일 누적 발전량 리셋.
                    today_str = new_today
                    today_energy_wh = 0.0

                if sample is not None:
                    window.append(sample)
                    # 다음 station 갱신까지 남은 순간전력을 today_energy_wh에도 반영해
                    # 대시보드가 항상 "최근까지의 금일 누적치"를 보게 한다.
                    today_energy_wh += sample.power_w * (sample_interval_s / 3600.0)

                iso_now = now.astimezone().isoformat(timespec="seconds")

                # ── solar_stations: 지도 마커용 최신 상태 (자주, 가볍게) ──
                if sample is not None and loop_start - last_station_update >= station_update_interval_s:
                    station_doc = {
                        **station_cfg,
                        "live_status": {
                            "state": "GENERATING" if sample.power_w > 0.5 else "IDLE",
                            "power_w": round(sample.power_w, 2),
                            "voltage_v": round(sample.voltage_v, 3),
                            "current_a": round(sample.current_a, 3),
                            "today_energy_wh": round(today_energy_wh, 2),
                            "temp_c": cpu_temp_c() or 0.0,  # 패널 온도 센서 미장착 시 CPU온도로 임시 대체
                            "last_updated": iso_now,
                        },
                        "telemetry": {
                            "pi_cpu_temp_c": cpu_temp_c() or 0.0,
                            "wifi_rssi_dbm": wifi_rssi_dbm(wifi_interface) or 0.0,
                        },
                    }
                    try:
                        fs.set_station(station_cfg["station_id"], station_doc)
                    except Exception as exc:  # noqa: BLE001 — 네트워크 문제로 루프 전체가 죽으면 안 됨
                        print(f"[firestore] solar_stations 갱신 실패: {exc}")
                    last_station_update = loop_start

                # ── solar_logs: 1분 평균/최고 (docs/DATA_SPEC.md §3 컬렉션 3) ──
                if loop_start - last_log_flush >= log_interval_s:
                    if window:
                        voltages = [s.voltage_v for s in window]
                        currents = [s.current_a for s in window]
                        powers = [s.power_w for s in window]
                        elapsed_h = (loop_start - last_log_flush) / 3600.0
                        log_doc = {
                            "station_id": station_cfg["station_id"],
                            "iso_time": iso_now,
                            "date": today_str,
                            "voltage_avg_v": round(sum(voltages) / len(voltages), 3),
                            "current_avg_a": round(sum(currents) / len(currents), 3),
                            "power_avg_w": round(sum(powers) / len(powers), 2),
                            "power_max_w": round(max(powers), 2),
                            "energy_delta_wh": round((sum(powers) / len(powers)) * elapsed_h, 3),
                            "temp_c": cpu_temp_c() or 0.0,
                            "sample_count": len(window),
                        }
                        try:
                            fs.add_log(log_doc)
                        except Exception as exc:  # noqa: BLE001
                            print(f"[firestore] solar_logs 추가 실패: {exc}")
                        window = []
                    save_today_energy(today_str, today_energy_wh)
                    last_log_flush = loop_start

                elapsed = time.monotonic() - loop_start
                time.sleep(max(0.0, sample_interval_s - elapsed))
        except KeyboardInterrupt:
            print("\n[main] 종료 신호 수신 — 정리 중")
            save_today_energy(today_str, today_energy_wh)


if __name__ == "__main__":
    main()
