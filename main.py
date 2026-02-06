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

# 통합 데이터 수집 및 업데이트
async def fetch_all_integrated_repos(response_url: str):
    # affiliation 파라미터를 통해 개인+조직 리포지토리를 한 번에 쿼리합니다.
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

async def collect_selected_repo_contents(repo_full_names: list, response_url: str):
    # 선택된 리포지토리들로부터 핵심 데이터(README, Commit)를 긁어옵니다.
    async with httpx.AsyncClient() as client:
        # 이 단계에서 수집된 데이터는 이후 AI Agent(M2)의 입력값이 됩니다.
        collected_data = []
        for full_name in repo_full_names:
            print(f"\n{'='*20} 분석 시작: {full_name} {'='*20}") # 개발자 확인용

            # 1. README 수집 (Base64 디코딩 포함)
            readme_res = await client.get(f"https://api.github.com/repos/{full_name}/readme", headers=HEADERS)
            content = ""
            if readme_res.status_code == 200:
                readme_content_b64 = readme_res.json().get("content", "")
                readme_text = base64.b64decode(readme_content_b64).decode('utf-8')
                
                print(f"[DEBUG] README 데이터 (상위 200자):\n{readme_text[:200]}...") # 개발자 확인용
            else:
                print(f"[DEBUG] README를 가져오지 못했습니다. (Status: {readme_res.status_code})")

            # 2. 최근 커밋 수집
            commit_res = await client.get(f"https://api.github.com/repos/{full_name}/commits?per_page=10", headers=HEADERS)
            
            commit_messages = []
            if commit_res.status_code == 200:
                commit_messages = [c["commit"]["message"] for c in commit_res.json()]
                print(f"[DEBUG] 최근 커밋 5건:") # 개발자 확인용
                for i, msg in enumerate(commit_messages, 1):
                    print(f"  {i}. {msg}")
            else:
                print(f"[DEBUG] 커밋 기록을 가져오지 못했습니다. (Status: {commit_res.status_code})")

            collected_data.append({
                "repo": full_name,
                "readme": readme_text,
                "commits": commit_messages
            })
            print(f"{'='*50}\n")

        # 수집 완료 후 안내
        await client.post(response_url, json={
            "replace_original": True,
            "text": f"✅ 데이터 수집 완료: {', '.join(d['repo'] for d in collected_data)}\n"
        })