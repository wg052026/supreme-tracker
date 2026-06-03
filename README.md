# Supreme 26S/S Pick Board

Supreme Spring/Summer 2026 아이템을 둘러보고 마음에 드는 걸 골라 정리하는 드래그앤드롭 픽 보드입니다.
다크모드 · 모바일 대응 · 자동저장(localStorage) 포함.

## 기능
- 카테고리 필터 + 🔥 금주(최신 주차) 필터
- 발매된 것 보기/숨기기 토글 (기본은 미발매만)
- 카드별 KREAM 검색 버튼 — `Supreme {제품명} 26ss` 형식으로 검색
- 내 픽: 금주 픽 / 전체 픽 분리, 드래그·▲▼ 정렬, 체크박스 다중선택 삭제
- 픽 자동저장 + JSON 내보내기/가져오기

## 데이터
- 출처: supremedroplist.com
- `data/data.json`을 fetch 하여 렌더링
- `scripts/scrape.py`가 left-to-drop + week 페이지를 긁어 갱신

## 배포 (GitHub Pages)
1. 이 저장소 내용을 새 GitHub 저장소에 push
2. Settings → Pages → Source = **GitHub Actions**
3. Actions 탭에서 워크플로 1회 수동 실행
4. `https://<user>.github.io/<repo>/` 접속

## 자동 갱신
`.github/workflows/update.yml` — 매일 18:00 UTC(03:00 KST) 자동 실행 + 수동 실행.
`scrape.py` 실행 → `data/data.json` 갱신·커밋 → Pages 재배포.
(0개 긁히면 기존 파일 유지하는 실패 안전장치 포함)
