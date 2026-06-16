#!/usr/bin/env python3
import os
import requests

host = os.environ["DATABRICKS_HOST"].rstrip("/")
h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
r = requests.get(f"{host}/api/2.0/marketplace-consumer/listings", headers=h, timeout=60)
r.raise_for_status()
keywords = ("virtue", "foundation", "dais", "hackathon", "healthcare", "nfhs", "facility", "facilities")
for listing in r.json().get("listings", []):
    name = listing.get("summary", {}).get("name", "")
    subtitle = listing.get("summary", {}).get("subtitle", "")
    text = (name + " " + subtitle).lower()
    if any(k in text for k in keywords):
        print(listing.get("id"), name[:120])
