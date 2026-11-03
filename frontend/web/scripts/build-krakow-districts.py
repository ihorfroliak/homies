"""Reproduce the Home map from the pinned municipal download (stdlib only).

No simplification, invented polygons, web requests or database writes. The
download stores easting/northing coordinates in EPSG:2178. Uniform scaling
and a north-up SVG y reflection retain every vertex and ring.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs/design/001c/geography/Dzielnice_MSIP_20261103.zip"
OUTPUT = ROOT / "frontend/web/src/geography/krakow-districts.json"
SHA256 = "5fca108c88267cb35816d5fa68cda9ca07fa776d2fb9532bfd5ecae076bb2b37"
# Original Home Mapa hues, extended for the five additional official districts.
HUES = [60, 15, 275, 30, 230, 140, 345, 205, 165, 325, 255, 305, 120, 180, 45, 290, 75, 95]


def inside(point, rings):
    x, y = point
    result = False
    for ring in rings:
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                result = not result
    return result


def label_point(rings):
    """Find an interior label location; labels never alter source geometry."""
    points = rings[0]
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    segments = [(a, b) for ring in rings for a, b in zip(ring, ring[1:])]

    def clearance(p):
        best = math.inf
        for a, b in segments:
            dx, dy = b[0] - a[0], b[1] - a[1]
            denominator = dx * dx + dy * dy
            t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denominator)) if denominator else 0
            best = min(best, (p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2)
        return best

    candidates = [(xmin + (x + .5) * (xmax - xmin) / 24,
                   ymin + (y + .5) * (ymax - ymin) / 24)
                  for x in range(24) for y in range(24)]
    return max((p for p in candidates if inside(p, rings)), key=clearance)


def build():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256, "Municipal source changed: review before updating"
    with zipfile.ZipFile(SOURCE) as archive:
        source = json.loads(archive.read("Dzielnice.geojson"))
    assert source["crs"]["properties"]["name"] == "EPSG:2178"
    features = sorted(source["features"], key=lambda f: f["properties"]["id_dzielni"])
    assert [f["properties"]["id_dzielni"] for f in features] == list(range(1, 19))
    for f in features:
        assert f["geometry"]["type"] == "Polygon"
        for ring in f["geometry"]["coordinates"]:
            assert len(ring) >= 4 and ring[0] == ring[-1]
            assert all(len(p) == 2 and all(math.isfinite(v) for v in p) for p in ring)
    points = [p for f in features for ring in f["geometry"]["coordinates"] for p in ring]
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    assert 7_400_000 < xmin < xmax < 7_500_000 and 5_500_000 < ymin < ymax < 5_600_000
    scale = 960 / (xmax - xmin)
    height = (ymax - ymin) * scale + 40

    def project(p):
        return [round(20 + (p[0] - xmin) * scale, 4), round(20 + (ymax - p[1]) * scale, 4)]

    districts = []
    for f in features:
        props, rings = f["properties"], f["geometry"]["coordinates"]
        path = " ".join("M" + " L".join(",".join(str(n) for n in project(p)) for p in ring) + " Z" for ring in rings)
        districts.append({"id": props["id_dzielni"], "roman": props["nr_dzielni"],
                          "name": props["nazwa"], "hue": HUES[props["id_dzielni"] - 1],
                          "label": project(label_point(rings)), "path": path})
    return json.dumps({"viewBox": f"0 0 1000 {height:.4f}", "sourceSha256": SHA256,
                       "vertexCount": len(points), "districts": districts}, ensure_ascii=False, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    result = build()
    if "--check" in sys.argv:
        assert OUTPUT.read_text(encoding="utf-8") == result, "Generated geometry differs from pinned source"
        print("PASS: all 18 districts, every source vertex/ring, deterministic SVG and interior labels")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(result, encoding="utf-8", newline="\n")
        print(f"Generated {OUTPUT.name}: {len(result.encode('utf-8'))} bytes")
