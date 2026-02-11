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

# GitHub Repository(Personal/Org) 접근 권한 인증용 Token
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") 
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# ---------------------------------------------------------
# [Error Handling]
# ---------------------------------------------------------
async def handle_github_error(res: httpx.Response, response_url: str):
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

    # Slack 채널로 Error Message 전송
    async with httpx.AsyncClient() as client:
        await client.post(response_url, json={"text": msg, "replace_original": True})

# ---------------------------------------------------------
# [Data Ingestion]
# ---------------------------------------------------------
async def get_user_id(client: httpx.AsyncClient):
    # Token Owner의 GitHub ID(Username) 조회 및 반환
    res = await client.get("https://api.github.com/user", headers=HEADERS)
    return res.json().get("login") if res.status_code == 200 else None

async def fetch_user_raw_data(client: httpx.AsyncClient, repo_full_name: str, user_id: str):
    # Repository 내 원본 README 및 Filtered Commit Log 수집
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
    # User가 수정한 File Path List 추출 및 수집
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
async def extract_user_core_code(client: httpx.AsyncClient, repo_full_name: str, file_paths: list):
    # 수정된 파일 중 핵심 로직 선별 및 Content 데이터 추출
    target_exts = [".py", ".js", ".ts", ".java", ".go"]
    priority_keywords = ['main.', 'app.', 'index.', 'agent.', 'service.']
    
    core_paths = [
        p for p in file_paths 
        if any(p.endswith(ext) for ext in target_exts) and
        (any(kw in p.lower() for kw in priority_keywords) or "/" not in p)
    ][:2] # 상위 2개

    code_segments = []
    for path in core_paths:
        f_res = await client.get(f"https://api.github.com/repos/{repo_full_name}/contents/{path}", headers=HEADERS)
        if f_res.status_code == 200:
            decoded = base64.b64decode(f_res.json()['content']).decode('utf-8', errors='ignore')
            code_segments.append(f"--- File: {path} ---\n{decoded[:1500]}")
    
    return "\n".join(code_segments)

async def process_data_pipeline(selected_repos: list, response_url: str):
    # 통합 분석 프로세스 및 결과(Result) 전송 Main 로직 실행
    agent = PortfolioAgent()
    async with httpx.AsyncClient() as client:
        user_id = await get_user_id(client)
        if not user_id: 
            await client.post(response_url, json={"text": "🚫 GitHub ID 조회 실패"})
            return

        project_analyses = []
        gallery_infos = []
        
        await client.post(response_url, json={
            "replace_original": False, 
            "text": f"🚀 *{len(selected_repos)}개* 리포지토리에 대한 분석을 시작합니다."
        })

        for repo_name in selected_repos:
            try:
                # 개별 리포지토리 분석 중 알림
                await client.post(response_url, json={
                    "replace_original": False,
                    "text": f"🔍 *{repo_name}* 분석 중... "
                })

                # 1. 데이터 수집
                raw_commits, raw_readme = await fetch_user_raw_data(client, repo_name, user_id)
                modified_paths = await fetch_user_modified_file_paths(client, repo_name, user_id)
                core_code = await extract_user_core_code(client, repo_name, modified_paths)
                
                # 2. 전처리 (agent.py로 이관된 로직 호출)
                combined_context = agent.preprocess_context(raw_commits, raw_readme, core_code)
                
                # 3. AI 상세 분석
                analysis_result = await agent.run_analysis(combined_context, repo_name)
                project_analyses.append(analysis_result)
                
                # 4. 메타데이터 추출 (갤러리용)
                meta = await agent.extract_project_meta(analysis_result)
                gallery_infos.append({
                    "name": repo_name,
                    "stack": meta.get("stack", "N/A"),
                    "summary": meta.get("summary", "N/A")
                })
                
                # 개별 리포지토리 분석 완료 알림
                await client.post(response_url, json={
                    "replace_original": False,
                    "text": f"✅ *{repo_name}* 분석 완료! (스택: `{meta.get('stack', 'N/A')}`)"
                })

            except Exception as e:
                await client.post(response_url, json={"text": f"⚠️ {repo_name} 분석 중 오류: {e}"})
                continue

        try:
            technical_overview = await agent.run_total_summary(project_analyses)
            
            # 갤러리 테이블 및 포트폴리오 조립
            gallery_table = build_gallery_table(gallery_infos)
            final_portfolio = assemble_full_portfolio(
                overview=technical_overview,
                gallery_table=gallery_table,
                project_sections=project_analyses
            )
            
            await save_to_file(final_portfolio)
            await client.post(response_url, json={
                "replace_original": False,
                "text": "🚀 *포트폴리오 생성이 완료되었습니다!* \n프로젝트 루트의 `PORTFOLIO.md`를 확인하세요.",
            })
        except Exception as e:
            print(f"❌ 조립/전송 단계 에러: {e}")
            await client.post(response_url, json={"text": f"❌ 포트폴리오 조립 중 에러 발생: {e}"})

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

    # 데이터 수집 단계 (README, Commit 등)
    if action_id == "repo_selection_action":
        selected_repos = [opt["value"] for opt in actions[0].get("selected_options", [])]
        background_tasks.add_task(process_data_pipeline, selected_repos, response_url)
        return {"replace_original": True, "text": f"📡 {len(selected_repos)}개 프로젝트의 상세 데이터를 추출 중입니다..."}

    return ""

# 리포지토리 목록 호출
async def fetch_all_integrated_repos(response_url: str):
    # Personal 및 Organization Repository 통합 쿼리 실행
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
                        "options": options[:25],
                        "max_selected_items": 5
                    },
                    "text": {"type": "plain_text", "text": "리포지토리 목록"}
                }
            ]
        }
        await client.post(response_url, json=update_payload)