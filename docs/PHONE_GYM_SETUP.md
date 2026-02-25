# iPhone Setup for Gym Logging (Fastest Path)

This is the easiest way to run the POC on iPhone without building a mobile app.

## Prerequisites

- Mac running this repo
- iPhone with internet access
- Same Tailscale account on both devices
- Terminal app on iPhone (Termius or Blink Shell)

## 1) Prepare the app on Mac

```bash
cd /Users/apoorvasharma/Projects/traininglogs
python3 scripts/init_db.py
python3 -m src.cli.main
```

If CLI opens locally, app is ready.

## 2) Enable SSH on Mac

- Open `System Settings -> General -> Sharing`
- Enable `Remote Login`
- Allow your user (or a dedicated non-admin user)

## 3) Install and connect Tailscale

- Install Tailscale on Mac and iPhone
- Sign into same account on both
- Confirm iPhone can see Mac device

## 4) Connect from iPhone terminal

Use Mac Tailscale IP or MagicDNS host, then:

```bash
cd /Users/apoorvasharma/Projects/traininglogs
python3 -m src.cli.main
```

## 5) Use conversational command mode

Start:

```text
phase 2 week 7 upper-strength no deload
done
ex Barbell Bench Press
w 40x5
w 60x3
s 80x5@8
s 80x5@9
done
finish
```

Helpful commands:

- `status`
- `undo`
- `note felt stronger than last week`
- `help`

Natural language examples:

- `phase 3 week 2 pull hypertrophy no deload`
- `let's do incline dumbbell press`
- `warmup 20x8`
- `did 80 for 5 at 8`

The app will show what it understood and ask for confirmation before applying.

## 6) Reliability for unstable gym network

Use `tmux` on Mac:

```bash
tmux new -As gymlog
cd /Users/apoorvasharma/Projects/traininglogs
python3 -m src.cli.main
```

If connection drops, reconnect and run `tmux attach -t gymlog`.

## 7) Resume after interruption

When you restart the app, it will ask:

`Resume your last in-progress session?`

If you confirm, it restores:
- committed exercises
- current draft exercise (if any)
- autosave state

## 8) Where autosave files go

- Event stream: `data/output/live_sessions/<session_id>.events.jsonl`
- Latest state: `data/output/live_sessions/<session_id>.snapshot.json`
- Saved full session JSON: `data/output/sessions/`
- Database: `data/database/traininglogs.db`
