"""The scheduled job: every 30 seconds, load any new file in inbox/ into the database,
then move it to inbox/processed/.

    python3 watch_inbox.py           check every 30 seconds (Ctrl+C to stop)
    python3 watch_inbox.py --once    check once and exit

In real life this runs on a machine that is always on (a server or a VPS), on a schedule
(cron on Mac/Linux, Task Scheduler on Windows). On a laptop it stops when the laptop does.
Standard library only.
"""
import shutil, sqlite3, sys, time
from datetime import datetime
from pathlib import Path

import load

ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox"
PROCESSED = INBOX / "processed"


def check():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    new = sorted(INBOX.glob("*.csv"))
    if not new:
        print(f"{datetime.now():%H:%M:%S}  nothing new")
        return
    con = sqlite3.connect(load.DB)
    for path in new:
        n = load.load_inbox_file(con, path)
        con.commit()
        shutil.move(str(path), PROCESSED / path.name)
        print(f"{datetime.now():%H:%M:%S}  loaded {path.name}: {n} rows")
    con.close()


if __name__ == "__main__":
    if "--once" in sys.argv:
        check()
    else:
        print("Watching inbox/ every 30 seconds. Ctrl+C to stop.")
        try:
            while True:
                check()
                time.sleep(30)
        except KeyboardInterrupt:
            print("Stopped.")
