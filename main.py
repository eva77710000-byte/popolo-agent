import datetime
import json
import os
import base64
import httpx
import re
from datetime import datetime
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
# [Error Handling]
# ---------------------------------------------------------
async def handle_github_error(res: httpx.Response, response_url: str):
    # GitHub API 에러 상태
    status_code = res.status_code

    if status_code == 403:
        # Rate Limit 초과 여부
        remaining = res.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            reset_time = int(res.headers.get("X-RateLimit-Reset", 0))
            reset_date = datetime.fromtimestamp(reset_time).strftime('%H:%M:%S')
            msg = f"🚫 *API 호출 한도 초과*: {reset_date}에 제한이 해제됩니다. 잠시 후 다시 시도해주세요."
        else:
            msg = "🚫 *권한 거부(403)*: 해당 리포지토리에 접근할 권한이 없습니다. 토큰의 'repo' 권한을 확인해주세요."
    elif status_code == 401:
        msg = "🚫 *인증 실패(401)*: GITHUB_TOKEN이 유효하지 않습니다. 설정을 확인해주세요."
    elif status_code >= 500:
        msg = "🚫 *GitHub 서버 에러*: GitHub 서비스에 일시적인 장애가 발생했습니다."
    else:
        msg = f"❓ *GitHub API 오류*: (Status Code: {status_code})"
    
    async with httpx.AsyncClient() as client:
        await client.post(response_url, json={"replace_original": False, "text": msg})

# ---------------------------------------------------------
# [Data Ingestion]
# ---------------------------------------------------------
async def fetch_readme_content(client: httpx.AsyncClient, repo_full_name: str, response_url: str) -> str:
    # 리포지토리 README.md를 수집 및 디코딩
    url = f"https://api.github.com/repos/{repo_full_name}/readme"
    res = await client.get(url, headers=HEADERS)

    if res.status_code == 200:
        content_b64 = res.json().get("content", "")
        return base64.b64decode(content_b64).decode('utf-8')
    
    if res.status_code != 404:
        # README가 없는 경우 외의 에러 발생
        await handle_github_error(res, response_url)

    return ""

async def fetch_all_author_commits(client: httpx.AsyncClient, repo_full_name: str, response_url: str) -> list:
    # 리포지토리에서 사용자가 작성한 모든 커밋 메세지 수집
    commit_messages = []
    page = 1
    while page <=3:
        url = f"https://api.github.com/repos/{repo_full_name}/commits?per_page=100&page={page}"
        res = await client.get(url, headers=HEADERS)

        if res.status_code != 200:
            await handle_github_error(res, response_url)
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

# ---------------------------------------------------------
# [Data Preprocessing]
# ---------------------------------------------------------
def filter_noise_msg(messages: list) -> list:
    noise_patterns = [
        r"^Merge branch.*", r"^Update README.*", r"^Initial commit.*",
        r"^fix typo.*", r"^cleanup.*", r"^\."
    ]
    return [
        msg.strip() for msg in messages 
        if not any(re.match(pattern, msg, re.IGNORECASE) for pattern in noise_patterns)
    ]

def optimize_content_size(readme: str, messages: list) -> tuple:
    # README 상위 2000자, 커밋 최신 50개 제한
    opt_readme = readme[:2000]
    opt_msg = messages[:50]
    return opt_readme, opt_msg

def structure_for_llm(repo_name: str, readme: str, messages: list) -> str:
    # 단일 테스트로 변환
    commit_str = "\n".join([f"- {m}" for m in messages])
    return f"### Project: {repo_name}\n\n[README Snippet]\n{readme}\n\n[Key Commits]\n{commit_str}"

# 데이터 수집 및 전처리 통합
async def process_data_pipeline(repo_full_names: list, response_url: str):
    async with httpx.AsyncClient() as client:
        final_contexts=[]
        missing_readmes = []

        for full_name in repo_full_names:
            # 수집
            raw_readme = await fetch_readme_content(client, full_name, response_url)
            if not raw_readme:
                missing_readmes.append(full_name)
            
            raw_commits = await fetch_all_author_commits(client, full_name, response_url)

            # 전처리
            filtered_commits = filter_noise_msg(raw_commits)
            clean_readme, clean_commits = optimize_content_size(raw_readme, filtered_commits)
            formatted_text = structure_for_llm(full_name, clean_readme, clean_commits)

            final_contexts.append(formatted_text)
        
        # README 부재 알림
        if missing_readmes:
            warning_text = "\n".join([f"⚠️'{repo}' README.md 없음" for repo in missing_readmes])
            await client.post(response_url, json={
                "replace_original": False,
                "text": f"일부 리포지토리의 설명 데이터가 부족할 수 있습니다.\n{warning_text}"
            })

        # 결과 전송
        await client.post(response_url, json={
            "replace_original": False,
            "text": f"✅ AI 분석 단계를 시작합니다."
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
        background_tasks.add_task(process_data_pipeline, selected_repos, response_url)
        return {"replace_original": True, "text": f"📡 {len(selected_repos)}개 프로젝트의 상세 데이터를 추출 중입니다..."}

    return ""

# 리포지토리 목록 호출
async def fetch_all_integrated_repos(response_url: str):
    # 개인+조직 리포지토리를 한 번에 쿼리
    api_url = "https://api.github.com/user/repos?sort=updated&per_page=30&affiliation=owner,collaborator,organization_member"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(api_url, headers=HEADERS)
        
        if res.status_code != 200:
            await handle_github_error(res, response_url)
            return

        repos = res.json()
        options = [
            {
                "text": {"type": "plain_text", "text": f"{r['full_name']} ({'Private' if r['private'] else 'Public'})"},
                "value": r['full_name']
            } for r in repos
        ]

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