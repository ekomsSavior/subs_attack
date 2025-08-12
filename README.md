# subs_attack — subscription attack tool

by: ekomsSavior and DA3 https://www.instagram.com/desertapple3

subs_attack is a CLI tool that runs an automated subscription attack and it maps fields by label/name/placeholder, fills what it can, and **skips** any form that’s missing required fields or shows a CAPTCHA / anti-bot wall.

* Browsers: Firefox (default) or Chromium
* Driver: handled by Selenium; Firefox ESR works out of the box on Kali
* No CAPTCHAs, no bypassing, no blasting

---                  
                                                                                                                       
![image0(1)](https://github.com/user-attachments/assets/f5287029-803d-410f-98a3-c2f6f03e8f22)
                                                                                                                       

## Install 

```bash
sudo apt update && sudo apt install -y firefox-esr chromium python3-pip wget tar curl
pip3 install --break-system-packages --upgrade selenium
```

> Firefox ESR is the default path. Chromium support is available; if your Chromium needs a driver, Selenium will attempt to manage it automatically. If you prefer the distro driver: `sudo apt install -y chromium-driver`.

---

## Clone

```bash
git clone https://github.com/ekomsSavior/subs_attack.git
cd subs_attack
```

Repo layout (key files):

```
autofill/
├─ subs_attack.py        # main CLI
├─ targets.txt             # your list of websites (one per line)
└─ user_agents.txt         # UA list (one per line)
```

---

## Prepare your data

### 1) the identity (what subs_attack will enter)

Have these handy (provide via CLI flags):

* Name (either `--full-name` **or** `--first-name` + `--last-name`)
* `--email`
* `--phone`
* Optional address fields: `--address1 --address2 --city --state --zip`
* Optional: `--company`, `--notes`

### 2) Target websites list

 `targets.txt` is list of subscription attack websites, you can edit this list:

```
https://example-movers.com/quote
https://some-insurance.com/get-a-quote
https://another-company.com/contact
```

One URL per line. Lines starting with `#` are ignored.

### 3)  User-Agent rotation

update the UA list (if needed) in `user_agents.txt` (repo root), one per line:

```
Mozilla/5.0 (...) Chrome/124.0 Safari/537.36
Mozilla/5.0 (...) Firefox/115.0
...
```

Autofill will randomly rotate UAs if you pass `--user-agents user_agents.txt`.


---

## Run


```bash
python3 subs_attack.py
```

### Watch it live (non-headless)

```bash
python3 subs_attack.py \
  --no-headless
```

### Use Chromium instead of Firefox

```bash
python3 form_autofill.py \
  --browser chromium
```

(If Selenium can’t find a compatible driver on your box, install it: `sudo apt install -y chromium-driver` and rerun. You can also pass explicit paths via `--chromium-binary` and `--chromedriver`.)

---


subs_attack will:

1. Load each URL,
2. Skip if a CAPTCHA/anti-bot wall appears,
3. Find a likely contact/quote form,
4. Map and fill known fields,
5. Submit once if required fields are present (else skip),
6. Log the outcome to `autofill.log`.


## Important switches

* `--required email,phone`
  Comma-list of fields that **must** be present to submit. If any are missing, the form/site is **skipped**. Adjust to your needs (e.g., `--required email,full_name`).

* `--headless / --no-headless`
  Headless is on by default. Use `--no-headless` to observe behavior.

* `--log autofill.log`
  Logs results and per-site decisions.

* `--browser {firefox,chromium}`
  Default is `firefox`. Both are supported.

---

## Behavior & Guardrails

* One polite attempt per site, first reasonable form only.
* If a **CAPTCHA/anti-bot wall** is detected (reCAPTCHA, hCaptcha, Turnstile, Cloudflare “Attention required”, etc.), Autofill **logs and skips**.
* If any **required** fields aren’t confidently mapped/fillable, Autofill **skips**.
* Small random delays and optional UA rotation are used to behave more like a human and avoid hammering pages.

---

## Troubleshooting

* **“No suitable forms”**: The page may be multi-step, behind JS wizards, or fields are unusual. Try `--no-headless` to inspect, or adjust `--required`.
* **Chromium driver errors**: Install `chromium-driver` or let Selenium Manager handle it; re-run the command.
* **State dropdowns**: If your target uses a select box, pass `--state "AZ"` (visible text must match one of the options).

---

## Disclaimer

This tool is for **legitimate, user-consented automation** only.
use only on systems, networks and people you have permission to test on.
USER is responsible for thier own actions and how they use this tool.

