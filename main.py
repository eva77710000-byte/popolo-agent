import os
import httpx
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="POPOLO Agent API",
    description="GitHub 포트폴리오 자동 생성 에이전트의 API 문서입니다.",
    version="0.1.0"
)

# [추가] 공통으로 사용할 HTTP 클라이언트 설정 (타임아웃 등)
GITHUB_API_URL = "https://api.github.com"

@app.get("/", tags=["Health Check"])
def read_root():
    return {"status": "online", "message": "POPOLO Agent is running!"}

# [수정] 단순히 값을 보여주는 것을 넘어, 실제 연결을 시도하는 QA용 엔드포인트
@app.get("/test-github-connection", tags=["QA"])
async def test_github_connection():
    """실제로 GitHub API에 접속하여 토큰 유효성을 검증합니다."""
    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        raise HTTPException(status_code=400, detail="GITHUB_TOKEN이 .env 파일에 없습니다.")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        async with httpx.AsyncClient() as client:
            # 내 프로필 정보를 가져와 봅니다.
            response = await client.get(f"{GITHUB_API_URL}/user", headers=headers, timeout=5.0)
            
            # 응답 코드가 200(성공)이 아니면 예외를 발생시킵니다.
            response.raise_for_status()
            
            user_data = response.json()
            return {
                "status": "success",
                "message": f"안녕하세요, {user_data.get('login')}님! 연결에 성공했습니다.",
                "scopes_info": {
                    "current_scopes": response.headers.get("X-OAuth-Scopes"),
                    "accepted_scopes": response.headers.get("X-Accepted-OAuth-Scopes")
                }
            }

    except httpx.HTTPStatusError as e:
        # 토큰이 잘못되었을 때 (401 Unauthorized 등)
        if e.response.status_code == 401:
            raise HTTPException(status_code=401, detail="토큰이 유효하지 않습니다. 다시 발급받아주세요.")
        raise HTTPException(status_code=e.response.status_code, detail=f"GitHub API 에러: {e.response.text}")
        
    except httpx.ConnectError:
        # 인터넷 연결 문제
        raise HTTPException(status_code=503, detail="네트워크 연결을 확인해주세요.")
        
    except Exception as e:
        # 그 외 예상치 못한 에러
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")