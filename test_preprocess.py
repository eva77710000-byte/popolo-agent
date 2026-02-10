from main import filter_noise_msg, optimize_content_size# structure_for_llm

def run_test():
    print("🚀 데이터 전처리 로직 테스트를 시작합니다.\n")

    # 1. 가상 데이터(Mock Data) 준비
    mock_readme = "# POPOLO Project\nThis is an AI portfolio agent. " * 100  # 약 3000자
    mock_commits = [
        "feat: 사용자 인증 로직 구현",
        "fix typo in main.py",           # 노이즈
        "Merge branch 'develop'",       # 노이즈
        "refactor: 비동기 데이터 수집 최적화",
        "Update README.md",              # 노이즈
        "docs: API 명세서 추가"
    ]

    # --- [검증 1: 노이즈 제거] ---
    filtered = filter_noise_msg(mock_commits)
    print(f"1. 노이즈 제거 테스트: {len(mock_commits)}개 -> {len(filtered)}개")
    assert "fix typo in main.py" not in filtered
    assert "Merge branch 'develop'" not in filtered
    print("✅ 노이즈 제거 검증 완료")

    # --- [검증 2: 토큰 최적화] ---
    clean_readme, clean_commits = optimize_content_size(mock_readme, filtered)
    print(f"2. 토큰 최적화 테스트: README 길이({len(clean_readme)}자), 커밋 개수({len(clean_commits)}개)")
    assert len(clean_readme) <= 2000
    print("✅ 토큰 최적화 검증 완료")
'''
    # --- [검증 3: 구조화] ---
    final_output = structure_for_llm("test-repo", clean_readme, clean_commits)
    print("\n3. 최종 구조화 결과 미리보기:")
    print("-" * 30)
    print(final_output[:300] + "...") # 앞부분만 출력
    print("-" * 30)
    assert "### Project: test-repo" in final_output
    print("✅ 구조화 검증 완료")
'''
if __name__ == "__main__":
    run_test()