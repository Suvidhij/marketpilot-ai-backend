"""Run the production UI and API together against a disposable database (no browser)."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--ui-dir", default="../marketpilot-ai-ui")
args = parser.parse_args()
backend = Path(__file__).resolve().parents[1]
ui = Path(args.ui_dir).resolve()
if not (ui / ".next/BUILD_ID").exists():
    raise SystemExit("Build the UI first: npm ci && npm run build")
standalone = ui / ".next/standalone"
if (standalone / "server.js").exists():
    shutil.copytree(
        ui / ".next/static", standalone / ".next/static", dirs_exist_ok=True
    )
    shutil.copytree(ui / "public", standalone / "public", dirs_exist_ok=True)
    ui_command = ["node", "server.js"]
    ui_cwd = standalone
else:
    ui_command = [
        "node",
        "node_modules/next/dist/bin/next",
        "start",
        "--hostname",
        "127.0.0.1",
        "--port",
        "3100",
    ]
    ui_cwd = ui
origin = "http://localhost:3100"
api_url = "http://127.0.0.1:8100"
with tempfile.TemporaryDirectory(prefix="marketpilot-smoke-") as temporary:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{temporary}/smoke.db",
        "ENVIRONMENT": "test",
        "COOKIE_SECURE": "false",
        "AI_ENABLED": "false",
        "CORS_ORIGINS": json.dumps([origin]),
        "ALLOWED_HOSTS": '["127.0.0.1","localhost"]',
        "API_BACKEND_URL": api_url,
        "APP_ORIGIN": origin,
        "NEXT_TELEMETRY_DISABLED": "1",
        "PORT": "3100",
        "HOSTNAME": "127.0.0.1",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
        check=True,
    )
    with (
        open(Path(temporary) / "api.log", "w+") as api_log,
        open(Path(temporary) / "ui.log", "w+") as ui_log,
    ):
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8100",
                ],
                cwd=backend,
                env=env,
                stdout=api_log,
                stderr=subprocess.STDOUT,
            ),
            subprocess.Popen(
                ui_command, cwd=ui_cwd, env=env, stdout=ui_log, stderr=subprocess.STDOUT
            ),
        ]
        try:
            with httpx.Client(base_url=origin, trust_env=False, timeout=20) as browser:
                for target in [api_url + "/api/v1/ready", origin + "/login"]:
                    for _ in range(100):
                        try:
                            if browser.get(target).status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        if any(p.poll() is not None for p in processes):
                            raise RuntimeError("A service exited before readiness")
                        time.sleep(0.1)
                    else:
                        raise RuntimeError(f"Service never became ready: {target}")
                assert browser.get("/dashboard").status_code == 307
                assert browser.get("/dashboard").headers["location"].endswith("/login")
                for path in ["/", "/signup", "/login", "/status"]:
                    assert browser.get(path).status_code == 200

                def call(method, path, body=None, expected=200):
                    r = browser.request(
                        method,
                        "/api/backend" + path,
                        json=body,
                        headers={"Origin": origin},
                    )
                    assert r.status_code == expected, (
                        path,
                        r.status_code,
                        r.text[:500],
                    )
                    return r.json() if r.status_code != 204 else None

                password = secrets.token_urlsafe(24)
                email = f"smoke-{uuid.uuid4().hex}@example.com"
                response = browser.post(
                    "/api/backend/auth/register",
                    json={"name": "Smoke Test", "email": email, "password": password},
                    headers={"Origin": origin},
                )
                assert response.status_code == 201, response.text
                assert "httponly" in response.headers["set-cookie"].lower()
                assert (
                    browser.post(
                        "/api/backend/clients",
                        json={"company_name": "Bad origin"},
                        headers={"Origin": "https://untrusted.example"},
                    ).status_code
                    == 403
                )
                client = call(
                    "POST",
                    "/clients",
                    {"company_name": "Smoke Client", "industry": "Software"},
                    201,
                )
                cid = client["id"]
                campaign = call(
                    "POST",
                    f"/clients/{cid}/campaigns",
                    {
                        "campaign_name": "Launch",
                        "platform": "Search",
                        "impressions": 1000,
                        "clicks": 100,
                        "spend": "200.00",
                        "revenue": "1000.00",
                        "lead_count": 10,
                    },
                    201,
                )
                overview = call("GET", f"/clients/{cid}/overview")
                assert (
                    overview["metrics"]["roas"] == 5.0
                    and overview["metrics"]["ctr"] == 10.0
                )
                content = call(
                    "POST",
                    f"/clients/{cid}/content",
                    {
                        "title": "Review draft",
                        "platform": "Social",
                        "body": "Content for a test only",
                    },
                    201,
                )
                call(
                    "POST",
                    f"/clients/{cid}/reports",
                    {"report_name": "Smoke snapshot"},
                    201,
                )
                token = call("POST", "/automation/token", expected=201)["token"]
                worker = {"X-Workflow-Key": token}
                action = call(
                    "POST",
                    "/automation/actions",
                    {
                        "client_id": cid,
                        "resource_id": content["id"],
                        "action": "publish_content",
                    },
                    201,
                )
                aid = action["id"]
                r = browser.post(
                    api_url + f"/api/v1/webhooks/actions/{aid}/claim", headers=worker
                )
                assert r.status_code == 409
                call(
                    "POST",
                    f"/automation/actions/{aid}/decision",
                    {"decision": "approve"},
                )
                r = browser.post(
                    api_url + f"/api/v1/webhooks/actions/{aid}/claim", headers=worker
                )
                assert (
                    r.status_code == 200
                    and r.json()["idempotency_key"] == f"marketpilot-action-{aid}"
                )
                # This receipt is synthetic. No external publisher is called by the smoke test.
                r = browser.post(
                    api_url + f"/api/v1/webhooks/actions/{aid}/complete",
                    json={"external_reference": "smoke-only-no-external-publication"},
                    headers=worker,
                )
                assert r.status_code == 200
                assert (
                    call("GET", f"/clients/{cid}/content/{content['id']}")["status"]
                    == "published"
                )
                call("POST", f"/clients/{cid}/agents/run", {"agent": "research"}, 503)
                for module in [
                    "",
                    "/clients",
                    "/research",
                    "/content",
                    "/campaigns",
                    "/leads",
                    "/reports",
                    "/assistant",
                    "/automation",
                    "/settings",
                ]:
                    r = browser.get("/dashboard" + module)
                    assert r.status_code == 200, (module, r.status_code)
                with httpx.Client(base_url=origin, trust_env=False) as other:
                    r = other.post(
                        "/api/backend/auth/register",
                        json={
                            "name": "Other User",
                            "email": f"other-{uuid.uuid4().hex}@example.com",
                            "password": password,
                        },
                        headers={"Origin": origin},
                    )
                    assert r.status_code == 201
                    assert other.get(f"/api/backend/clients/{cid}").status_code == 404
                call("POST", "/auth/logout", expected=204)
                assert browser.get("/dashboard").status_code == 307
                assert browser.get("/api/backend/auth/me").status_code == 401
                print(
                    "Production HTTP smoke passed: pages, proxy cookies, signup, tenant isolation, CRUD, metrics, reports, approval handoff and logout."
                )
                print(
                    "No live OpenAI, n8n executor, external publisher, or browser interaction was exercised."
                )
        except Exception:
            for name, log in [("API", api_log), ("UI", ui_log)]:
                log.flush()
                log.seek(0)
                print(f"{name} diagnostic tail:\n{log.read()[-3000:]}", file=sys.stderr)
            raise
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
