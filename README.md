# Supreme Pick Board

Supreme 시즌 아이템을 둘러보고 마음에 드는 걸 골라 정리하는 드래그앤드롭 픽 보드.
다크모드 · 모바일 대응 · 자동저장(localStorage).

## 기능
- 주차별 섹션 구분 (Left To Drop / Week N…) + 상단 주차 바로가기 칩
- 카테고리 필터, 발매된 것 보기/숨기기 토글
- 카드 호버 시 컬러/디테일 이미지 슬라이드
- 가격 표시 (발매 아이템), 미발매는 "가격 미정"
- 카드별 KREAM 검색 (Supreme {제품명} {시즌태그}, 예: 26ss / 26fw 자동)
- 내 픽: 드래그·▲▼ 정렬, 다중선택 삭제, 가격 합계, JSON 내보내기/가져오기

## 자동 갱신 (매주/매시즌 자동 추적)
- `scripts/scrape.py`가 supremedroplist 홈에서 **현재 진행 시즌을 자동 감지**.
  - 26SS → 26FW로 넘어가면 슬러그(springsummer/fallwinter)를 따라 자동 전환
  - KREAM 검색 태그(26ss/26fw)도 자동으로 바뀜
  - 새 주차(Week N)가 열리면 자동으로 섹션·칩에 추가
- `.github/workflows/update.yml`: 매일 18:00 UTC(03:00 KST) 실행 → data.json 갱신·커밋 → Pages 배포
  - 0개 긁히면 기존 파일 유지(실패 안전장치)

## 배포 (GitHub Pages)
1. 저장소에 이 내용 push
2. Settings → Pages → Source = GitHub Actions
3. Settings → Actions → General → Workflow permissions = Read and write
4. Actions 탭에서 워크플로 1회 수동 실행
