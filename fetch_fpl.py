"""
Script otomatis untuk menarik data FPL (Fantasy Premier League) resmi
dan menggabungkannya jadi satu file JSON yang mudah dibaca (dengan nama pemain asli,
bukan cuma ID angka).

Cara pakai:
1. Ganti TEAM_ID di bawah dengan Team ID FPL kamu.
2. Jalankan otomatis lewat GitHub Actions (lihat .github/workflows/update.yml)
   atau manual: python fetch_fpl.py
3. Hasilnya tersimpan di data/latest.json
"""

import json
import os
import urllib.request

# ==== KONFIGURASI ====
TEAM_ID = 4182775  # Ganti dengan Team ID kamu jika berbeda
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "latest.json")

BASE_URL = "https://fantasy.premierleague.com/api"


def fetch_json(url: str) -> dict:
    """Ambil dan parse JSON dari URL, dengan header User-Agent agar tidak diblokir."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FPL-Auto-Fetcher/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_current_event(bootstrap: dict) -> int:
    """Cari gameweek terakhir yang sudah selesai (is_finished=True) atau yang sedang berjalan."""
    events = bootstrap["events"]
    current = None
    for e in events:
        if e.get("is_current"):
            current = e["id"]
    if current is None:
        # fallback: cari event terakhir yang sudah finished
        finished = [e["id"] for e in events if e.get("finished")]
        current = max(finished) if finished else 1
    return current


def build_player_lookup(bootstrap: dict) -> dict:
    """Buat dict {element_id: info_pemain} dari data bootstrap-static."""
    teams = {t["id"]: t["name"] for t in bootstrap["teams"]}
    positions = {p["id"]: p["singular_name_short"] for p in bootstrap["element_types"]}

    lookup = {}
    for el in bootstrap["elements"]:
        lookup[el["id"]] = {
            "name": el["web_name"],
            "full_name": f'{el["first_name"]} {el["second_name"]}',
            "team": teams.get(el["team"], "Unknown"),
            "position": positions.get(el["element_type"], "Unknown"),
            "price": el["now_cost"] / 10,  # harga FPL disimpan x10 (mis. 102 = 10.2)
            "form": el.get("form"),
            "total_points": el.get("total_points"),
            "points_per_game": el.get("points_per_game"),
            "selected_by_percent": el.get("selected_by_percent"),
            "status": el.get("status"),  # 'a'=available, 'i'=injured, 'd'=doubtful, 's'=suspended
            "news": el.get("news", ""),
            "chance_of_playing_next_round": el.get("chance_of_playing_next_round"),
            "expected_goal_involvements": el.get("expected_goal_involvements"),
            "expected_goals_conceded": el.get("expected_goals_conceded"),
        }
    return lookup


def build_squad_detail(picks_data: dict, player_lookup: dict) -> list:
    """Gabungkan data picks (ID only) dengan nama & statistik pemain asli."""
    squad = []
    for pick in picks_data["picks"]:
        pid = pick["element"]
        info = player_lookup.get(pid, {})
        squad.append({
            "name": info.get("name", f"Unknown (ID {pid})"),
            "full_name": info.get("full_name"),
            "team": info.get("team"),
            "position": info.get("position"),
            "price": info.get("price"),
            "form": info.get("form"),
            "total_points": info.get("total_points"),
            "status": info.get("status"),
            "news": info.get("news"),
            "is_captain": pick["is_captain"],
            "is_vice_captain": pick["is_vice_captain"],
            "multiplier": pick["multiplier"],
            "in_starting_xi": pick["multiplier"] > 0,
        })
    return squad


def main():
    print("Mengambil data master pemain (bootstrap-static)...")
    bootstrap = fetch_json(f"{BASE_URL}/bootstrap-static/")

    current_event = get_current_event(bootstrap)
    print(f"Gameweek saat ini/terakhir selesai: {current_event}")

    print(f"Mengambil squad Team ID {TEAM_ID} untuk GW{current_event}...")
    picks_data = fetch_json(f"{BASE_URL}/entry/{TEAM_ID}/event/{current_event}/picks/")

    print("Mengambil info entry (rank, total poin, chip, dsb)...")
    entry_info = fetch_json(f"{BASE_URL}/entry/{TEAM_ID}/")

    print("Mencocokkan ID pemain ke nama asli...")
    player_lookup = build_player_lookup(bootstrap)
    squad_detail = build_squad_detail(picks_data, player_lookup)

    result = {
        "team_id": TEAM_ID,
        "team_name": entry_info.get("name"),
        "manager_name": f'{entry_info.get("player_first_name", "")} {entry_info.get("player_last_name", "")}'.strip(),
        "current_event": current_event,
        "entry_history": picks_data.get("entry_history"),
        "active_chip": picks_data.get("active_chip"),
        "chips_used": entry_info.get("chips") or entry_info.get("current"),
        "overall_rank": entry_info.get("summary_overall_rank"),
        "overall_points": entry_info.get("summary_overall_points"),
        "squad": squad_detail,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Selesai. Data tersimpan di {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
