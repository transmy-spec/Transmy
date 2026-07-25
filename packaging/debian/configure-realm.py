#!/usr/bin/python3
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 10:
        raise SystemExit(
            "usage: configure-realm.py TEMPLATE OUTPUT DOMAIN OIDC_SECRET "
            "PROVISIONING_SECRET PROFILE ADMIN_PASSWORD MANAGER_PASSWORD "
            "PROFESSIONAL_PASSWORD"
        )

    template, output, domain, oidc_secret, provisioning_secret, profile, *passwords = sys.argv[1:]
    if profile not in {"production", "evaluation"}:
        raise SystemExit("profile must be production or evaluation")
    realm = json.loads(Path(template).read_text(encoding="utf-8"))
    public_url = f"https://{domain}"

    client = next(client for client in realm["clients"] if client["clientId"] == "transmissions-web")
    client["secret"] = oidc_secret
    client["redirectUris"] = [f"{public_url}/auth/callback"]
    client["webOrigins"] = [public_url]
    client.setdefault("attributes", {})["post.logout.redirect.uris"] = f"{public_url}/*"
    provisioning_client = next(
        client for client in realm["clients"]
        if client["clientId"] == "transmissions-provisioning"
    )
    provisioning_client["secret"] = provisioning_secret

    password_by_username = dict(zip(("admin", "chefservice", "professionnel"), passwords))
    for user in realm["users"]:
        if user.get("serviceAccountClientId"):
            continue
        password = password_by_username[user["username"]]
        user["credentials"] = [{"type": "password", "value": password, "temporary": True}]
    if profile == "production":
        realm["users"] = [
            user
            for user in realm["users"]
            if user.get("serviceAccountClientId") or user["username"] == "admin"
        ]

    Path(output).write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
