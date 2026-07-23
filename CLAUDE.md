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

## Session status (2026-06-16)

### Done today
- **렌더 코어 완성·검증** — playwright 설치(시스템 Edge `channel=msedge`로 Chromium
  150MB 다운로드 회피). `render_cards.py`로 4·5월 카드 5장 렌더 → 리치 디자인 시각 검증.
- **카드 디자인 보강** — 카드3 `📊수입게임 분석`·카드4 `📊국산게임 분석` 박스 추가,
  카드2 누적 셀에 전년 절대값+증감(YoY) 표기, 카드2 푸터를 누적셀 바로 아래로 이동.
- **카드4 멀티게임 레이아웃** — `domestic_card.games`(여러 주목작 리스트) / `spotlight`
  (단일 딥) 자동 분기. 5월(텐센트·넷이즈·三七·릴리스 4종) 재현, 4월(망각의바다) 단일 유지.
- **오케스트레이션(STEP 2)** — `main.py`를 리포트(1회)/카드발행(매일 재시도)로 분리,
  구 PIL 인라인 카드 경로 제거. `card_publisher.py` 신규(멱등 마커, StateManager 무수정).
  Dockerfile(chromium·templates·color-emoji 폰트), README 3단계 아키텍처·editorial 스키마,
  `routine_prompt.md` 신규.
- **git-less HTTPS 재설계** — NAS에 git이 없어 핸드오프를 HTTPS로: `data_export`=GitHub
  Contents API push(+로컬저장), `card_publisher`=editorial HTTPS fetch(공개 repo 무인증).
  `config.py`에 GITHUB_REPO/BRANCH/TOKEN·DATA_DIR.
- **NAS chromium=apt(Debian)** — `cdn.playwright.dev`가 중국망에서 0% 멈춤 → `playwright
  install` 대신 apt chromium(Tsinghua 미러) + `executable_path`+`--no-sandbox`(root).
- **클라우드 routine 프롬프트 교체** — Chrome(Claude in Chrome)으로 `trig_012kD3EST1CPi1fDbqe42oCA`
  지침을 git-less 신규 프롬프트(분석 Canvas + editorial JSON 산출)로 교체·저장.
- **NAS 배포·검증** — 실측: DS220+, `insoo` docker그룹(무 sudo), **git 없음**, 코드 볼륨
  마운트, DSM 스케줄러가 `docker compose run --rm cn-isbn`로 일일 실행. 새 파일 scp(`-O`),
  `docker-compose.yml`에 새 마운트·GITHUB env 추가, **이미지 재빌드(1.12GB)** →
  **컨테이너에서 카드 5장 실제 렌더 성공**(국기 이모지가 진짜 깃발로 렌더 = 데스크탑보다 우수).
- **GITHUB_TOKEN 발급·수정·검증** — fine-grained PAT(Contents:write). `.env` 추가 시
  `github_pat_` 접두어 중복(401) → sed로 중복 제거(시크릿 비노출) → `GET /repos` 200 ·
  **write=True 검증**.
- **커밋·푸시** — 62d1804(렌더코어+오케스트레이션), 6c5180c(git-less), d6a6d62(apt chromium).

### Open / 미완 (다음 세션 블로커)
- ⬜ **6/22 첫 자동 사이클 모니터링** — NAS push(`[data_export] pushed`) → GitHub
  `cn-isbn-202606.json` → routine이 Canvas+`...-editorial.json` 생성 → 다음 NAS 실행에서
  `[cards] published` + Slack 카드 5장. 로그: `logs/cron.log`.
- ⬜ **routine 자체 GitHub 쓰기 권한** — NAS PAT와 별개(claude.ai GitHub 연결). routine이
  editorial JSON push 가능한지 6/22 로그로 확인, 실패 시 연결을 write로 승격.
- ⬜ **GITHUB_TOKEN 만료 관리** — fine-grained PAT 만료 시 push 중단 → 갱신 필요(만료일 확인).
- ⬜ (선택) **Slack 5월 중복 Canvas 수동 삭제** — 이전 세션 잔여(MCP에 삭제 도구 없음).

## Session status (2026-07-01)

