#!/usr/bin/env python3
import argparse, random, time, sys, os, re, logging, pathlib, json, socket
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, ElementNotInteractableException,
    WebDriverException, StaleElementReferenceException
)
from selenium.webdriver.firefox.options import Options as FxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions

# === Paths / defaults ===
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_UA_FILE = SCRIPT_DIR / "user_agents.txt"
DEFAULT_TARGETS_FILE = SCRIPT_DIR / "targets.txt"
PROFILE_JSON = SCRIPT_DIR / "profile.json"
LOG_FILE = SCRIPT_DIR / "autofill.log"

# === Banner ===
def print_banner():
    banner = r"""
                      ░██                                             ░██       ░██                          ░██          
                      ░██                                             ░██       ░██                          ░██          
 ░███████  ░██    ░██ ░████████   ░███████               ░██████   ░████████ ░████████  ░██████    ░███████  ░██    ░██   
░██        ░██    ░██ ░██    ░██ ░██                          ░██     ░██       ░██          ░██  ░██    ░██ ░██   ░██    
 ░███████  ░██    ░██ ░██    ░██  ░███████               ░███████     ░██       ░██     ░███████  ░██        ░███████     
       ░██ ░██   ░███ ░███   ░██        ░██             ░██   ░██     ░██       ░██    ░██   ░██  ░██    ░██ ░██   ░██    
 ░███████   ░█████░██ ░██░█████   ░███████  ░██████████  ░█████░██     ░████     ░████  ░█████░██  ░███████  ░██    ░██   

    """
    print(banner)

# --------- Field matching heuristics ---------
FIELD_PATTERNS = {
    "first_name":  re.compile(r"\b(first|given)\b.*\bname\b|\bfname\b", re.I),
    "last_name":   re.compile(r"\b(last|family|surname)\b.*\bname\b|\blname\b", re.I),
    "full_name":   re.compile(r"\b(full|your)?\s*name\b", re.I),
    "email":       re.compile(r"\bemail\b|\be-mail\b", re.I),
    "phone":       re.compile(r"\bphone\b|\bmobile\b|\bcell\b|\btelephone\b|\btel\b", re.I),
    "address1":    re.compile(r"\b(address( line)? 1|street|addr1)\b", re.I),
    "address2":    re.compile(r"\b(address( line)? 2|apt|suite|unit|addr2)\b", re.I),
    "city":        re.compile(r"\bcity\b|\btown\b", re.I),
    "state":       re.compile(r"\bstate\b|\bprovince\b|\bregion\b", re.I),
    "zip":         re.compile(r"\bzip\b|\bpostal\b|\bpostcode\b", re.I),
    "company":     re.compile(r"\bcompany\b|\borganization\b|\borg\b|\bbusiness\b", re.I),
    "notes":       re.compile(r"\bnotes?\b|\bcomments?\b|\bmessage\b", re.I),
}
BUTTON_PATTERNS = re.compile(r"\b(submit|send|continue|quote|start|get|next|go|request)\b", re.I)

# --------- Data model ---------
@dataclass
class Profile:
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = "Contacting for a quote. Please email me details. Thank you!"

    def complete_names(self):
        if not self.full_name and (self.first_name or self.last_name):
            parts = [p for p in [self.first_name, self.last_name] if p]
            self.full_name = " ".join(parts) if parts else None
        if (not self.first_name or not self.last_name) and self.full_name:
            parts = self.full_name.split()
            if parts:
                self.first_name = self.first_name or parts[0]
                if len(parts) > 1:
                    self.last_name = self.last_name or " ".join(parts[1:])

    def as_dict(self) -> Dict[str, str]:
        d = {k: v for k, v in self.__dict__.items() if v}
        if "address" not in d and self.address1:
            d["address"] = self.address1
        return d

# --------- Utilities ---------
def read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]

def load_user_agents_default() -> List[str]:
    return read_lines(str(DEFAULT_UA_FILE)) if DEFAULT_UA_FILE.exists() else []

def load_targets_default() -> List[str]:
    return read_lines(str(DEFAULT_TARGETS_FILE)) if DEFAULT_TARGETS_FILE.exists() else []

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE.as_posix()), logging.StreamHandler(sys.stdout)]
    )

# --------- Prompts & persistence ---------
def prompt_input(label: str, default: Optional[str]=None) -> Optional[str]:
    prompt = f"{label}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    val = input(prompt).strip()
    return val or default

