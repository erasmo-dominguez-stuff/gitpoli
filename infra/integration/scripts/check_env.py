"""Check environments and deployment protection rules for the repo."""
import os, time, jwt, httpx

APP_ID = os.environ.get("GITHUB_APP_ID", "")
KEY_PATH = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "/secrets/app.pem")
REPO = "erasmo-dominguez-stuff/repol"

with open(KEY_PATH) as f:
    pem = f.read()

now = int(time.time())
jwt_token = jwt.encode({"iat": now - 60, "exp": now + 600, "iss": APP_ID}, pem, algorithm="RS256")

# Get installation token
headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

r = httpx.get("https://api.github.com/app/installations", headers=headers)
inst_id = r.json()[0]["id"]
token_r = httpx.post(f"https://api.github.com/app/installations/{inst_id}/access_tokens", headers=headers)
token = token_r.json()["token"]

auth_headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# List environments
print("=== Environments ===")
envs_r = httpx.get(f"https://api.github.com/repos/{REPO}/environments", headers=auth_headers)
if envs_r.status_code == 200:
    envs = envs_r.json().get("environments", [])
    if not envs:
        print("  No environments found")
    for env in envs:
        name = env["name"]
        print(f"  - {name}")
        # Check deployment protection rules
        rules_r = httpx.get(
            f"https://api.github.com/repos/{REPO}/environments/{name}/deployment_protection_rules",
            headers=auth_headers,
        )
        if rules_r.status_code == 200:
            rules = rules_r.json().get("custom_deployment_protection_rules", [])
            if rules:
                for rule in rules:
                    app_info = rule.get("app", {})
                    print(f"    Protection rule: {app_info.get('name', 'unknown')} (slug: {app_info.get('slug', '?')}, enabled: {rule.get('enabled', '?')})")
            else:
                print("    No custom deployment protection rules")
        else:
            print(f"    Could not fetch rules: {rules_r.status_code}")
else:
    print(f"  Error: {envs_r.status_code} - {envs_r.text}")

# Check if test-deploy workflow exists
print("\n=== Workflows ===")
wf_r = httpx.get(f"https://api.github.com/repos/{REPO}/actions/workflows", headers=auth_headers)
if wf_r.status_code == 200:
    for wf in wf_r.json().get("workflows", []):
        print(f"  - {wf['name']} ({wf['path']}) state={wf['state']}")
else:
    print(f"  Error: {wf_r.status_code}")
