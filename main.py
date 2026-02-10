import json
import os
import base64
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="POPOLO Agent")

# 분석 대상인 계정의 토큰
# 이 토큰이 계정의 개인/조직 리포지토리 접근 권한을 결정
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") 
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# ---------------------------------------------------------
# [Data Ingection]
# ---------------------------------------------------------
async def fetch_readme_content(client: httpx.AsyncClient, repo_full_name: str) -> str:
    # 리포지토리 README.md를 수집 및 디코딩
    url = f"https://api.github.com/repos/{repo_full_name}/readme"
    res = await client.get(url, headers=HEADERS)

    if res.status_code == 200:
        content_b64 = res.json().get("content", "")
        return base64.b64decode(content_b64).decode('utf-8')

    return ""

async def fetch_all_author_commits(client: httpx.AsyncClient, repo_full_name: str) -> list:
    # 리포지토리에서 사용자가 작성한 모든 커밋 메세지 수집
    commit_messages = []
    page = 1
    while page <=3:
        url = f"https://api.github.com/repos/{repo_full_name}/commits?per_page=100&page={page}"
        res = await client.get(url, headers=HEADERS)
        if res.status_code != 200:
            break
        commits = res.json()
        if not commits:
            break
        for c in commits:
            msg = c.get("commit", {}).get("message", "")
            if msg:
                commit_messages.append(msg)
        page+=1
    return commit_messages

async def collect_selected_repo_contents(repo_full_names: list, response_url: str):
    # 사용자가 선택한 리포지토리들의 데이터를 통합 수집
    async with httpx.AsyncClient() as client:
        collected_data = []
        missing_readme = []
        
        for full_name in repo_full_names:
            # README 수집
            readme_text = await fetch_readme_content(client, full_name)
            if not readme_text:
                missing_readme.append(full_name)
            # 커밋 메세지 수집
            commit_logs = await fetch_all_author_commits(client, full_name)

            collected_data.append({
                "repo": full_name,
                "readme": readme_text,
                "raw_commits": commit_logs
            })
        # README가 없는 리포지토리 알림
        if missing_readme:
            warning_text = "\n".join([f"⚠️ `{repo}` README.md 없음" for repo in missing_readme])
            await client.port(response_url, json={
                "replace_original": False,
                "text": f"알림: 일부 리포지토리의 설명 데이터가 부족할 수 있습니다. \n{warning_text}"
            })
        # 수집 완료 알림
        await client.post(response_url, json={
            "replace_original": False,
            "text": f"✅ 데이터 수집 완료 "
        })

# ---------------------------------------------------------
# [Slack Interaction Handler]
# ---------------------------------------------------------
@app.post("/slack/command")
async def handle_slack_command(request: Request, background_tasks: BackgroundTasks):
    form_data = await request.form()
    response_url = form_data.get("response_url")

    # slack 타임아웃 방지
    background_tasks.add_task(fetch_all_integrated_repos, response_url)

    return {
        "response_type": "ephemeral",
        "text": "🔍 본인 계정 및 소속 조직의 리포지토리를 불러오고 있습니다. 잠시만 기다려주세요..."
    }

@app.post("/slack/interactive")
async def handle_slack_interactive(request: Request, background_tasks: BackgroundTasks):
    form_data = await request.form()
    payload = json.loads(form_data["payload"])
    actions = payload.get("actions", [])
    if not actions: return ""

    action_id = actions[0].get("action_id")
    response_url = payload.get("response_url")

    # [리포지토리 선택 시] 데이터 수집 단계 (README, Commit 등)
    if action_id == "repo_selection_action":
        selected_repos = [opt["value"] for opt in actions[0].get("selected_options", [])]
        background_tasks.add_task(collect_selected_repo_contents, selected_repos, response_url)
        return {"replace_original": True, "text": f"📡 {len(selected_repos)}개 프로젝트의 상세 데이터를 추출 중입니다..."}

    return ""

# 리포지토리 목록 호출
async def fetch_all_integrated_repos(response_url: str):
    # 개인+조직 리포지토리를 한 번에 쿼리
    api_url = "https://api.github.com/user/repos?sort=updated&per_page=30&affiliation=owner,collaborator,organization_member"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(api_url, headers=HEADERS)
        
        if res.status_code != 200:
            error_msg = {"replace_original": True, "text": "❌ 리포지토리를 불러오지 못했습니다. .env의 GITHUB_TOKEN을 확인하세요."}
            await client.post(response_url, json=error_msg)
            return

        repos = res.json()
        # 선택 메뉴 구성을 위해 full_name(owner/repo)을 추출합니다.
        options = [
            {
                "text": {"type": "plain_text", "text": f"{r['full_name']} ({'Private' if r['private'] else 'Public'})"},
                "value": r['full_name']
            } for r in repos
        ]

        # 슬랙의 response_url을 통해 기존 메시지를 선택 메뉴로 교체합니다.
        update_payload = {
            "replace_original": True,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": "📂 *POPOLO*가 분석할 프로젝트를 선택해주세요. (최대 5개)"}},
                {
                    "type": "section",
                    "block_id": "repo_select_block",
                    "accessory": {
                        "type": "multi_static_select",
                        "action_id": "repo_selection_action",
                        "options": options[:25], # 슬랙 드롭다운 최대 한계치 고려
                        "max_selected_items": 5
                    },
                    "text": {"type": "plain_text", "text": "리포지토리 목록"}
                }
            ]
        }
        await client.post(response_url, json=update_payload)