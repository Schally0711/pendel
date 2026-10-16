"""Fill an empty Pendel instance with made-up demo data and take the screenshots in docs/images.

Needs Playwright (pip install playwright && playwright install chromium-headless-shell) and a
fresh instance started with a known setup token, e.g. from backend/:

    PENDEL_DATA_DIR=/tmp/pendel-demo PENDEL_SETUP_TOKEN=demo PENDEL_STATIC_DIR=../frontend/build \\
        .venv/bin/uvicorn pendel.main:app --port 8765
    python tools/screenshots.py http://127.0.0.1:8765 demo
"""

import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import APIRequestContext, sync_playwright

TZ = ZoneInfo("Europe/Berlin")
OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
EMAIL, PASSWORD = "alex@example.org", "demo-password-123"
H = {"X-Requested-With": "pendel"}


def at(day: date, hhmm: str, jitter: int = 0) -> str:
    h, m = map(int, hhmm.split(":"))
    t = datetime(day.year, day.month, day.day, h, m, tzinfo=TZ) + timedelta(minutes=jitter)
    return t.isoformat()


def ok(r, what: str):
    if not r.ok:
        raise SystemExit(f"{what}: {r.status} {r.text()}")
    return r.json() if r.status != 204 else None


def seed(api: APIRequestContext, base: str, setup_code: str) -> None:
    rnd = random.Random(7)
    today = datetime.now(TZ).date()
    start = today - timedelta(days=7 * 10 + today.weekday())  # a Monday ten weeks ago
    ok(
        api.post(
            f"{base}/api/setup",
            data={"email": EMAIL, "password": PASSWORD, "display_name": "Alex", "setup_code": setup_code},
            headers=H,
        ),
        "setup",
    )
    emp = ok(api.get(f"{base}/api/employments"), "employments")[0]
    ok(api.put(f"{base}/api/employments/{emp['id']}", data={"employer": "Musterfirma GmbH", "start": "2024-04-01"}, headers=H), "employment")
    model = ok(api.get(f"{base}/api/work-models"), "models")[0]
    ok(api.put(f"{base}/api/work-models/{model['id']}", data={**model, "valid_from": str(start)}, headers=H), "model")
    places = ok(api.get(f"{base}/api/places"), "places")
    home = next(p for p in places if p["kind"] == "home")
    office = next(p for p in places if p["kind"] == "office")
    ok(api.put(f"{base}/api/places/{office['id']}", data={**office, "distance_km": 28}, headers=H), "office")
    ok(api.put(f"{base}/api/places/{home['id']}", data={**home, "distance_km": 0}, headers=H), "home")
    ok(api.put(f"{base}/api/vacation/{today.year}", data={"days": 30, "carried_over": 3}, headers=H), "vacation")

    vacation = (start + timedelta(days=21), start + timedelta(days=25))
    sick = start + timedelta(days=37)
    ok(api.post(f"{base}/api/absences", data={"start": str(vacation[0]), "end": str(vacation[1]), "kind": "vacation", "note": "Ostsee"}, headers=H), "vac")
    ok(api.put(f"{base}/api/days/{sick}", data={"kind": "sick"}, headers=H), "sick")
    future = today + timedelta(days=24)
    ok(api.post(f"{base}/api/absences", data={"start": str(future), "end": str(future + timedelta(days=4)), "kind": "vacation", "note": "Herbstferien"}, headers=H), "future")

    day = start
    while day < today:
        if day.weekday() < 5 and not (vacation[0] <= day <= vacation[1]) and day != sick:
            j = lambda: rnd.randint(-15, 20)  # noqa: E731
            if day.weekday() in (1, 3):  # office on Tuesday and Thursday
                go, arrive = j(), rnd.randint(32, 48)
                ok(api.post(f"{base}/api/commutes", data={"direction": "to_work", "start": at(day, "07:15", go), "end": at(day, "07:15", go + arrive), "from_place_id": home["id"], "to_place_id": office["id"]}, headers=H), "c1")
                end = at(day, "16:20", j() + 20)
                s = ok(api.post(f"{base}/api/sessions", data={"kind": "office", "place_id": office["id"], "start": at(day, "07:15", go + arrive), "end": end}, headers=H), "s")
                b = j()
                ok(api.post(f"{base}/api/sessions/{s['id']}/breaks", data={"start": at(day, "12:05", b), "end": at(day, "12:05", b + rnd.randint(30, 50))}, headers=H), "b")
                back = datetime.fromisoformat(end)
                ok(api.post(f"{base}/api/commutes", data={"direction": "from_work", "start": back.isoformat(), "end": (back + timedelta(minutes=rnd.randint(35, 55))).isoformat(), "from_place_id": office["id"], "to_place_id": home["id"]}, headers=H), "c2")
            else:
                s = ok(api.post(f"{base}/api/sessions", data={"kind": "home", "place_id": home["id"], "start": at(day, "08:00", j()), "end": at(day, "16:40", j())}, headers=H), "s")
                b = j()
                ok(api.post(f"{base}/api/sessions/{s['id']}/breaks", data={"start": at(day, "12:15", b), "end": at(day, "12:15", b + rnd.randint(30, 45))}, headers=H), "b")
        day += timedelta(days=1)

    # today: home office for a while (independent of the time the script runs), with a break
    now = datetime.now(TZ)
    begin = now - timedelta(hours=5, minutes=50)
    s = ok(api.post(f"{base}/api/sessions", data={"kind": "home", "place_id": home["id"], "start": begin.isoformat()}, headers=H), "today")
    ok(api.post(f"{base}/api/sessions/{s['id']}/breaks", data={"start": (begin + timedelta(hours=2)).isoformat(), "end": (begin + timedelta(hours=2, minutes=35)).isoformat()}, headers=H), "today break")


def shoot(base: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    month = datetime.now(TZ).strftime("%Y-%m")
    shots = [
        ("today", "/", None),
        ("history", "/history", None),
        ("absences", "/absences", None),
        ("stats", "/stats", "3 Monate"),
        ("report", f"/report/{month}", None),
        ("settings", "/settings", None),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme, viewport, suffix in (("light", {"width": 1280, "height": 860}, ""), ("dark", {"width": 1280, "height": 860}, "-dark")):
            ctx = browser.new_context(locale="de-DE", color_scheme=scheme, viewport=viewport, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(f"{base}/login")
            page.fill("#email", EMAIL)
            page.fill("#password", PASSWORD)
            page.keyboard.press("Enter")
            page.wait_for_url(f"{base}/")
            for name, path, button in shots:
                if scheme == "dark" and name not in ("today", "stats"):
                    continue
                page.goto(base + path)
                time.sleep(1.5)
                if button:
                    page.get_by_role("button", name=button).click()
                    time.sleep(1.5)
                page.screenshot(path=str(OUT / f"{name}{suffix}.png"))
            ctx.close()
        # phone
        ctx = browser.new_context(locale="de-DE", viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        page.goto(f"{base}/login")
        page.fill("#email", EMAIL)
        page.fill("#password", PASSWORD)
        page.keyboard.press("Enter")
        page.wait_for_url(f"{base}/")
        time.sleep(1.5)
        page.screenshot(path=str(OUT / "mobile-today.png"))
        page.goto(f"{base}/absences")
        time.sleep(1.5)
        page.screenshot(path=str(OUT / "mobile-absences.png"))
        browser.close()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    base, code = sys.argv[1].rstrip("/"), sys.argv[2]
    with sync_playwright() as p:
        api = p.request.new_context()
        seed(api, base, code)
        api.dispose()
    shoot(base)
    print("screenshots written to", OUT)


if __name__ == "__main__":
    main()
