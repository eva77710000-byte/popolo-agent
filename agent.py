import os
import base64
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

load_dotenv()

# Project Summary 및 Tech Stack 추출을 위한 Data Model 정의
class ProjectMeta(BaseModel):
    stack: str = Field(description="프로젝트에 사용된 주요 기술 스택 (예: Python, FastAPI, React)")
    summary: str = Field(description="프로젝트에 대한 한 줄 요약")

class PortfolioAgent:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        llm_kwargs = {
            "model": "gemini-2.5-flash",
            "temperature": 0,
        }

        if api_key:
            llm_kwargs["api_key"] = api_key

        self.llm = ChatGoogleGenerativeAI(**llm_kwargs)
        self.meta_parser = JsonOutputParser(pydantic_object=ProjectMeta)
    
    # 전처리 로직
    def preprocess_context(self, commits: list, readme_data: dict, core_code: str) -> str:
        # Raw Data를 AI 분석용 Context 데이터로 결합 및 가공
        commit_text = "\n".join([f"- {c['commit']['message']} ({c['commit']['author']['date']})" for c in commits])
        
        readme_text = ""
        if readme_data:
            readme_text = base64.b64decode(readme_data.get('content', '')).decode('utf-8', errors='ignore')
            
        return f"### [USER ACTIVITY]\n{commit_text}\n\n### [README]\n{readme_text[:2000]}\n\n### [CORE CODE]\n{core_code}"

    async def run_analysis(self, context: str, project_name: str):
        # 개별 프로젝트 상세 분석 및 Markdown 결과물 반환
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 개발자의 기술 역량을 분석하여 문서화하는 전문 에이전트입니다."),
            ("human", "아래 데이터를 분석하여 '{project_name}' 섹션을 마크다운 형식으로 완성하세요:\n\n{context}")
        ])
        chain = prompt | self.llm
        res = await chain.ainvoke({"context": context, "project_name": project_name})
        return res.content

    async def extract_project_meta(self, analysis_result: str):
        # Gallery Table용 Metadata(Stack, Summary) 추출
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 분석 보고서에서 핵심 정보를 추출하여 JSON 형식으로 출력하는 도우미입니다. {format_instructions}"),
            ("human", "다음 분석 결과에서 주요 기술 스택과 한 줄 요약을 추출하세요:\n\n{analysis}")
        ])
        
        chain = prompt | self.llm | self.meta_parser
        return await chain.ainvoke({
            "analysis": analysis_result,
            "format_instructions": self.meta_parser.get_format_instructions()
        })

    async def run_total_summary(self, project_summaries: list):
        # Technical Overview
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 채용 담당자의 시선을 사로잡는 시니어 기술 작가입니다."),
            ("human", "다음 프로젝트 분석 결과들을 종합하여 'Technical Overview' 섹션을 작성하세요:\n\n{summaries}")
        ])
        chain = prompt | self.llm
        res = await chain.ainvoke({"summaries": "\n\n".join(project_summaries)})
        return res.content