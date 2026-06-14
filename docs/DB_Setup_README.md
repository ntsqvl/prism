# Database Setup Guide
**Vendor Governance Platform — From Laragon to Digital Ocean**

---

## Part 1: Installing Laragon

### Step 1 — Download Laragon
- Go to: https://laragon.org/download/
- Download the **Full version** (`laragon-full.exe`)
- Run the installer, use default settings
- > **Note:** Install to `C:\laragon` — avoid paths with spaces

### Step 2 — Launch Laragon
- Open Laragon from the desktop shortcut
- Click **Start All**
- > We only need Laragon for HeidiSQL — ignore Apache/MySQL

### Step 3 — Open HeidiSQL
- In the Laragon panel, click the **Database** button
- HeidiSQL will open automatically

---

## Part 2: Connecting HeidiSQL to Digital Ocean

### Step 4 — Create a New Session
- Click **New** (bottom left of Session Manager)
- Change network type from `MySQL` to **PostgreSQL (TCP/IP)**

### Step 5 — Fill in Connection Details

Check this GOOGLE DOCS for DATABASE CONFIGURATION SAMPLE: https://docs.google.com/document/d/1mmWU2bTIKoOZ8HEsEtAUKO_oDtgNWM700O7ilQ6RMs8/edit?usp=sharing

### Step 6 — Enable SSL
- Click the **SSL tab**
- Check **Use SSL**
- Leave all certificate fields **empty** — DO handles it automatically

### Step 7 — Set the Library
- Go back to the **Settings tab**
- Under **Library**, select `libpq-15`
- > The library version doesn't need to match the server version

### Step 8 — Connect
- Click **Open**
- You should see `defaultdb` in the left panel ✅



