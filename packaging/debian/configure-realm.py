#!/usr/bin/python3
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 8:
        raise SystemExit(
            "usage: configure-realm.py TEMPLATE OUTPUT DOMAIN OIDC_SECRET "
            "ADMIN_PASSWORD MANAGER_PASSWORD PROFESSIONAL_PASSWORD"
        )

    template, output, domain, oidc_secret, *passwords = sys.argv[1:]
    realm = json.loads(Path(template).read_text(encoding="utf-8"))
    public_url = f"https://{domain}"

    client = next(client for client in realm["clients"] if client["clientId"] == "transmissions-web")
    client["secret"] = oidc_secret
    client["redirectUris"] = [f"{public_url}/auth/callback"]
    client["webOrigins"] = [public_url]
    client.setdefault("attributes", {})["post.logout.redirect.uris"] = f"{public_url}/*"

    password_by_username = dict(zip(("admin", "chefservice", "professionnel"), passwords))
    for user in realm["users"]:
        password = password_by_username[user["username"]]
        user["credentials"] = [{"type": "password", "value": password, "temporary": True}]

    Path(output).write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
