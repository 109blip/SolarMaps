"""규격서(docs/DATA_SPEC.md) §5 목업 데이터를 Firestore에 주입한다.

firebase-admin(grpcio)이 Python 3.14용 휠을 아직 제공하지 않는 환경에서는
REST API + google-auth로 자동 대체한다. 두 경로 모두 동일한 문서를 쓴다.

사용 전: Firebase 콘솔에서 서비스 계정 키를 발급받아
GOOGLE_APPLICATION_CREDENTIALS 환경변수로 경로를 지정하거나,
serviceAccountKey.json을 프로젝트 루트에 둔다(둘 다 .gitignore 대상).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATIONS = [
    {
        "station_id": "station_rooftop_main_01",
        "name": "본관 옥상 실험 1호기",
        "category": "ROOFTOP",
        "building_id": "bldg_main",
        "building_name": "본관",
        "floor": 4,
        "location": {"latitude": 37.3338, "longitude": 127.2555, "altitude_m": 165.0},
        "hardware": {
            "panel_model": "Portable-Solar-30W",
            "rated_power_w": 30.0,
            "surface_area_m2": 0.18,
            "tilt_angle_deg": 30,
            "azimuth_deg": 180,
        },
        "live_status": {
            "state": "GENERATING",
            "power_w": 21.45,
            "voltage_v": 5.12,
            "current_a": 4.19,
            "today_energy_wh": 112.5,
            "temp_c": 34.2,
            "last_updated": "2026-09-04T13:45:00+09:00",
        },
        "telemetry": {"pi_cpu_temp_c": 46.8, "wifi_rssi_dbm": -62},
    },
    {
        "station_id": "station_playground_01",
        "name": "운동장 스탠드 2호기",
        "category": "GROUND",
        "building_id": "bldg_field",
        "building_name": "운동장",
        "floor": 1,
        "location": {"latitude": 37.3345, "longitude": 127.2562, "altitude_m": 150.0},
        "hardware": {
            "panel_model": "Portable-Solar-30W",
            "rated_power_w": 30.0,
            "surface_area_m2": 0.18,
            "tilt_angle_deg": 0,
            "azimuth_deg": 180,
        },
        "live_status": {
            "state": "GENERATING",
            "power_w": 18.20,
            "voltage_v": 5.08,
            "current_a": 3.58,
            "today_energy_wh": 95.8,
            "temp_c": 36.1,
            "last_updated": "2026-09-04T13:45:00+09:00",
        },
        "telemetry": {"pi_cpu_temp_c": 48.1, "wifi_rssi_dbm": -71},
    },
]

CAMPUS_POLYGON = {
    "id": "poly_hafs_measured_full",
    "properties": {
        "building_name": "HAFS 옥상 및 유휴지 (3회 실측 합계)",
        "total_roof_area_m2": 850.0,
        "usable_solar_area_m2": 7612.67,
        "measured_trials_m2": [7606, 7644, 7588],
        "measured_std_m2": 28.59,
        "current_installed_stations": ["station_rooftop_main_01"],
        "potential_capacity_kw": 761.27,
        "monthly_consumption_kwh": 135865.9,
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [127.039600, 37.501100],
                [127.040100, 37.501100],
                [127.040100, 37.501400],
                [127.039600, 37.501400],
                [127.039600, 37.501100],
            ]
        ],
    },
}

SCHOOL_SUMMARY = {
    "date": "2026-09-04",
    "today_total_generation_kwh": 0.208,
    "simulated_full_campus_kwh": 165.0,
    "school_today_consumption_kwh": 420.0,
    "real_contribution_percent": 0.05,
    "simulated_self_sufficiency_percent": 39.3,
    "co2_reduced_kg": 0.0995,
    "tree_planted_equivalent": 0.0045,
    "last_updated": "2026-09-04T13:45:00+09:00",
}


def _seed_with_admin_sdk(project_id: str | None) -> None:
    import firebase_admin
    from firebase_admin import credentials, firestore

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or str(ROOT / "serviceAccountKey.json")
    if not Path(cred_path).exists():
        raise FileNotFoundError(f"서비스 계정 키를 찾을 수 없음: {cred_path}")

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
    db = firestore.client()

    for s in STATIONS:
        db.collection("solar_stations").document(s["station_id"]).set(s)
    db.collection("campus_polygons").document(CAMPUS_POLYGON["id"]).set(CAMPUS_POLYGON)
    db.collection("school_energy_summary").document("latest").set(SCHOOL_SUMMARY)
    print(f"firebase-admin으로 시드 완료: station {len(STATIONS)}개, polygon 1개, summary 1개")


def _seed_with_rest(project_id: str) -> None:
    import urllib.request

    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/datastore"])
    creds.refresh(google.auth.transport.requests.Request())
    token = creds.token

    base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"

    def to_firestore_value(v):
        if isinstance(v, bool):
            return {"booleanValue": v}
        if isinstance(v, int):
            return {"integerValue": str(v)}
        if isinstance(v, float):
            return {"doubleValue": v}
        if isinstance(v, str):
            return {"stringValue": v}
        if isinstance(v, list):
            return {"arrayValue": {"values": [to_firestore_value(x) for x in v]}}
        if isinstance(v, dict):
            return {"mapValue": {"fields": {k: to_firestore_value(x) for k, x in v.items()}}}
        return {"nullValue": None}

    def put_doc(collection: str, doc_id: str, data: dict) -> None:
        body = json.dumps({"fields": {k: to_firestore_value(v) for k, v in data.items()}}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/{collection}/{doc_id}",
            data=body,
            method="PATCH",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            resp.read()

    for s in STATIONS:
        put_doc("solar_stations", s["station_id"], s)
    put_doc("campus_polygons", CAMPUS_POLYGON["id"], CAMPUS_POLYGON)
    put_doc("school_energy_summary", "latest", SCHOOL_SUMMARY)
    print(f"REST API로 시드 완료: station {len(STATIONS)}개, polygon 1개, summary 1개")


def main() -> None:
    firebaserc = ROOT / ".firebaserc"
    project_id = None
    if firebaserc.exists():
        cfg = json.loads(firebaserc.read_text(encoding="utf-8"))
        project_id = cfg.get("projects", {}).get("default")
        if project_id == "REPLACE_WITH_YOUR_PROJECT_ID":
            project_id = None

    if project_id is None:
        print(".firebaserc에 실제 project ID를 설정한 뒤 다시 실행하세요.", file=sys.stderr)
        sys.exit(1)

    try:
        _seed_with_admin_sdk(project_id)
    except ImportError:
        print("firebase-admin 미설치(Python 3.14 휠 부재 등) — REST 경로로 대체합니다.")
        _seed_with_rest(project_id)


if __name__ == "__main__":
    main()
