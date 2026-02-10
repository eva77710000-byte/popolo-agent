import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

class PortfolioAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model = "gemini-2.5-flash",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        self.parser = StrOutputParser()
    
    def _create_project_chain(self):
        # 개별 리포지토리 분석
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 개발자의 기술 역량을 분석하여 문서화하는 전문 에이전트입니다.")
            ("human", "아래 데이터를 분석하여 '{project_name}' 섹션을 완성하세요:\n\n{context}")
        ])

        return prompt | self.llm | self.parser
    
    async def run_analysis(self, context: str, project_name: str):
        chain = self._create_project_chain()

        return await chain.ainvoke({
            "context": context,
            "project_name": project_name
        })
    
    def _create_summary_chain(self):
        # Technical Overview
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
            "당신은 채용 담당자의 시선을 사로잡는 시니어 기술 작가입니다. "
            "제공된 여러 프로젝트 분석 내용을 바탕으로 개발자의 'Technical Overview'를 작성하세요. "
            "핵심 역량(Core Competencies)은 데이터에 기반하여 정량적으로 추론하세요."
            )),
            ("human", (
            "다음은 개별 리포지토리 분석 결과물입니다:\n\n"
            "{project_summaries}\n\n"
            "---"
            "위 내용을 바탕으로 전체 포트폴리오의 'Technical Overview' 섹션을 마크다운 형식으로 작성해 주세요. "
            "주요 기술 스택과 핵심 역량을 포함해야 합니다."
            ))
        ])

        return prompt | self.llm | self.parser
    
    async def run_total_summary(self, summaries: list):
        # 개별 분석 결과를 하나의 문자열로 합침
        combined_summaries = "\n\n".join(summaries)
        
        chain = self._create_summary_chain()

        return await chain.ainvoke({"project_summaries": combined_summaries})