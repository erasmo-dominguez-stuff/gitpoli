"""Enable the custom deployment protection rule on the production environment."""
import os, time, jwt, httpx

APP_ID = os.environ.get("GITHUB_APP_ID", "")
KEY_PATH = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "/secrets/app.pem")
REPO = "erasmo-dominguez-stuff/repol"
ENV_NAME = "production"

with open(KEY_PATH) as f:
    pem = f.read()

now = int(time.time())
jwt_token = jwt.encode({"iat": now - 60, "exp": now + 600, "iss": APP_ID}, pem, algorithm="RS256")

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Get app info (need the integration_id)
app_r = httpx.get("https://api.github.com/app", headers=headers)
app_data = app_r.json()
app_integration_id = app_data["id"]
app_name = app_data["name"]
print(f"App: {app_name} (integration_id: {app_integration_id})")

# Get installation token
inst_r = httpx.get("https://api.github.com/app/installations", headers=headers)
inst_id = inst_r.json()[0]["id"]
token_r = httpx.post(f"https://api.github.com/app/installations/{inst_id}/access_tokens", headers=headers)
token = token_r.json()["token"]

auth_headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Enable custom deployment protection rule
url = f"https://api.github.com/repos/{REPO}/environments/{ENV_NAME}/deployment_protection_rules"
payload = {"integration_id": app_integration_id}
print(f"POST {url}")
print(f"Payload: {payload}")

resp = httpx.post(url, json=payload, headers=auth_headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

if resp.status_code == 201:
    print("\n✅ Custom deployment protection rule enabled on production!")
else:
    print(f"\n❌ Failed: {resp.status_code}")
