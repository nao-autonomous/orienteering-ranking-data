#!/usr/bin/env python3
"""
Fetch IOF + JOA rankings and update data/ directory with index.json.
Designed to run in GitHub Actions for automated weekly updates.
"""

import csv
import io
import json
import os
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

# --- Config ---

IOF_API_BASE = "https://ranking.orienteering.org/api/wrs"
JOA_BASE = "https://japan-o-entry.com/ranking/ranking/ranking_index"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

IOF_DISCIPLINE_MAP = {"foot": "F", "sprint": "FS"}
IOF_GROUP_MAP = {"M": "MEN", "W": "WOMEN"}
DISCIPLINE_DISPLAY = {"foot": "FootO", "sprint": "Sprint"}

JOA_CATEGORIES = {
    ("foot", "M"): (5, 39),
    ("foot", "W"): (5, 46),
    ("sprint", "M"): (17, 85),
    ("sprint", "W"): (17, 86),
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "OrienteeringRankingBot/1.0"})


# --- IOF ---

def fetch_iof(discipline: str, gender: str) -> dict:
    disc_code = IOF_DISCIPLINE_MAP[discipline]
    group_code = IOF_GROUP_MAP[gender]
    url = f"{IOF_API_BASE}/{disc_code}?group={group_code}"

    print(f"  IOF {discipline}/{gender}: {url}")
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    athletes = []
    for entry in data:
        first = entry.get("firstName", "") or ""
        last = entry.get("lastName", "") or ""
        athletes.append({
            "rank": entry.get("pos") or entry.get("wrsPosition") or 0,
            "name": f"{last} {first}".strip(),
            "nameJa": "",
            "club": "",
            "country": (entry.get("country", "") or "").upper(),
            "points": float(entry.get("points") or 0),
            "iofId": entry.get("iofid") or entry.get("personId") or 0,
        })

    athletes.sort(key=lambda a: a["rank"] or 99999)
    today_str = date.today().isoformat()
    return {
        "source": "IOF",
        "discipline": DISCIPLINE_DISPLAY[discipline],
        "gender": gender,
        "date": today_str,
        "fetchedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "athletes": athletes,
    }


# --- JOA ---

def fetch_joa_page(category: int, subcategory: int, page: int = 0):
    if page == 0:
        url = f"{JOA_BASE}/{category}/{subcategory}"
    else:
        url = f"{JOA_BASE}/{category}/{subcategory}/{page}"

    print(f"  JOA page {page}: {url}")
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="ranking_table")
    if not table:
        return [], False

    athletes = []
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        rank_text = cols[0].get_text(strip=True)
        name = cols[1].get_text(strip=True)
        club = cols[2].get_text(strip=True)
        points_text = cols[3].get_text(strip=True)
        try:
            rank = int(rank_text)
        except (ValueError, TypeError):
            rank = 0
        try:
            points = float(points_text.replace(",", ""))
        except (ValueError, TypeError):
            points = 0.0
        if name:
            athletes.append({
                "rank": rank, "name": name, "nameJa": name,
                "club": club, "points": points,
            })

    has_next = False
    next_suffix = f"/{category}/{subcategory}/{page + 1}"
    for link in soup.find_all("a", href=True):
        if link["href"].endswith(next_suffix):
            has_next = True
            break

    return athletes, has_next


def fetch_joa(discipline: str, gender: str) -> dict:
    key = (discipline, gender)
    if key not in JOA_CATEGORIES:
        return None
    category, subcategory = JOA_CATEGORIES[key]

    print(f"  JOA {discipline}/{gender}")
    all_athletes = []
    page = 0
    while page <= 50:
        athletes, has_next = fetch_joa_page(category, subcategory, page)
        all_athletes.extend(athletes)
        if not has_next or not athletes:
            break
        page += 1

    return {
        "source": "JOA",
        "discipline": DISCIPLINE_DISPLAY[discipline],
        "gender": gender,
        "date": date.today().isoformat(),
        "fetchedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "athletes": all_athletes,
    }


# --- Main ---

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str = date.today().isoformat()

    # Load existing index
    index_path = os.path.join(DATA_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path) as f:
            index = json.load(f)
    else:
        index = {"latestDate": "", "dates": {}}

    date_entry = {
        "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }

    saved = []

    for discipline in ["foot", "sprint"]:
        for gender in ["M", "W"]:
            g = gender.lower()

            # IOF
            try:
                iof_data = fetch_iof(discipline, gender)
                iof_file = f"iof_{discipline}_{g}_{today_str}.json"
                iof_path = os.path.join(DATA_DIR, iof_file)
                with open(iof_path, "w", encoding="utf-8") as f:
                    json.dump(iof_data, f, ensure_ascii=False, indent=2)
                date_entry[f"iof_{discipline}_{g}"] = {
                    "file": iof_file,
                    "count": len(iof_data["athletes"]),
                }
                saved.append((iof_file, len(iof_data["athletes"])))
                print(f"    -> {iof_file}: {len(iof_data['athletes'])} athletes")
            except Exception as e:
                print(f"    IOF {discipline}/{gender} error: {e}")

            # JOA
            try:
                joa_data = fetch_joa(discipline, gender)
                if joa_data is None:
                    continue
                joa_date = joa_data["date"]
                joa_file = f"joa_{discipline}_{g}_{joa_date}.json"
                joa_path = os.path.join(DATA_DIR, joa_file)
                with open(joa_path, "w", encoding="utf-8") as f:
                    json.dump(joa_data, f, ensure_ascii=False, indent=2)
                date_entry[f"joa_{discipline}_{g}"] = {
                    "file": joa_file,
                    "count": len(joa_data["athletes"]),
                }
                saved.append((joa_file, len(joa_data["athletes"])))
                print(f"    -> {joa_file}: {len(joa_data['athletes'])} athletes")
            except Exception as e:
                print(f"    JOA {discipline}/{gender} error: {e}")

    # Update index
    index["latestDate"] = today_str
    index["dates"][today_str] = date_entry

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # Update latest.json (copy of index for quick access)
    latest_path = os.path.join(DATA_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nDone: {len(saved)} files, {sum(c for _, c in saved)} total athletes")


if __name__ == "__main__":
    main()