def get_or_create_profile() -> Profile:
    data = {}
    if PROFILE_JSON.exists():
        try:
            with PROFILE_JSON.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    print("\n[ Profile ] Enter your info (leave blank to keep current value)")
    first_name = prompt_input("First name", data.get("first_name"))
    last_name  = prompt_input("Last name",  data.get("last_name"))
    full_name  = prompt_input("Full name",  data.get("full_name"))
    email      = prompt_input("Email",      data.get("email"))
    phone      = prompt_input("Phone",      data.get("phone"))
    address1   = prompt_input("Address line 1", data.get("address1"))
    address2   = prompt_input("Address line 2", data.get("address2"))
    city       = prompt_input("City",       data.get("city"))
    state      = prompt_input("State/Province", data.get("state"))
    zipc       = prompt_input("ZIP/Postal", data.get("zip"))
    company    = prompt_input("Company",    data.get("company"))
    notes      = prompt_input("Message/Notes", data.get("notes") or "Contacting for a quote. Please email me details. Thank you!")
    prof = Profile(first_name, last_name, full_name, email, phone, address1, address2, city, state, zipc, company, notes)
    prof.complete_names()
    try:
        with PROFILE_JSON.open("w", encoding="utf-8") as f:
            json.dump(prof.__dict__, f, indent=2)
        print(f"[✓] Saved profile to {PROFILE_JSON.name}\n")
    except Exception:
        print("[!] Could not save profile.json (continuing)")
    return prof

def ensure_targets() -> List[str]:
    urls = load_targets_default()
    if urls:
        return urls
    print(f"\n[ Targets ] No {DEFAULT_TARGETS_FILE.name} found. Paste URLs (one per line). Finish with an empty line:")
    lines = []
    while True:
        ln = input().strip()
        if not ln:
            break
        lines.append(ln)
    if not lines:
        print("[!] No targets provided. Exiting.")
        sys.exit(1)
    try:
        with DEFAULT_TARGETS_FILE.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[✓] Saved {len(lines)} targets to {DEFAULT_TARGETS_FILE.name}\n")
    except Exception:
        print("[!] Could not save targets.txt (continuing with in-memory list)")
    return lines

# --------- UA rotation (automatic) ---------
def pick_user_agent(pool: List[str]) -> Optional[str]:
    return random.choice(pool) if pool else None

# --- Engine-aware UA selection (NEW) ---
UA_FIREFOX_PAT        = re.compile(r"\bFirefox/\d+", re.I)
UA_CHROMIUM_PAT       = re.compile(r"\b(Chrome/\d+|Edg/\d+)\b", re.I)
UA_SAFARI_DESKTOP_PAT = re.compile(r"\bVersion/\d+(\.\d+)? Safari/\d+\b", re.I)
UA_IOS_SAFARI_PAT     = re.compile(r"\biPhone|\biPad", re.I)

def pick_engine_compatible_ua(pool: List[str], browser: str) -> Optional[str]:
    """Prefer UAs that match the actual engine to reduce bot walls and DOM drift."""
    if not pool:
        return None
    b = (browser or "").lower()
    shuffled = pool[:]  # copy
    random.shuffle(shuffled)

    if b == "firefox":
        # Prefer Firefox UAs
        for ua in shuffled:
            if UA_FIREFOX_PAT.search(ua):
                return ua
        # As a last resort, take anything non-Chromium Safari (rare)
        for ua in shuffled:
            if not UA_CHROMIUM_PAT.search(ua):
                return ua
        return shuffled[0]

    # Chromium path: prefer Chrome/Edge UAs (not Firefox)
    for ua in shuffled:
        if UA_CHROMIUM_PAT.search(ua) and not UA_FIREFOX_PAT.search(ua):
            return ua
    # If none found, allow Safari desktop/iOS as fallback (not ideal but better than nothing)
    for ua in shuffled:
        if UA_SAFARI_DESKTOP_PAT.search(ua) or UA_IOS_SAFARI_PAT.search(ua):
            return ua
    return shuffled[0]

# --------- Tor detection ---------
def is_tor_listening(host: str, port: int, timeout: float = 0.75) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

