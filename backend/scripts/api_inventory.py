"""List every real API endpoint, grouped by router tag."""

from collections import defaultdict

from fastapi.routing import APIRoute

from app.main import app

groups: dict[str, list[str]] = defaultdict(list)
total = 0

for route in app.routes:
    if not isinstance(route, APIRoute):
        continue  # skips /docs, /openapi.json, /redoc
    for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
        tag = (route.tags[0] if route.tags else "untagged")
        groups[tag].append(f"{method:6} {route.path}")
        total += 1

for tag in sorted(groups):
    print(f"\n{tag}  ({len(groups[tag])})")
    for line in sorted(groups[tag]):
        print(f"  {line}")

print(f"\nTOTAL API ENDPOINTS: {total}")
