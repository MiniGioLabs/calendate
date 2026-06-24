# 📅 CalenDate

> *Scheduling infrastructure for people who touch grass.*

---

## ✨ The Pitch

Your calendar should work **for** you. Set a window, let someone pick a spot, get paid. Clean, fast, no meetings about meetings.

---

## 🚀 Spin It Up

```bash
git clone https://github.com/MiniGioLabs/calendate.git
cd calendate
uv sync
python3 -c "import secrets; open('.env','w').write('SECRET_KEY=***python3 -c "import secrets; open('.env','w').write('SECRET_KEY=***PYTHONPATH=src uv run uvicorn calendate.main:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000` → sign up → you're live.

---

## 🎯 What It Does

- 🗓️ Stripe-style calendar with dots for timed slots, stripes for all-day
- 🔗 One booking link to share — people pick their window
- 💰 Deposits via Stripe — money goes to YOU
- ✂️ Smart slots — approved times split off, cancelled times merge back
- 📱 Text reminders for both sides
- 🔗 Shareable date pages for friends

---

Built with ❤️ by [MiniGioLabs](https://github.com/MiniGioLabs).