# --------- Browser selection (headless only) ---------
def make_driver(browser: str, ua: Optional[str], timeout: int,
                use_tor: bool, tor_host: str, tor_port: int,
                chromium_binary: Optional[str]=None, chromedriver_path: Optional[str]=None):
    browser = browser.lower()

    if browser == "chromium":
        opts = ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        if ua:
            opts.add_argument(f"--user-agent={ua}")
        if chromium_binary:
            opts.binary_location = chromium_binary
        # light stealth
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        # Tor via SOCKS5
        if use_tor:
            opts.add_argument(f"--proxy-server=socks5://{tor_host}:{tor_port}")

        drv = webdriver.Chrome(options=opts)
        drv.set_page_load_timeout(timeout)
        drv.implicitly_wait(2)
        return drv

    # default: firefox
    fx = FxOptions()
    fx.add_argument("--headless")
    if ua:
        fx.set_preference("general.useragent.override", ua)
    fx.set_preference("dom.webdriver.enabled", False)

    if use_tor:
        # SOCKS5 proxy w/ remote DNS
        fx.set_preference("network.proxy.type", 1)  # manual
        fx.set_preference("network.proxy.socks", tor_host)
        fx.set_preference("network.proxy.socks_port", tor_port)
        fx.set_preference("network.proxy.socks_version", 5)
        fx.set_preference("network.proxy.socks_remote_dns", True)

    drv = webdriver.Firefox(options=fx)
    drv.set_page_load_timeout(timeout)
    drv.implicitly_wait(2)
    return drv

# --------- CAPTCHA / bot-wall detection ---------
CAPTCHA_IFRAME_PAT = re.compile(r"(google\.com/recaptcha|gstatic\.com/recaptcha|hcaptcha\.com|newassets\.hcaptcha\.com|challenges\.cloudflare\.com|turnstile\.js)", re.I)
CAPTCHA_TEXT_PAT = re.compile(r"(i'?m not a robot|select all images|hcaptcha|recaptcha|turnstile|human verification|attention required|verify you are human)", re.I)

def page_has_captcha(drv) -> bool:
    try:
        if drv.find_elements(By.CSS_SELECTOR, ".g-recaptcha, #g-recaptcha, .h-captcha, #cf-challenge"):
            return True
        for f in drv.find_elements(By.TAG_NAME, "iframe"):
            src = (f.get_attribute("src") or "") + " " + (f.get_attribute("data-src") or "")
            if CAPTCHA_IFRAME_PAT.search(src):
                return True
        html = (drv.page_source or "")[:200000]
        if CAPTCHA_TEXT_PAT.search(html):
            return True
    except Exception:
        pass
    return False

def cloudflare_blocked(drv) -> bool:
    try:
        title = (drv.title or "").lower()
        if "just a moment" in title or "attention required" in title:
            return True
        html = (drv.page_source or "").lower()
        if "cloudflare" in html and ("checking your browser" in html or "verify you are human" in html):
            return True
    except Exception:
        pass
    return False

# --------- Form logic ---------
def label_text_for(drv, el) -> str:
    try:
        el_id = el.get_attribute("id")
        if el_id:
            lbl = drv.find_element(By.CSS_SELECTOR, f"label[for='{el_id}']")
            txt = lbl.text.strip()
            if txt: return txt
    except Exception:
        pass
    try:
        parent = el.find_element(By.XPATH, "./ancestor::label[1]")
        txt = parent.text.strip()
        if txt: return txt
    except Exception:
        pass
    return ""

def match_field(field_key: str, label: str, attrs: Dict[str,str]) -> bool:
    pat = FIELD_PATTERNS[field_key]
    hay = " ".join(filter(None, [label] + list(attrs.values())))
    return bool(pat.search(hay))

def fill_input(el, value: str):
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(value)

def try_select(el, value: str) -> bool:
    try:
        Select(el).select_by_visible_text(value)
        return True
    except Exception:
        try:
            sel = Select(el)
            for opt in sel.options:
                if opt.text.strip().lower() == value.strip().lower():
                    sel.select_by_visible_text(opt.text)
                    return True
        except Exception:
            pass
    return False

def submit_form(form) -> bool:
    buttons = form.find_elements(By.CSS_SELECTOR, "button, input[type=submit]")
    for b in buttons:
        try:
            bt = (b.text or "").strip()
            bname = (b.get_attribute("name") or "") + " " + (b.get_attribute("value") or "")
            if BUTTON_PATTERNS.search(bt) or BUTTON_PATTERNS.search(bname) or b.tag_name == "input":
                b.click()
                return True
        except Exception:
            continue
    try:
        any_text = form.find_element(By.CSS_SELECTOR, "input[type=text], input:not([type]), textarea")
        any_text.send_keys(Keys.ENTER)
        return True
    except Exception:
        return False

