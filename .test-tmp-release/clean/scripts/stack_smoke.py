"""Exercise only the disposable docker-compose.integration.yml stack."""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "http://127.0.0.1:18080"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--restored", action="store_true", help="Verify existing records in the isolated restored API")
    mode.add_argument("--https", action="store_true", help="Use the isolated localhost TLS rehearsal")
    parser.add_argument("--ca-file", help="Explicitly trusted rehearsal certificate; never disables verification")
    args = parser.parse_args()
    if args.https and not args.ca_file:
        parser.error("--https requires --ca-file")
    base = "http://127.0.0.1:18081" if args.restored else ("https://localhost:18443" if args.https else BASE)
    jar = http.cookiejar.CookieJar()
    handlers: list[urllib.request.BaseHandler] = [urllib.request.HTTPCookieProcessor(jar)]
    if args.https:
        handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=args.ca_file)))
    opener = urllib.request.build_opener(*handlers)

    def request(path, method="GET", payload=None, raw=None, content_type=None, csrf=True, status=200):
        headers = {}
        if csrf:
            token = next((c.value for c in jar if c.name == "novaq_csrf"), None)
            if token:
                headers["X-CSRF-Token"] = token
        if payload is not None:
            raw, content_type = json.dumps(payload).encode(), "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        if args.restored:
            path = path.removeprefix("/api")
        req = urllib.request.Request(base + path, data=raw, headers=headers, method=method)
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == status, (path, response.status, body[:300])
            return body, response.headers

    if not args.restored:
        assert request("/healthz")[0] == b"ok\n"
        page, page_headers = request("/")
        assert b'<div id="root">' in page
        assert page_headers.get("X-Content-Type-Options") == "nosniff"
        assert page_headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in page_headers.get("Content-Security-Policy", "")
        assert "unsafe-eval" not in page_headers.get("Content-Security-Policy", "")
        assert "/" not in page_headers.get("Server", ""), "nginx version must be hidden"
        if args.https:
            assert page_headers.get("Strict-Transport-Security") == "max-age=300"
        asset = re.search(rb'src="(/assets/[^" ]+\.js)"', page)
        assert asset, "Built JavaScript asset missing"
        assert len(request(asset.group(1).decode())[0]) > 100
        assert request("/optimize")[0] == page, "SPA route fallback failed"
    request("/api/ready")
    _, request_id_headers = request("/api/health")
    assert request_id_headers.get("X-Request-ID")
    request("/api/auth/me", status=401)
    _, headers = request("/api/auth/login", "POST", {
        "email": "integration@example.com", "password": "integration-only",
    })
    assert "HttpOnly" in ";".join(headers.get_all("Set-Cookie", []))
    if args.https:
        assert all(cookie.secure for cookie in jar), "HTTPS session/CSRF cookies must be Secure"
        plain = urllib.request.Request("http://localhost:18443/api/auth/me")
        jar.add_cookie_header(plain)
        assert plain.get_header("Cookie") is None, "Secure cookies leaked to HTTP"
        request("/api/auth/me", status=200)
        origin_req = urllib.request.Request(base + "/api/auth/me", headers={"Origin": base})
        with opener.open(origin_req, timeout=30) as response:
            assert response.headers.get("Access-Control-Allow-Origin") == base
        denied_req = urllib.request.Request(base + "/api/auth/me", headers={"Origin": "https://untrusted.example"})
        with opener.open(denied_req, timeout=30) as response:
            assert response.headers.get("Access-Control-Allow-Origin") is None
    request("/api/auth/me")
    if args.restored:
        datasets = json.loads(request("/api/datasets")[0])["datasets"]
        scenarios = json.loads(request("/api/scenarios")[0])["scenarios"]
        assert len(datasets) == len(scenarios) == 1, "Restored fixtures missing or unexpected"
        dataset = json.loads(request(f"/api/datasets/{datasets[0]['id']}")[0])["dataset"]
        assert dataset["row_count"] == 1 and dataset["normalized"][0]["lambda"] == 5
        scenario = json.loads(request(f"/api/scenarios/{scenarios[0]['id']}")[0])["scenario"]
        assert scenario["provenance"] == "verified_snapshot"
        calculation = scenario["settings"]["calculation"]
        recomputed = json.loads(request("/api/optimize/batch", "POST", {
            "segments": calculation["input_segments"], **calculation["options"],
        })[0])
        assert recomputed == scenario["results"], "Restored snapshot does not reproduce"
        for kind, magic in [("pdf", b"%PDF"), ("excel", b"PK")]:
            assert request(f"/api/reports/scenarios/{scenario['id']}/{kind}")[0].startswith(magic)
        request("/api/auth/logout", "POST")
        request("/api/auth/me", status=401)
        print("PASS: restored login, dataset, reproducible scenario, PDF/Excel and logout")
        return
    request("/api/scenarios", "POST", {"name": "CSRF must fail"}, csrf=False, status=403)

    def upload(data, status=201):
        boundary = "novaqIntegrationBoundary"
        raw = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="segments.csv"\r\n'
               'Content-Type: text/csv\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
        return request("/api/datasets", "POST", raw=raw,
                       content_type=f"multipart/form-data; boundary={boundary}", status=status)[0]

    # Above nginx's historical 1 MiB default, within the application's 5 MiB cap.
    saved = json.loads(upload(b"time,lambda,mu,c\nt,5,10,2\n" + b"\n" * (2 * 1024 * 1024)))
    dataset_id = saved["dataset"]["id"]
    assert saved["dataset"]["row_count"] == 1
    upload(b"x" * (5 * 1024 * 1024 + 1), status=413)
    upload(b"x" * (6 * 1024 * 1024 + 1), status=413)
    segments = [{"time": "t", "lambda": 5, "mu": 10, "c": 2}]
    options = {"target_utilization": .7, "max_servers": 4}
    results = json.loads(request("/api/optimize/batch", "POST", {"segments": segments, **options})[0])
    assert results["results"][0]["rho_optimal"] <= .7
    snapshot = {"schema_version": 1, "engine_version": "novaq-2026-09-integrity-v1",
                "input_segments": segments, "options": options, "what_if_multiplier": 1,
                "calculated_at": datetime.now(timezone.utc).isoformat()}
    scenario = json.loads(request("/api/scenarios", "POST", {
        "name": "integration", "dataset_id": dataset_id,
        "settings": {**options, "calculation": snapshot}, "results": results,
    }, status=201)[0])["scenario"]
    assert scenario["provenance"] == "verified_snapshot"
    sid = scenario["id"]
    request(f"/api/scenarios/{sid}", "PATCH", {"results": {}}, status=409)
    for kind, magic in [("pdf", b"%PDF"), ("excel", b"PK")]:
        body, _ = request(f"/api/reports/scenarios/{sid}/{kind}")
        assert body.startswith(magic)
    request("/api/auth/logout", "POST")
    request("/api/auth/me", status=401)
    for _ in range(9):
        request(
            "/api/auth/login",
            "POST",
            {"email": "missing-user@example.com", "password": "wrong"},
            status=401,
        )
    limited, limited_headers = request(
        "/api/auth/login",
        "POST",
        {"email": "missing-user@example.com", "password": "wrong"},
        status=429,
    )
    assert json.loads(limited)["code"] == "rate_limited"
    assert int(limited_headers["Retry-After"]) >= 1
    if args.https:
        print("PASS: verified localhost TLS, Secure cookies, HTTP cookie exclusion, allowed/rejected CORS origins")
    print("PASS: nginx SPA/assets, readiness, sessions/CSRF, upload limits, snapshots, PDF/Excel")


if __name__ == "__main__":
    main()
