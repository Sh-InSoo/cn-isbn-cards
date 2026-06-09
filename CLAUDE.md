# cn-isbn-cards — 중국 NPPA 게임 판호 월간 리포트 파이프라인

중국 NPPA 게임 판호(ISBN) 월간 발표를 추적해 Slack으로 리포트하는 2단계 파이프라인
(NAS 스크래퍼 + 클라우드 routine). 아키텍처·스키마는 README.md 참조.

## Session status (2026-06-09)

### Done today
- **`main.py`** — `data_export.export_and_push()` 핸드오프 연결 (`state.mark_sent()` 직전,
  try/except로 감싸 push 실패가 run을 막지 않도록; 재push는 멱등)
- **GitHub 업로드** — repo를 public으로 올림 (`https://github.com/Sh-InSoo/cn-isbn-cards`).
  `master`→`main` 브랜치 변경, Git Credential Manager 브라우저 인증으로 push.
  (gh CLI는 winget 권한 승격 문제로 설치 실패 → GCM로 우회)
- **클라우드 routine 생성** (`/schedule`) — ID `trig_012kD3EST1CPi1fDbqe42oCA`,
  cron `0 10 22-31 * *` UTC (= 매월 22~31일 18:00 CST), 모델 sonnet-4-6,
  소스=이 repo, 커넥터=Slack. data/ 최신 월 JSON 읽어 분석 Canvas 발행 + 중복방지.
- **5월 실데이터 발송 테스트** — 웹검색으로 2026-05 데이터 확보(국산 154 / 수입 4 /
  변경 9, YTD 국산 754·수입 25; 4월 카드와 누계 교차검증)하여 `data/cn-isbn-202605.json`
  작성·push → routine 강제 실행으로 **Slack Canvas 발행 경로 검증 성공**.
- **채널명 변경 반영** — `#cn-isbn` → `#match_cn_isbn` (routine 프롬프트 + README 갱신).
- **카드뉴스 책임분리 확정(옵션 3)** — 인스타 카드 5장 PNG는 **NAS**(`image_gen.py` +
  `slack_client.files_upload_v2`)가 계속 담당, 클라우드 routine은 **분석 Canvas만**.
  제약: Slack MCP 커넥터에는 이미지 파일 업로드 도구가 없어 클라우드가 카드를 못 올림.
- **테스트 흔적 제거** — `data/cn-isbn-202605.json` 삭제·push (실데이터만 NAS가 채우도록).

### Open / 미완 (다음 세션 블로커)
- ⬜ **Slack 중복 Canvas 수동 삭제** — 강제 발행 테스트로 `#match_cn_isbn`에 5월 Canvas가
  2개. MCP에 삭제 도구가 없어 사용자가 직접 테스트분 삭제 필요 (NAS 봇 5/27 정식분은 유지).
- ⬜ **6/22 첫 자동 실행 모니터링** — NAS가 `data/cn-isbn-202606.json` push → routine이
  Canvas 자동 발행하는지 확인.
- ⬜ (선택) **gh CLI 설치** — 향후 repo 작업 편의를 위해. winget 머신범위 설치가 권한
  승격을 요구해 이번엔 GCM로 우회함.