def visible(el) -> bool:
    try:
        return el.is_displayed() and el.is_enabled()
    except Exception:
        return False

def fill_best_form(drv, prof: Profile, required_keys: List[str], per_site_wait: int) -> Tuple[bool,str]:
    if page_has_captcha(drv) or cloudflare_blocked(drv):
        return (False, "CAPTCHA or anti-bot wall detected; skipping")

    forms = drv.find_elements(By.TAG_NAME, "form")
    if not forms:
        return (False, "No forms found")

    profile_dict = prof.as_dict()
    for idx, form in enumerate(forms[:3]):  # avoid multi-submit
        try:
            if form.find_elements(By.CSS_SELECTOR, ".g-recaptcha, .h-captcha, #cf-challenge"):
                continue

            inputs = form.find_elements(By.CSS_SELECTOR, "input, textarea, select")
            if not inputs:
                continue

            found_map, missing_required = {}, set(required_keys)

            for el in inputs:
                if not visible(el):
                    continue
                tag = el.tag_name.lower()
                etype = (el.get_attribute("type") or "").lower()
                attrs = {
                    "name": (el.get_attribute("name") or ""),
                    "id": (el.get_attribute("id") or ""),
                    "placeholder": (el.get_attribute("placeholder") or ""),
                    "aria_label": (el.get_attribute("aria-label") or ""),
                    "type": etype
                }
                label_txt = label_text_for(drv, el)

                if tag == "input" and etype in ("submit", "button", "reset", "image", "file", "search"):
                    continue

                target_key = None
                for key in ("first_name","last_name","full_name","email","phone",
                            "address1","address2","city","state","zip","company","notes"):
                    if match_field(key, label_txt, attrs):
                        target_key = key
                        break

                if not target_key:
                    hay = " ".join([*attrs.values(), label_txt])
                    if re.search(r"\bname\b", hay, re.I) and ("full_name" in profile_dict or "first_name" in profile_dict):
                        target_key = "full_name" if profile_dict.get("full_name") else "first_name"
                    elif re.search(r"\bmessage|comment|note\b", hay, re.I):
                        target_key = "notes"

                if not target_key:
                    continue

                value = profile_dict.get(target_key)
                if not value:
                    if target_key in ("first_name","last_name") and profile_dict.get("full_name"):
                        parts = profile_dict["full_name"].split()
                        if target_key == "first_name" and parts:
                            value = parts[0]
                        elif target_key == "last_name" and len(parts) > 1:
                            value = " ".join(parts[1:])
                    else:
                        continue

                try:
                    if tag == "select":
                        if not try_select(el, value):
                            continue
                    else:
                        fill_input(el, value)
                    found_map[target_key] = value
                    if target_key in missing_required:
                        missing_required.remove(target_key)
                except (ElementNotInteractableException, StaleElementReferenceException):
                    continue

            if missing_required:
                continue

            if page_has_captcha(drv) or cloudflare_blocked(drv):
                return (False, "CAPTCHA appeared pre-submit; skipping")

            clicked = submit_form(form)
            if not clicked:
                continue

            url_before = drv.current_url
            try:
                WebDriverWait(drv, 6).until(EC.url_changes(url_before))
                return (True, "Submitted (URL changed).")
            except TimeoutException:
                page_text = (drv.page_source or "")[:20000]
                if re.search(r"(thank you|thanks|received|we'll be in touch|success)", page_text, re.I):
                    return (True, "Submitted (confirmation text).")
                time.sleep(2)
                return (True, "Submitted (no confirmation detected).")
        except Exception:
            continue
    return (False, "No suitable forms matched required fields")

