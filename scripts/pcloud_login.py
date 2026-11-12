# Run this once, by hand, on your own computer:  python scripts/pcloud_login.py
#
# It gives the runs on GitHub access to your pCloud, so they can put the
# downloaded files in the pCloud folder /metacheck_downloads
# (P:\metacheck_downloads). It uses pCloud's documented way for programs
# (OAuth 2.0), which works with two-step verification:
#   1. Before running: register an app at https://docs.pcloud.com/my_apps/
#      (log in, "New app"; any name, e.g. "metacheck reports"). Its page shows
#      a Client ID and a Client secret.
#   2. This script asks for both, opens pCloud's approval page in your browser
#      (log in there as usual, with the code from your phone, and approve), and
#      asks for the code pCloud then shows.
#   3. It exchanges that code for an access key, makes the folders, and saves
#      the key and your pCloud region as the GitHub secrets PCLOUD_TOKEN and
#      PCLOUD_HOST of both report repositories. The key is never printed.
# Needs: Python 3 and the GitHub program "gh", logged in.
#
# The key stays valid until you remove the app's access in pCloud (Settings,
# Apps) or delete the app; then run this again.
import getpass
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser

HOSTS = ["eapi.pcloud.com", "api.pcloud.com"]   # pCloud's Europe and US regions
REPOS = ["Lakens/medrxiv_metacheck", "Lakens/psyarxiv_metacheck"]
FOLDERS = ["/metacheck_downloads", "/metacheck_downloads/medrxiv", "/metacheck_downloads/psyarxiv"]


def call(host, method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"https://{host}/{method}", data=data, timeout=60) as r:
        return json.load(r)


def main():
    client_id = input("Client ID of your pCloud app: ").strip()
    secret = getpass.getpass("Client secret of your pCloud app (not shown): ").strip()
    url = "https://my.pcloud.com/oauth2/authorize?" + urllib.parse.urlencode(
        {"client_id": client_id, "response_type": "code"})
    print(f"\nOpening pCloud's approval page in your browser. If it does not open, go to:\n{url}\n")
    webbrowser.open(url)
    code = input("The code pCloud shows after you approve: ").strip()

    answers = []
    for host in HOSTS:      # the code works only with your region's address
        res = call(host, "oauth2_token", client_id=client_id, client_secret=secret, code=code)
        if res.get("result") == 0 and res.get("access_token"):
            break
        answers.append(f"{host}: {res.get('result')} {res.get('error')}")
    else:
        sys.exit("pCloud did not give an access key:\n  " + "\n  ".join(answers))
    token = res["access_token"]
    print(f"Access granted, region {host}.")

    for path in FOLDERS:
        r = call(host, "createfolderifnotexists", access_token=token, path=path)
        if r.get("result") != 0:
            sys.exit(f"Could not make the folder {path}: {r.get('result')} {r.get('error')}")
        print(f"Folder {r.get('metadata', {}).get('path', path)} exists.")

    for repo in REPOS:
        for name, value in [("PCLOUD_TOKEN", token), ("PCLOUD_HOST", host)]:
            subprocess.run(["gh", "secret", "set", name, "--repo", repo], input=value.encode(), check=True)
        print(f"Saved PCLOUD_TOKEN and PCLOUD_HOST in {repo}.")


if __name__ == "__main__":
    main()
