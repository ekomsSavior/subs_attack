# subs_attack — subscription attack tool

by: ekomsSavior and DA3 

subs_attack is a CLI tool that runs an automated subscription sign-up attack.
This tool supports Tor routing.

---                  
                                                                                                                       
![image0(1)](https://github.com/user-attachments/assets/f5287029-803d-410f-98a3-c2f6f03e8f22)
                                                                                                                       

## Install 

```bash
sudo apt update && sudo apt install -y tor firefox-esr chromium python3-pip wget tar curl
pip3 install --break-system-packages --upgrade selenium
```

> Firefox is the default path. Chromium support is available; if your Chromium needs a driver, Selenium will attempt to manage it automatically. 
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

 `targets.txt` is list of subscription attack websites, you have to edit this list with your prefered sub urls:

```
https://example-movers.com/quote
https://some-insurance.com/get-a-quote
https://another-company.com/contact
```

One URL per line. Lines starting with `#` are ignored.

Tip: for each website you list make sure to provide the url that lands on the submisson form you want subs_attack to fill.

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

Start Tor:

```bash
sudo systemctl start tor@default
```
run subs_attack:

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

### Tor sometimes triggers bot-walls; for non-tor flows, try:
```bash
python3 form_autofill.py --browser chromium --no-tor
```

---


subs_attack will:

1.  Route everything thru Tor
2. Load each URL from your edited `targets.txt` 
3. Skip if a CAPTCHA/anti-bot wall appears,
4. Find a likely contact/quote form,
5. Map and fill known fields,
6. Submit once if required fields are present (else skip),
7. Log the outcome to `autofill.log`.


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

* One polite attempt per site.
* If a **CAPTCHA/anti-bot wall** is detected (reCAPTCHA, hCaptcha, Turnstile, Cloudflare “Attention required”, etc.), Autofill **logs and skips**.
* If any **required** fields aren’t confidently mapped/fillable, Autofill **skips**.
* Small random delays and optional UA rotation are used to behave more like a human and avoid hammering pages.

---

## Troubleshooting

* ** Tor sometimes triggers bot-walls; for legit flows, try:
```bash
python3 form_autofill.py --browser chromium --no-tor
```
* **“No suitable forms”**: The page may be multi-step, behind JS wizards, or fields are unusual. Try `--no-headless` to inspect, or adjust `--required`.
* **Chromium driver errors**: Install `chromium-driver` or let Selenium Manager handle it; re-run the command.
* **State dropdowns**: If your target uses a select box, pass `--state "AZ"` (visible text must match one of the options).

---

## Disclaimer

This tool is for **legitimate, user-consented automation** only.
use only on systems, networks and people you have permission to test on.
USER is responsible for thier own actions and how they use this tool.

![image0(1)](https://github.com/user-attachments/assets/f925450d-1c44-47aa-9571-fcb3d0eda9fc)

brought to you by: ekomsSavior and DA3