# --------- Main ---------
def main():
    print_banner()
    setup_logger()

    # Optional power flags (identity & targets are handled automatically)
    ap = argparse.ArgumentParser(description="Polite Form Autofiller (Kali-ready)", add_help=True)
    ap.add_argument("--browser", choices=["firefox","chromium"], default="firefox", help="Browser engine (default: firefox)")
    ap.add_argument("--timeout", type=int, default=20, help="Page load timeout")
    ap.add_argument("--per-site-wait", type=int, default=10, help="Seconds to wait post-submit")
    ap.add_argument("--min-delay", type=float, default=2.5, help="Min delay between sites")
    ap.add_argument("--max-delay", type=float, default=6.0, help="Max delay between sites")
    ap.add_argument("--chromium-binary", help="Path to chromium binary (optional)")
    ap.add_argument("--chromedriver", help="Path to chromedriver (optional)")
    # Tor controls (all optional, defaults to auto-detect)
    ap.add_argument("--tor", action="store_true", help="Force Tor (error if not listening on host/port)")
    ap.add_argument("--no-tor", action="store_true", help="Disable Tor even if detected")
    ap.add_argument("--tor-host", default="127.0.0.1", help="Tor SOCKS host (default: 127.0.0.1)")
    ap.add_argument("--tor-port", type=int, default=9050, help="Tor SOCKS port (default: 9050)")
    ns = ap.parse_args()

    # Targets
    urls = ensure_targets()
    total = len(urls)
    logging.info(f"[Init] Loaded {total} targets from {DEFAULT_TARGETS_FILE.name}")

    # Profile
    profile = get_or_create_profile()

    # UA rotation
    ua_pool = load_user_agents_default()
    if ua_pool:
        logging.info(f"[Init] UA rotation enabled ({len(ua_pool)} entries from {DEFAULT_UA_FILE.name})")
    else:
        logging.info("[Init] No user_agents.txt found. Using browser default UA.")

    # Tor mode
    tor_available = is_tor_listening(ns.tor_host, ns.tor_port)
    if ns.no_tor:
        use_tor = False
        logging.info("[Init] Tor disabled by flag.")
    elif ns.tor:
        if not tor_available:
            logging.error(f"[Init] --tor requested but no Tor at {ns.tor_host}:{ns.tor_port}. Start Tor or adjust --tor-host/--tor-port.")
            sys.exit(1)
        use_tor = True
        logging.info(f"[Init] Tor enabled (forced) via SOCKS5 {ns.tor_host}:{ns.tor_port}")
    else:
        use_tor = tor_available
        if use_tor:
            logging.info(f"[Init] Tor detected; routing via SOCKS5 {ns.tor_host}:{ns.tor_port}")
        else:
            logging.info("[Init] Tor not detected; connecting directly.")

    required_keys = ["email", "phone"]  # sensible default

    ok = skipped = errors = 0
    for i, url in enumerate(urls, 1):
        # Use engine-aware UA selection
        ua = pick_engine_compatible_ua(ua_pool, ns.browser) if ua_pool else None
        if not ua and ua_pool:
            # Shouldn't happen, but log just in case
            logging.warning("[UA] No engine-compatible UA found; falling back to random.")
            ua = pick_user_agent(ua_pool)

        label = urlparse(url).netloc or url
        ua_lab = ua or "default"
        net_lab = "Tor" if use_tor else "Direct"
        logging.info(f"[{i}/{total}] Visiting {url} | {ns.browser} | UA={ua_lab} | Net={net_lab}")

        try:
            drv = make_driver(ns.browser, ua=ua, timeout=ns.timeout,
                              use_tor=use_tor, tor_host=ns.tor_host, tor_port=ns.tor_port,
                              chromium_binary=ns.chromium_binary, chromedriver_path=ns.chromedriver)
        except WebDriverException as e:
            logging.error(f"[{label}] WebDriver error: {e}")
            errors += 1
            continue

        try:
            drv.get(url)

            if page_has_captcha(drv) or cloudflare_blocked(drv):
                logging.info(f"[{label}] CAPTCHA/anti-bot detected on load; skipping")
                skipped += 1
            else:
                try:
                    WebDriverWait(drv, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "form, input, textarea, button"))
                    )
                except TimeoutException:
                    pass

                submitted, msg = fill_best_form(drv, profile, required_keys, ns.per_site_wait)
                if submitted:
                    logging.info(f"[{label}] {msg}")
                    ok += 1
                else:
                    logging.info(f"[{label}] Skipped: {msg}")
                    skipped += 1
        except TimeoutException:
            logging.warning(f"[{label}] Timeout loading page.")
            skipped += 1
        except Exception as e:
            logging.exception(f"[{label}] Error: {e}")
            errors += 1
        finally:
            try:
                drv.quit()
            except Exception:
                pass

        time.sleep(random.uniform(ns.min_delay, ns.max_delay))

    logging.info(f"Done. Submitted={ok}, Skipped={skipped}, Errors={errors}")

if __name__ == "__main__":
    main()
