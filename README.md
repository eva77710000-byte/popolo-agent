# POPOLO Agent
**포트폴리오를 대신 작성하는 AI agent**

> **POPOLO(포폴로):** '포트폴리오(포폴)'와 '길(로 路)'의 합성어로, 파편화된 프로젝트 기록을 체계화하여 포트폴리오를 작성해주는 AI 에이전트입니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/Framework-LangChain-white.svg)](https://www.langchain.com/)

---

## 1. 개요 (Overview)
본 프로젝트는 **LangChain 프레임워크와 Gemini 모델을 기반으로 설계된 자율형 AI 에이전트**입니다. 
개발자의 GitHub 데이터를 소스로 삼아 에이전트가 스스로 프로젝트의 성격을 규정하고, 최적의 포트폴리오 서사를 구축합니다. 
단순한 텍스트 요약을 넘어, 데이터 기반의 객관적 역량 증명을 자동화하는 솔루션을 지향합니다.

## 2. 핵심 기능 (Key Features)
* **GitHub 데이터 자율 추출 (Agent Tooling)**: GitHub API를 활용하여 레포지토리 메타데이터, 커밋 히스토리, 소스 코드를 수집하며, 에이전트가 분석에 필요한 핵심 데이터를 스스로 선별합니다.
* **AI 에이전트 기반 기술 서사 구축**: Gemini-2.5-pro의 추론 능력을 바탕으로 LangChain 기반 에이전트가 [기획 의도 - 해결 - 성과] 구조의 논리적 연결성을 자율적으로 설계하고 작성합니다.
* **직무 역량 가시화 및 키워드 도출**: 에이전트가 전체 프로젝트 이력을 종합 분석하여 사용자의 기술적 강점이 응축된 핵심 역량 키워드를 도출하고 포트폴리오 전략을 수립합니다.
* **Notion 포트폴리오 자동 빌딩**: 분석 완료 후 Notion API를 호출하여 구조화된 레이아웃으로 변환합니다. 생성된 결과물은 사용자가 즉시 자신의 워크스페이스로 복제하여 활용할 수 있습니다.
* **Slack 기반 워크플로우 제어**: Slack Bolt 프레임워크를 통해 사용자와 에이전트 간의 인터랙션을 관리하며, 명령어 하나로 전체 분석 프로세스를 구동합니다.

## 3. 기술 스택 (Technical Stack)
| 분류 | 기술 항목 |
| :--- | :--- |
| **에이전트 프레임워크** | LangChain |
| **추론 엔진 (LLM)** | Google Gemini-2.5-Pro |
| **백엔드** | FastAPI |
| **인터페이스** | Slack (Bolt SDK) |
| **연동 API** | GitHub API, Notion API |

## 4. 로드맵 (Roadmap)
본 프로젝트는 AI 에이전트의 자율적 판단 로직 구현을 중심으로 단계별 개발을 진행합니다.

* **Phase 0: 에이전트 설계 및 환경 구성**
    * [ ] 프로젝트 요구사항 정의 및 에이전트 작동 규칙(Persona/Rule) 설계
    * [ ] LangChain 기반 에이전트 워크플로우 아키텍처 확정
* **Phase 1: 에이전트 지능 및 데이터 분석 구현**
    * [ ] GitHub API 도구 연동 및 데이터 전처리 로직 개발
    * [ ] Chain-of-Thought(CoT)를 적용한 기술 서사 생성 프롬프트 엔지니어링
* **Phase 2: 문서 자동화 인프라 구축**
    * [ ] Notion API 기반 구조화된 포트폴리오 빌더 구현
* **Phase 3: 인터페이스 통합 및 최적화**
    * [ ] Slack 인터랙션 설계 및 에이전트 실행 핸들러 통합
    * [ ] API 예외 처리 및 에이전트 추론 안정화
* **Phase 4: 확장 기능 (Optional)**
    * [ ] LinkedIn 데이터 연동을 통한 커리어 히스토리 통합

## 5. 라이선스 (License)
본 프로젝트는 **MIT License**를 따릅니다.
