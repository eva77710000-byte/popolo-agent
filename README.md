# POPOLO Agent
**포트폴리오를 대신 작성하는 AI agent**

> **POPOLO(포폴로):** '포트폴리오(포폴)'와 '길(로 路)'의 합성어로, 파편화된 프로젝트 기록을 체계화하여 포트폴리오를 작성해주는 AI 에이전트입니다.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangChain](https://img.shields.io/badge/Framework-LangChain-white.svg)](https://www.langchain.com/)

---

## 1. 개요 (Overview)
POPOLO는 개발자의 GitHub 리포지토리 데이터를 분석하여 프로젝트의 성과와 기술적 기여도를 객관적인 서사로 변환합니다. 
LangChain과 Gemini 모델을 활용해 데이터 추출부터 마크다운 형식의 결과물 생성까지 전 과정을 자동화하는 AI 에이전트 솔루션입니다.

## 2. 핵심 기능 (Key Features)
* **GitHub 데이터 자율 분석**: 커밋 히스토리 및 소스 코드에서 핵심 변화량을 선별하여 분석에 활용합니다.
* **AI 에이전트 기반 서사 구축**: [기획 의도 - 해결 방안 - 결과] 구조의 논리적 연결성을 갖춘 기술 문서를 생성합니다.
* **포트폴리오 자동화**: 분석된 내용을 바탕으로 즉시 활용 가능한 `PORTFOLIO.md` 파일을 로컬에 생성합니다.
* **확장성 있는 인터페이스**: 슬랙(Slack) 커맨드 연동을 통한 워크플로우 제어를 지원할 예정입니다.

## 3. 기술 스택 (Technical Stack)
| 분류 | 기술 항목 |
| :--- | :--- |
| **에이전트 프레임워크** | LangChain |
| **추론 엔진 (LLM)** | Google Gemini |
| **백엔드** | FastAPI |
| **인터페이스** | Slack (Bolt SDK) |
| **데이터 연동** | GitHub API |

## 4. 로드맵 (Roadmap)
본 프로젝트는 **AI 에이전트**의 자율적 분석 로직 구현을 중심으로 개발되었으며, 마일스톤에 따라 단계별로 기능을 확장해 나갈 예정입니다.

* **Milestone 1: 에이전트 설계 및 환경 구성 (완료)**
    * [x] LangChain & Gemini 기반 워크플로우 확정
    * [x] GitHub API 연동 및 데이터 전처리 로직 구현
    * [x] 환경 설정 가이드(`.env.example`) 구축
* **Milestone 2: 데이터 분석 및 결과 생성 (완료)**
    * [x] 마크다운 양식 최적화 및 결과물 자동 생성 기능 구현
    * [x] 데이터 처리 효율화 및 분석 로직 최적화
    * [x] 로컬 내 `PORTFOLIO.md` 생성 프로세스 완료
* **Milestone 3: 서비스 인터페이스 확장 (진행 예정)**
    * [ ] 슬랙(Slack) 인터랙션 및 커맨드 핸들러 통합
    * [ ] GitHub API 토큰 입력만으로 구동 가능한 실행 환경 최적화
* **Milestone 4: 지능형 고도화 (장기 비전)**
    * [ ] 슬랙 내 커리어 관리 돕는 상시 대화형 챗봇으로 기능 확대 검토
    * [ ] 모델 파인튜닝을 통한 분석 정밀도 및 생성 성능 고도화 고민

## 5. 시작하기 (Getting Started)

## 6. 라이선스 (License)
본 프로젝트는 **MIT License**를 따릅니다.
