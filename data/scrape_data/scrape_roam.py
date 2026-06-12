import json
import re
import time
import hashlib
import unicodedata
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

OUT_PATH = Path(r"c:\Users\USER\Desktop\pfe_26\scrape_data\roaming_partner_operators_selenium.json")

WAIT_SEC = 15
SLEEP_AFTER_SELECT = 0.8


# -----------------------------
# Helpers
# -----------------------------
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


def normalize_country_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    replacements = {
        "emirats arabes unis": "emirats arabes unis",
        "united arab emirates": "emirats arabes unis",
        "uk": "royaume uni",
        "united kingdom": "royaume uni",
        "great britain": "royaume uni",
        "usa": "usa",
        "united states": "usa",
        "south africa": "afrique du sud",
        "coree du sud": "coree du sud",
        "republique tcheque": "republique tcheque",
        "rd congo": "rd congo",
        "republique democratique du congo": "rd congo",
        "peurto rico": "porto rico",
    }
    return replacements.get(s, s)


def same_country(selected_label: str, row_country: str) -> bool:
    a = normalize_country_name(selected_label)
    b = normalize_country_name(row_country)

    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    return False


def is_placeholder_country(label: str) -> bool:
    return bool(re.search(r"(sélectionner|choisissez|select|choose|country|pays)", label, re.I))


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1600,2400")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def get_page_title(driver):
    try:
        return clean(driver.title)
    except Exception:
        return ""


# -----------------------------
# Explicit selectors for this widget
# -----------------------------
def find_partner_country_select(driver):
    try:
        return WebDriverWait(driver, WAIT_SEC).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select#pays"))
        )
    except TimeoutException:
        return None


def find_partner_table(driver):
    try:
        return driver.find_element(By.CSS_SELECTOR, "table.dataTable")
    except Exception:
        return None


def extract_partner_table_text(driver):
    table = find_partner_table(driver)
    if not table:
        return ""
    return normalize_txt(table.text)


def parse_partner_table(country_label: str, table_text: str):
    """
    Parse a table like:
    Nom Opérateur  Pays   Type Roaming
    Orange         France 4G
    SFR            France Prépayé
    ...
    """
    if not table_text:
        return None

    lines = [clean(x) for x in table_text.split("\n") if clean(x)]
    if not lines:
        return None

    records = []
    seen = set()

    for line in lines:
        low = line.lower()

        # skip headers
        if "nom opérateur" in low or "operator" in low:
            continue
        if "type roaming" in low:
            continue
        if low == normalize_country_name(low):
            pass

        # split by multiple spaces first
        parts = re.split(r"\s{2,}", line)
        parts = [clean(p) for p in parts if clean(p)]

        # fallback if table collapses into single-spaced text
        if len(parts) < 3:
            tokens = line.split()
            if len(tokens) >= 3:
                roaming_type = tokens[-1]
                country = tokens[-2]
                operator = " ".join(tokens[:-2])
                parts = [operator, country, roaming_type]

        if len(parts) < 3:
            continue

        operator = parts[0]
        country = parts[1]
        roaming_type = " ".join(parts[2:])

        if not same_country(country_label, country):
            continue

        key = (operator.lower(), country.lower(), roaming_type.lower())
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "operator": operator,
            "country": country,
            "roaming_type": roaming_type
        })

    if not records:
        return None

    raw_lines = [f"Country: {country_label}"]
    for r in records:
        raw_lines.append(
            f"Operator: {r['operator']} | Country: {r['country']} | Roaming Type: {r['roaming_type']}"
        )

    raw_text = "\n".join(raw_lines).strip()

    return {
        "country": country_label,
        "raw_text": raw_text,
        "clean_text": raw_text,
        "embedding_text": to_embedding_text(raw_text),
        "rows": records
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

    # trigger JS listeners explicitly
    driver.execute_script("""
        const sel = document.querySelector('select#pays');
        if (sel) {
            sel.dispatchEvent(new Event('input', { bubbles: true }));
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }
    """)

    time.sleep(SLEEP_AFTER_SELECT)

    def changed(d):
        try:
            current = extract_partner_table_text(d)
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
    select_el = find_partner_country_select(driver)

    if not select_el:
        print(f"[WARN] partner country select not found: {url}")
        return records

    sel = Select(select_el)
    options = sel.options

    old_snapshot = extract_partner_table_text(driver)

    for idx, opt in enumerate(options):
        try:
            label = clean(opt.text)
            value = opt.get_attribute("value")

            if not label or is_placeholder_country(label):
                continue

            # refresh select because DOM may rerender
            select_el = find_partner_country_select(driver)
            if not select_el:
                continue

            select_country_and_wait(
                driver,
                select_el,
                country_value=value if value else None,
                country_text=None if value else label,
                old_snapshot=old_snapshot
            )

            current_snapshot = extract_partner_table_text(driver)
            parsed = parse_partner_table(label, current_snapshot)

            if not parsed:
                continue

            record = {
                "url": url,
                "title": title,
                "http_status": 200,
                "section": section,
                "language": language,
                "page_type": "roaming_partner_operators",
                "country": parsed["country"],
                "raw_text": parsed["raw_text"],
                "clean_text": parsed["clean_text"],
                "embedding_text": parsed["embedding_text"],
                "content_hash": make_hash(parsed["embedding_text"]),
                "status": "success",
                "reason": ""
            }

            records.append(record)
            old_snapshot = current_snapshot
            print(f"[OK] {label} -> {len(parsed['rows'])} operator rows")

        except Exception as e:
            print(f"[ERR] {url} | option #{idx} | {type(e).__name__}: {e}")

    return records


def dedup_records(records):
    seen = set()
    out = []
    for r in records:
        key = (r["url"], r["country"].lower(), r["content_hash"])
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