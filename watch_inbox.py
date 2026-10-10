"""The scheduled job: every 30 seconds, load any new file in inbox/ into the database,
then move it to inbox/processed/. A file that can't be loaded goes to inbox/rejected/ instead.

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
REJECTED = INBOX / "rejected"


def check():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    new = sorted(INBOX.glob("*.csv"))
    if not new:
        print(f"{datetime.now():%H:%M:%S}  nothing new")
        return
    con = sqlite3.connect(load.DB)
    for path in new:
        try:
            n = load.load_inbox_file(con, path)
        except (load.LoadError, ValueError, KeyError) as e:  # a bad file: set it aside, load nothing from it
            con.rollback()
            REJECTED.mkdir(exist_ok=True)
            shutil.move(str(path), REJECTED / path.name)
            print(f"{datetime.now():%H:%M:%S}  NOT LOADED {path.name}, moved to inbox/rejected/: {e}")
            continue
        con.commit()
        shutil.move(str(path), PROCESSED / path.name)
        if load.pg.database_url():  # instructor only: the shared copy gets the same rows
            try:
                load.pg.append(load.DB, path.name)
            except Exception as e:
                print(f"{datetime.now():%H:%M:%S}  loaded locally, but the shared copy was NOT updated ({e}). "
                      "Run python3 load.py to publish it again.")
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
