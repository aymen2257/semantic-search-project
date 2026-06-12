import json
import re
import time
import hashlib
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


TARGET_URLS = [
    "https://www.ooredoo.tn/Business/fr/content/242-roaming",
    "https://www.ooredoo.tn/Personal/fr/content/133--roaming",
]

OUT_PATH = Path(r"c:\Users\USER\Desktop\pfe_26\scrape_data\roaming_country_tariffs_selenium.json")

WAIT_SEC = 15
SLEEP_AFTER_SELECT = 0.8


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def normalize_txt(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [clean(x) for x in text.split("\n")]
    lines = [x for x in lines if x]
    return "\n".join(lines).strip()


def to_embedding_text(text: str) -> str:
    return clean(text.replace("\n", " "))


def make_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def classify_url(url: str):
    p = urlsplit(url).path.lower()
    if "/personal/en" in p:
        return "personal", "en"
    if "/personal/fr" in p:
        return "personal", "fr"
    if "/business/en" in p:
        return "business", "en"
    if "/business/fr" in p:
        return "business", "fr"
    return "unknown", "unknown"


def is_placeholder_country(label: str) -> bool:
    return bool(re.search(r"(sélectionner|choisissez|select|choose|country|pays)", label, re.I))


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1600,2200")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def get_page_title(driver):
    try:
        return clean(driver.title)
    except Exception:
        return ""


def find_country_select(driver):
    # explicit selector from your screenshots
    try:
        return WebDriverWait(driver, WAIT_SEC).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select#country"))
        )
    except TimeoutException:
        return None


def find_tariff_container(driver):
    """
    Find the visible block that contains:
    - ZONE
    - Appels vers un numéro Tunisien
    """
    xpath = """
    //*[contains(normalize-space(.), 'Appels vers un numéro Tunisien')
        and contains(normalize-space(.), 'ZONE')]
    """
    candidates = driver.find_elements(By.XPATH, xpath)

    best = None
    best_len = 10**9

    for el in candidates:
        try:
            txt = clean(el.text)
            if txt and len(txt) < best_len:
                best = el
                best_len = len(txt)
        except Exception:
            continue

    return best


def extract_tariff_text(driver):
    container = find_tariff_container(driver)
    if not container:
        return ""
    return normalize_txt(container.text)


def parse_tariff_block(country: str, text: str):
    """
    Parse a block like:
    ZONE 2
    Appels vers un numéro Tunisien
    1.9
    Appels vers un numéro du pays visité
    1.6
    ...
    """
    if not text:
        return None

    text = normalize_txt(text)
    lines = text.split("\n")

    # find zone
    zone = ""
    zone_match = re.search(r"ZONE\s*\d+", text, re.I)
    if zone_match:
        zone = zone_match.group(0).upper()

    # flatten for robust parsing
    joined = " ".join(lines)

    patterns = {
        "calls_to_tunisian_number": r"Appels vers un numéro Tunisien\s+([0-9.]+)",
        "calls_to_visited_country": r"Appels vers un numéro du pays visité\s+([0-9.]+)",
        "calls_received": r"Appels reçus(?:\s*\(.*?\))?\s+([0-9.]+)",
        "sms": r"Envoi des SMS(?:\s*\(.*?\))?\s+([0-9.]+)",
        "roaming_data": r"Roaming Data\s+([0-9.]+)",
        "calls_to_rest_of_world": r"Appels vers le reste du monde\s+([0-9.]+)",
    }

    values = {}
    for key, pat in patterns.items():
        m = re.search(pat, joined, re.I)
        values[key] = m.group(1) if m else ""

    if not zone and not any(values.values()):
        return None

    raw_text = "\n".join([
        f"Country: {country}",
        f"Zone: {zone}",
        f"Calls to Tunisian number: {values['calls_to_tunisian_number']}",
        f"Calls to visited country: {values['calls_to_visited_country']}",
        f"Calls received: {values['calls_received']}",
        f"SMS: {values['sms']}",
        f"Roaming Data: {values['roaming_data']}",
        f"Calls to rest of world: {values['calls_to_rest_of_world']}",
    ]).strip()

    return {
        "country": country,
        "zone": zone,
        "raw_text": raw_text,
        "clean_text": raw_text,
        "embedding_text": to_embedding_text(raw_text),
    }


def select_country_and_wait(driver, select_el, country_value=None, country_text=None, old_snapshot=""):
    sel = Select(select_el)

    if country_value is not None:
        sel.select_by_value(country_value)
    elif country_text is not None:
        sel.select_by_visible_text(country_text)
    else:
        raise ValueError("Need either country_value or country_text")

    time.sleep(SLEEP_AFTER_SELECT)

    def changed(d):
        try:
            current = extract_tariff_text(d)
            return current and current != old_snapshot
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, WAIT_SEC).until(changed)
    except TimeoutException:
        pass


def scrape_url(driver, url):
    section, language = classify_url(url)
    records = []

    driver.get(url)
    WebDriverWait(driver, WAIT_SEC).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(1)

    title = get_page_title(driver)
    select_el = find_country_select(driver)

    if not select_el:
        print(f"[WARN] country select not found: {url}")
        return records

    sel = Select(select_el)
    options = sel.options

    old_snapshot = extract_tariff_text(driver)

    for idx, opt in enumerate(options):
        try:
            label = clean(opt.text)
            value = opt.get_attribute("value")

            if not label or is_placeholder_country(label):
                continue

            # refresh select because DOM may re-render
            select_el = find_country_select(driver)
            if not select_el:
                continue

            select_country_and_wait(
                driver,
                select_el,
                country_value=value if value else None,
                country_text=None if value else label,
                old_snapshot=old_snapshot
            )

            current_snapshot = extract_tariff_text(driver)
            parsed = parse_tariff_block(label, current_snapshot)

            if not parsed:
                continue

            record = {
                "url": url,
                "title": title,
                "http_status": 200,
                "section": section,
                "language": language,
                "page_type": "roaming_tariff_country",
                "country": parsed["country"],
                "zone": parsed["zone"],
                "raw_text": parsed["raw_text"],
                "clean_text": parsed["clean_text"],
                "embedding_text": parsed["embedding_text"],
                "content_hash": make_hash(parsed["embedding_text"]),
                "status": "success",
                "reason": ""
            }

            records.append(record)
            old_snapshot = current_snapshot
            print(f"[OK] {label} -> {parsed['zone']}")

        except Exception as e:
            print(f"[ERR] {url} | option #{idx} | {type(e).__name__}: {e}")

    return records


def dedup_records(records):
    seen = set()
    out = []
    for r in records:
        key = (r["url"], r["country"].lower(), r["zone"], r["content_hash"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def main():
    driver = setup_driver()
    all_records = []

    try:
        for url in TARGET_URLS:
            recs = scrape_url(driver, url)
            all_records.extend(recs)
    finally:
        driver.quit()

    all_records = dedup_records(all_records)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSaved {len(all_records)} records to: {OUT_PATH}")


if __name__ == "__main__":
    main()