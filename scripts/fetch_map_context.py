#!/usr/bin/env python3
"""Fetch pinned public-domain Natural Earth context for a simple study-area map.

The selected country geometries are cartographic context, not a Dhaka municipal
boundary or pollution surface. No API key, tile service or geometry library is
required. Existing selected files are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
from urllib.request import Request, urlopen

COMMIT = "ca96624a56bd078437bca8184e78163e5039ad19"
SOURCE_PATH = "geojson/ne_10m_admin_0_countries.geojson"
SOURCE_URL = f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{COMMIT}/{SOURCE_PATH}"
# Git blob ID from the GitHub contents API for this exact pinned commit/path.
EXPECTED_GIT_BLOB_SHA1 = "5ebc66e25fc1af01edaebe9375c546655e04cf1e"
EXPECTED_SOURCE_BYTES = 13287234
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
COUNTRIES = ("Bangladesh", "India", "Myanmar", "Nepal", "Bhutan")
LICENSE_URL = "https://www.naturalearthdata.com/about/terms-of-use/"
ATTRIBUTION = "Made with Natural Earth. Public domain, 1:10m Admin 0 Countries."


def download_source() -> bytes:
    trust = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    context = ssl.create_default_context(cafile=trust if trust else None)
    request = Request(SOURCE_URL, headers={"User-Agent": "Dhaka-study-map/1.0"})
    with urlopen(request, timeout=30, context=context) as response:
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Natural Earth source exceeds the bounded download limit")
    if len(payload) != EXPECTED_SOURCE_BYTES:
        raise ValueError("Pinned source byte count changed")
    blob_id = hashlib.sha1(b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload).hexdigest()
    if blob_id != EXPECTED_GIT_BLOB_SHA1:
        raise ValueError("Payload does not match the pinned Git blob")
    return payload


def select_context(payload: bytes) -> tuple[dict, dict]:
    source = json.loads(payload)
    if source.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    selected = {}
    for feature in source["features"]:
        properties = feature.get("properties", {})
        name = properties.get("ADMIN")
        if name not in COUNTRIES:
            continue
        if name in selected:
            raise ValueError(f"Ambiguous country selection for {name}")
        geometry = feature.get("geometry", {})
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Unexpected country geometry for {name}")
        selected[name] = {"type": "Feature", "properties": {
            "layer": "country", "name": name,
            "iso_a3": properties.get("ADM0_A3"), "source_attribution": ATTRIBUTION,
        }, "geometry": geometry}
    if set(selected) != set(COUNTRIES):
        raise ValueError(f"Missing countries: {sorted(set(COUNTRIES)-set(selected))}")
    context = {"type": "FeatureCollection", "name": "Natural Earth study-area country context",
               "features": [selected[name] for name in COUNTRIES]}
    manifest = {
        "source_repository": "https://github.com/nvkelso/natural-earth-vector",
        "source_commit": COMMIT, "source_path": SOURCE_PATH, "source_url": SOURCE_URL,
        "source_git_blob_sha1": EXPECTED_GIT_BLOB_SHA1,
        "unmodified_source_sha256": hashlib.sha256(payload).hexdigest(),
        "unmodified_source_bytes": len(payload), "source_feature_count": len(source["features"]),
        "selected_names": list(COUNTRIES), "selected_features": len(context["features"]),
        "selection_rule": "Exact ADMIN property equals one of Bangladesh, India, Myanmar, Nepal or Bhutan; entire original country geometries retained. Only properties are reduced.",
        "coordinate_reference_system": "WGS84 longitude,latitude (OGC:CRS84; GeoJSON convention)",
        "geometry_changes": "None: no clipping, simplification, reprojection or coordinate rounding.",
        "cartographic_scale": "Natural Earth 1:10m Admin 0 Countries",
        "licence": "Public domain", "licence_url": LICENSE_URL, "attribution": ATTRIBUTION,
        "context_scope": "Country borders and coastlines only. No formal Dhaka city boundary, pollution surface, grid footprint or river layer.",
    }
    return context, manifest


def fetch(output: Path) -> dict:
    context_path, manifest_path = output / "context.geojson", output / "context_manifest.json"
    if context_path.exists() or manifest_path.exists():
        raise FileExistsError("Map context already exists; choose another output directory")
    payload = download_source()
    context, manifest = select_context(payload)
    encoded = (json.dumps(context, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    manifest["selected_context_sha256"] = hashlib.sha256(encoded).hexdigest()
    manifest["selected_context_bytes"] = len(encoded)
    encoded_manifest = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    output.mkdir(parents=True, exist_ok=True)
    with context_path.open("xb") as stream:
        stream.write(encoded)
    with manifest_path.open("x", encoding="utf-8") as stream:
        stream.write(encoded_manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/maps"))
    args = parser.parse_args()
    try:
        manifest = fetch(args.output)
    except FileExistsError as exc:
        parser.error(str(exc))
    print(json.dumps({key: manifest[key] for key in ["source_commit", "unmodified_source_bytes", "selected_names", "selected_context_bytes", "selected_context_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
