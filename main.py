import asyncio
import datetime
import json
import os
import base64
import httpx
import re
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

from agent import PortfolioAgent
from publisher import build_gallery_table, assemble_full_portfolio, save_to_file

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
    """GitHub API 응답에 따른 에러 메시지 생성 및 슬랙 알림"""
    status_code = res.status_code
    msg = f"🚫 *GitHub API 에러*: 상태 코드 {status_code}가 발생했습니다."

    if status_code == 403:
        remaining = res.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            reset_time = int(res.headers.get("X-RateLimit-Reset", 0))
            reset_date = datetime.fromtimestamp(reset_time).strftime('%H:%M:%S')
            msg = f"🚫 *API 한도 초과*: {reset_date} 이후에 다시 시도해주세요."
        else:
            msg = "🚫 *권한 거부*: 토큰의 'repo' 권한을 확인해주세요."
    elif status_code == 404:
        msg = "🚫 *찾을 수 없음*: 리포지토리를 찾을 수 없거나 접근 권한이 없습니다."

    # 슬랙으로 에러 메시지 전송
    async with httpx.AsyncClient() as client:
        await client.post(response_url, json={"text": msg, "replace_original": True})

# ---------------------------------------------------------
# [Data Ingestion]
# ---------------------------------------------------------
async def get_user_id(client: httpx.AsyncClient):
    """현재 토큰 주인의 GitHub ID를 가져옵니다."""
    res = await client.get("https://api.github.com/user", headers=HEADERS)
    return res.json().get("login") if res.status_code == 200 else None

async def fetch_user_raw_data(client: httpx.AsyncClient, repo_full_name: str, user_id: str):
    """리포지토리에서 원본 README와 사용자 필터링된 커밋 로그를 수집합니다."""
    commit_url = f"https://api.github.com/repos/{repo_full_name}/commits?author={user_id}&per_page=20"
    readme_url = f"https://api.github.com/repos/{repo_full_name}/readme"
    
    commit_res, readme_res = await asyncio.gather(
        client.get(commit_url, headers=HEADERS),
        client.get(readme_url, headers=HEADERS)
    )
    
    commits = commit_res.json() if commit_res.status_code == 200 else []
    readme = readme_res.json() if readme_res.status_code == 200 else {}
    
    return commits, readme

async def fetch_user_modified_file_paths(client: httpx.AsyncClient, repo_full_name: str, user_id: str):
    """사용자가 직접 수정한 파일들의 경로 리스트를 수집합니다."""
    commits_url = f"https://api.github.com/repos/{repo_full_name}/commits?author={user_id}&per_page=30"
    res = await client.get(commits_url, headers=HEADERS)
    
    paths = set()
    if res.status_code == 200:
        for commit in res.json():
            d_res = await client.get(commit['url'], headers=HEADERS)
            if d_res.status_code == 200:
                files = d_res.json().get('files', [])
                for f in files:
                    paths.add(f['filename'])
    return list(paths)

# ---------------------------------------------------------
# [Data Preprocessing]
# ---------------------------------------------------------
def preprocess_commits(commits):
    """원본 커밋 리스트를 AI 분석용 텍스트로 정제합니다."""
    return "\n".join([f"- {c['commit']['message']} ({c['commit']['author']['date']})" for c in commits])

def preprocess_readme(readme_data):
    """Base64 README 데이터를 디코딩하고 텍스트를 최적화합니다."""
    if not readme_data: return ""
    content = base64.b64decode(readme_data.get('content', '')).decode('utf-8', errors='ignore')
    return content[:2000]

async def extract_user_core_code(client: httpx.AsyncClient, repo_full_name: str, file_paths: list):
    """수정된 파일 중 핵심 로직을 선별하여 내용을 추출합니다."""
    target_exts = [".py", ".js", ".ts", ".java", ".go"]
    priority_keywords = ['main.', 'app.', 'index.', 'agent.', 'service.']
    
    core_paths = [
        p for p in file_paths 
        if any(p.endswith(ext) for ext in target_exts) and
        (any(kw in p.lower() for kw in priority_keywords) or "/" not in p)
    ][:2] # 상위 2개 핵심 파일만

    code_segments = []
    for path in core_paths:
        f_res = await client.get(f"https://api.github.com/repos/{repo_full_name}/contents/{path}", headers=HEADERS)
        if f_res.status_code == 200:
            decoded = base64.b64decode(f_res.json()['content']).decode('utf-8', errors='ignore')
            code_segments.append(f"--- File: {path} ---\n{decoded[:1500]}")
    
    return "\n".join(code_segments)


async def process_data_pipeline(selected_repos: list[str], response_url: str):
    """
    선택된 리포지토리들에 대해 GitHub 데이터를 수집하고,
    LangChain 기반 포트폴리오 에이전트로 분석한 뒤,
    최종 포트폴리오 마크다운을 생성·저장합니다.
    """
    if not selected_repos:
        return

    agent = PortfolioAgent()
    project_summaries: list[str] = []
    gallery_repos_info: list[dict] = []

    async with httpx.AsyncClient() as client:
        user_id = await get_user_id(client)
        if not user_id:
            await client.post(
                response_url,
                json={"replace_original": False, "text": "🚫 GitHub 사용자 정보를 가져오지 못했습니다. 토큰을 확인해주세요."},
            )
            return

        for repo_full_name in selected_repos:
            # 1) 원본 데이터 수집
            commits, readme = await fetch_user_raw_data(client, repo_full_name, user_id)
            file_paths = await fetch_user_modified_file_paths(client, repo_full_name, user_id)
            core_code = await extract_user_core_code(client, repo_full_name, file_paths)

            # 2) 전처리
            commits_text = preprocess_commits(commits)
            readme_text = preprocess_readme(readme)

            context = (
                f"### Repository: {repo_full_name}\n\n"
                f"## README (trimmed)\n{readme_text}\n\n"
                f"## Commit History\n{commits_text}\n\n"
                f"## Core Code Snippets\n{core_code}\n"
            )

            # 3) 개별 프로젝트 분석
            project_summary = await agent.run_analysis(context=context, project_name=repo_full_name)
            project_summaries.append(project_summary)

            # 갤러리용 메타 정보 (간단 추출)
            first_line = project_summary.splitlines()[0] if project_summary else repo_full_name
            gallery_repos_info.append(
                {
                    "name": repo_full_name,
                    "stack": "Auto-detected",  # TODO: LLM 결과에서 스택 추출
                    "summary": first_line[:120],
                }
            )

    if not project_summaries:
        async with httpx.AsyncClient() as client:
            await client.post(
                response_url,
                json={"replace_original": False, "text": "⚠️ 분석 가능한 프로젝트 데이터가 없습니다."},
            )
        return

    # 4) 전체 요약 및 포트폴리오 조립
    overview = await agent.run_total_summary(project_summaries)
    gallery_table = build_gallery_table(gallery_repos_info)
    full_portfolio_md = assemble_full_portfolio(overview, gallery_table, project_summaries)

    # 5) 로컬 파일로 저장
    await save_to_file(full_portfolio_md, filename="PORTFOLIO.md")

    # 6) 슬랙 알림
    async with httpx.AsyncClient() as client:
        await client.post(
            response_url,
            json={
                "replace_original": True,
                "text": "✅ 선택한 리포지토리 기반 포트폴리오 분석이 완료되었습니다.\n로컬 파일 `PORTFOLIO.md`로 저장되었습니다.",
            },
        )

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