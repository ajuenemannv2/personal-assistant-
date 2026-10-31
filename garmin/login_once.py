"""Run ONCE on your own PC to log in to Garmin (handles MFA).

    py -m pip install --require-hashes -r requirements.txt
    py login_once.py

It writes garmin_tokens.json next to this file. Paste its contents into the
GitHub secret GARMIN_TOKENS_SEED, then DELETE the file. Your password is
never saved anywhere.
"""

import getpass
import os
import stat

from garminconnect import Garmin

email = input("Garmin email: ").strip()
password = getpass.getpass("Garmin password (hidden): ")

g = Garmin(email=email, password=password, prompt_mfa=lambda: input("MFA code: ").strip())
g.login()
del password

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "garmin_tokens.json")
with open(path, "w", encoding="utf-8") as f:
    f.write(g.client.dumps())
try:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
except OSError:
    pass

print(f"Logged in as {g.get_full_name()}.")
print(f"Token saved to {path}")
print("Paste it into the GARMIN_TOKENS_SEED GitHub secret, then delete the file.")