### Done today
- **6월 판호 수동 처리(클라우드 routine 창구 22~31일이 이미 지나 대신 수행)** —
  NPPA 공식 발표(6/30) + 즈후 기사(https://zhuanlan.zhihu.com/p/2055375709674156997)
  교차검증: 국산 163 / 수입 8 / 변경 6, 상반기 누적 국산 917(전년比 +13%) ·
  수입 33(전년比 -40%). `data/cn-isbn-202606.json` + `-editorial.json` 작성·push.
- **수입게임 편집 데이터를 실제 원작 정보로 교체** — 사용자 제공 조사 결과 반영:
  《异克斯小队》=XCOM 2(Firaxis), 《夜鸦》=Night Crows(MADNGINE·위메이드),
  《北境之地》=Northgard(Shiro Games), 《对峙：交锋时刻》=Standoff 2(AXLEBOLT),
  《海岛之魂》=Spirit of the Island, 《桥梁工程师：传送门》=Bridge Constructor
  Portal(Valve IP) 등. 분석 문구도 장르 다양성(MMORPG·전략·퍼즐·라이프시뮬·FPS) 중심으로 재작성.
- **국산게임 카드 보강** — 즈후 기사 기반으로 《仙剑奇侠传四：重制》(方块游戏, 원 프로듀서
  张孝全 복귀, 19년 만의 정식 리메이크)를 기대작으로 추가. 6월 전체 171건(전월 158 대비
  +13) 통계 반영, 텐센트 北极光 《灰境行者》 모바일판 자격변경 소식도 언급.
- **카드5를 ChinaJoy 2026 행사 안내로 교체** — `templates/cards.html.j2`의 카드5를
  데이터 기반으로 파라미터화(`cta.topbar_label`/`highlight_num`/`highlight_label` 추가,
  미지정 시 기존 "수입 판호 소진" 문구로 폴백해 4·5월 카드는 그대로 렌더됨). 6월 editorial
  cta를 7/31–8/3 상하이 ChinaJoy(주제 与AI同游, 참가사 900+·해외 275개사) 안내로 교체.
  참고: `E:\dev\Claude_Cowork\sns_out\gippie_sns_chinajoy2026.md`.
- **`comparison.py` 버그 수정** — `mom_import`/`mom_domestic`이 전월 원자 수치(raw count)를
  그대로 저장했는데, `cards.html.j2` 템플릿은 이 값을 이미 계산된 증감분(delta)으로
  취급해 "전월比 ▲+N종"으로 그대로 출력 중이었음(방치 시 다음 자동 실행에서 카드2 MoM이
  틀린 숫자로 표시될 뻔함). `get_comparison_counts`가 이번 달 counts를 받아
  this_month - prev_month로 delta를 계산하도록 수정, `main.py` 호출부도 갱신.
- **로컬 렌더 파이프라인 이슈 확인** — `render_cards.py`의 `page.goto(...,
  wait_until="networkidle")`가 데스크탑 환경에서 반복 타임아웃(Google Fonts 서브셋
  요청이 많아 idle 상태에 안 걸림). `wait_until="load"` + `document.fonts.ready` 대기로
  임시 우회해 카드 5장 전부 렌더·시각 검증 완료(템플릿 코드 자체는 미수정).
- **NAS 실행 경로 파악·안내** — `main.py`가 `day < Config.START_DAY(22)`면 즉시 종료됨을
  확인(오늘 7/1 기준 그냥 트리거하면 no-op). `TEST_YEAR=2026 TEST_MONTH=6 TEST_DAY=25`
  환경변수 오버라이드로 SSH에서 `docker compose run --rm -e ... cn-isbn` 실행하는 방법을
  안내. 사용자가 SSH 접속 시도 중 URL 형식 오류(https:// 접두어)로 1차 실패 → 재시도 안내함.
- **NAS SSH 접속 후 6월 실행 완료·확인** — 사용자가 직접 SSH 접속해 `docker compose run
  --rm -e TEST_YEAR=2026 -e TEST_MONTH=6 -e TEST_DAY=25 cn-isbn` 실행, 카드 5장이
  `#match_cn_isbn`에 실제 발행된 것을 확인함. 6월 판호 리포트 파이프라인 이번 세션 목표 완료.

### Open / 미완 (다음 세션 블로커)
- ⬜ **`render_cards.py`의 `networkidle` 타임아웃 근본 수정** — 임시 우회(`wait_until="load"`)만
  했고 템플릿/스크립트 자체는 안 고침. NAS(apt chromium)에서도 같은 증상 있는지 확인 후
  `wait_until="load"`로 정식 교체 검토.
- ⬜ **오프라인 폰트 임베드** — 여전히 미해결(Google Fonts CDN 의존, 위 타임아웃과 연관).
- ⬜ **GITHUB_TOKEN 만료 관리** — 계속 이월 중, 만료일 미확인.
- ⬜ (선택) **Slack 5월 중복 Canvas 수동 삭제** — 계속 이월 중.
