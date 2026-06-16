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

## Session status (2026-06-15)

### Done today
- **환경 비교 분석** — claude.ai 수작업 월간 카드뉴스 워크플로(리서치→카피→HTML 카드)를
  Code vs Cowork, CLI vs 데스크탑으로 비교. 결론: 저작·반복은 **데스크탑 Code + 이 repo**,
  무인 실행은 CLI/NAS. 카드 디자인의 시각 피드백 루프가 환경 선택의 핵심.
- **아키텍처 결정(AskUserQuestion)** — ① 렌더링 = **HTML 템플릿 + Playwright**,
  ② 편집 콘텐츠 = **클라우드 routine이 editorial JSON 생성** → NAS가 읽어 렌더·업로드.
- **현황 파악** — repo의 `cardnews_pangho_april2026.html`(983줄 정적)과 구 PIL
  `image_gen.py`는 별개 디자인. `cn-isbn-202604-card*.png` 기준 PNG는 **구 PIL 단순본**
  (스크랩 원본 그대로의 표)으로 확인 → 픽셀 비교 대상 아님, 리치 디자인으로 교체가 목표.
- **`templates/cards.html.j2` 생성** — 4월 HTML을 Jinja2로 변수화(5장 카드 + 선택적
  소셜 포스트). CSS는 원본 그대로, 본문 데이터만 파라미터화. MoM ▲/▼ 색상 분기 추가.
- **`render_cards.py` 생성** — 스크랩 JSON + editorial JSON 병합 → Jinja2 → Playwright로
  각 `#cardN`을 1080² PNG 캡처. `--month YYYYMM` / `--html-only` / `--scrape/--editorial` 옵션.
- **샘플 데이터** — `data/cn-isbn-202604.json`(NPPA 수치: 수입7/국산147/변경13, YTD·비교)
  + `data/cn-isbn-202604-editorial.json`(스포트라이트 ARC Raiders·遗忘之海, 영문명·개발사·
  분석 등 편집 레이어). YoY/누적 %·증감방향은 render_cards가 수치에서 자동 계산.
- **jinja2 3.1.6 설치 + 템플릿 HTML 렌더 검증** — `--html-only` 성공(31KB). PyPI 네트워크
  타임아웃 잦아 `--default-timeout=120 --retries 8` 필요.

### Open / 미완 (다음 세션 블로커)
- ⬜ **playwright 설치 완료 + `playwright install chromium`** — 설치 중 PyPI 타임아웃으로
  재시도 진행 중이었음.
- ⬜ **4월 5장 PNG 렌더 후 시각 검증** — `python render_cards.py --month 202604`로 리치
  디자인(스포트라이트·영문명·개발사·분석)이 claude.ai 결과와 일치하는지 확인.
- ⬜ **오프라인 폰트 임베드** — 템플릿이 Google Fonts CDN 의존. NAS 망 제약 대비
  @font-face로 로컬 Pretendard/PingFang 임베드 필요(중문 글리프 커버리지 포함).
- ⬜ **오케스트레이션(STEP 2)** — 흐름 순서 변경: NAS 스크랩·push → routine이 editorial
  JSON 생성·push → **다음 NAS 실행**이 editorial 감지 시 리치 카드 렌더·업로드.
  `main.py` 상태머신(카드 발송 지연/분리) + routine 프롬프트(editorial JSON 산출) 수정.
- ⬜ **`requirements.txt`에 jinja2/playwright 추가** + Dockerfile에 chromium 설치 반영.
- ⬜ **구 PIL `image_gen.py` 거취 결정** — HTML 렌더로 대체 vs 폴백(Playwright 불가 시)으로 유지.
