# cn-isbn-cards

중국 NPPA 게임 판호(ISBN) 월간 발표를 추적해 Slack으로 리포트하는 파이프라인.

## 아키텍처 (3단계 · NAS + 클라우드 routine + NAS 카드 렌더)

리치 카드뉴스는 NPPA 스크랩에 없는 **편집 데이터**(스포트라이트 게임·영문명·개발사·
분석 문구)가 필요하다. 그 편집 레이어를 클라우드 routine이 생성하므로, 카드 렌더는
스크랩·routine **다음 NAS 실행**으로 한 박자 늦춰진다.

```
Phase 1 ─ [NAS / Docker]  중국망에서 NPPA 직접 접근, 매월 22일~ 매일
  scraper.py        NPPA 3종(进口/国产/变更) 스크래핑
  state_manager.py  리포트 중복 발송 방지 (state.json)
  slack_client.py   Slack 텍스트 리포트 발송
  data_export.py    3종 모두 발표된 달의 수치를 JSON으로 덤프 → git push
                          │
                          ▼   data/cn-isbn-YYYYMM.json   (수치만)
                    [GitHub repo]  ← 공개적으로 도달 가능한 핸드오프 지점
                          │
                          ▼
Phase 2 ─ [Cloud routine]  Anthropic 클라우드, 매일 18:00 CST (매월 22~31일)
  repo clone → data/ 최신 월 JSON 확인
    · JSON 없음            → no-op (조용히 종료)
    · 이미 Canvas 게시됨   → no-op (중복 방지: 채널 검색)
    · 신규 완성본          → ① 분석 Canvas 발행 (#match_cn_isbn)
                            ② data/cn-isbn-YYYYMM-editorial.json 생성 → git push
                          │
                          ▼   data/cn-isbn-YYYYMM-editorial.json   (편집 레이어)
                    [GitHub repo]
                          │
                          ▼
Phase 3 ─ [NAS / Docker]  다음 daily 실행
  card_publisher.py git pull → editorial JSON 감지 시:
  render_cards.py     scrape + editorial → templates/cards.html.j2 →
                      Playwright(Chromium) → 5×1080² PNG
  slack_client.py     files_upload_v2 로 카드 5장 업로드 (#match_cn_isbn)
```

- **수치(객관)** 는 스크랩 JSON에서, **서사(편집)** 는 editorial JSON에서 온다.
  YoY/누적 %·증감 방향은 `render_cards.py`가 수치에서 자동 계산한다.
- 카드 렌더·업로드는 **NAS 책임**(Slack MCP 커넥터엔 파일 업로드 도구가 없어 클라우드가
  이미지를 못 올림). 클라우드 routine은 **분석 Canvas + editorial JSON 생성**만 담당.
- routine은 NPPA에 직접 붙지 않으므로 도달성 리스크가 없다.
- 카드 발행 상태는 `data/cards/.published-YYYYMM` 마커(NAS-local)로 멱등 관리 —
  NAS의 StateManager는 건드리지 않는다.

> **구 `image_gen.py`(PIL 단순본)** 는 HTML 렌더로 대체됐다. Playwright 사용 불가 환경의
> 폴백으로만 보존하며, 평시 경로는 `render_cards.py`다.

## 핸드오프 JSON 스키마 (`data/cn-isbn-YYYYMM.json`)

```jsonc
{
  "schema_version": 1,
  "year": 2026, "month": 6, "year_month": "202606",
  "generated_at": "2026-06-22T18:00:00+08:00",
  "results": {
    "import":   { "count": 0, "url": "...", "games": [ { "游戏名称": "..." } ] },
    "domestic": { "count": 0, "url": "...", "games": [ ... ] },
    "change":   { "count": 0, "url": "...", "games": [ ... ] }
  },
  "ytd":        { "import": 0, "domestic": 0, "change": 0 },
  "comparison": { "mom_import": 0, "mom_domestic": 0,
                  "yoy_import": 0, "yoy_domestic": 0,
                  "ytd_import_prev": 0, "ytd_domestic_prev": 0 }
}
```
`comparison`의 키는 선택적(상류 fetch 실패 시 생략). routine은 JSON에 있는 값만
사용하고 없는 값은 추정하지 않는다.

## 편집 레이어 스키마 (`data/cn-isbn-YYYYMM-editorial.json`)

Phase 2에서 **클라우드 routine이 생성**한다. 카드의 서사 부분(스크랩에 없는 정보)을
담으며, 수치는 담지 않는다(수치는 스크랩 JSON에서 병합).

```jsonc
{
  "schema_version": 1, "year": 2026, "month": 4, "year_month": "202604",
  "import_card": {
    "spotlight": { "cn": "...", "en": "...", "tags": ["...", "..."] },
    "games": [
      { "cn": "弧光猎人", "en": "ARC Raiders",
        "dev": "Embark Studios<br>/ Nexon · Tencent",   // <br> 허용
        "country": "🇸🇪 스웨덴 / 🇰🇷", "hl": true }       // hl=스포트라이트 행 강조
    ],
    "footer_note": "...",
    "analysis": "📊 수입게임 분석 본문 (HTML 일부 허용: <strong>)"
  },
  "domestic_card": {
    // 방식 A — 주목작 여러 개: 멀티게임 리스트
    "subtitle": "텐센트·넷이즈 양강 …",
    "games": [ { "publisher": "텐센트", "name": "追逐卡蕾多",
                 "name_sub": "머신소녀 RPG", "desc": "...", "genre": "2차원 RPG" } ],
    // 방식 B — 한 타이틀이 압도적: 단일 딥 스포트라이트 (games 대신 spotlight)
    "spotlight": { "cn": "...", "kr": "...", "studio": "...",
                   "grid": [ { "key": "개발 기간", "val": "7년 이상" } ],
                   "note": "..." },
    "mom_base": "3월 130종 → 4월 147종",   // 방식 B에서만 사용
    "footnote": "...",
    "analysis": "📊 국산게임 분석 본문"
  },
  "cta": {
    "ytd_highlight_right": "연간 발급 총량은<br>정해져 있습니다",
    "headline": "남은 수량,<br>지금 확보하세요",
    "body_lines": [ "...", "<strong>...</strong>", "..." ]
  },
  "social": [ { "platform": "Instagram", "handle": "@gippie_sh" }, … ]  // 선택(기본값 내장)
}
```

`domestic_card`는 **`games`(멀티) 또는 `spotlight`(단일)** 중 하나를 채운다 — 템플릿이
존재하는 쪽으로 자동 분기한다. `social` 생략 시 `render_cards.DEFAULT_SOCIAL` 사용.

렌더 검증: `python render_cards.py --month 202604` (또는 `--scrape/--editorial` 직접 지정,
`--html-only`로 PNG 없이 HTML만 확인).

## NAS 측 배포

`main.py`가 Phase 1(`_run_report`)에서 `data_export.export_and_push(...)`로 스크랩 JSON을
push하고, Phase 3에서 `card_publisher.publish_cards_if_ready(...)`가 같은 repo를 pull해
editorial JSON을 감지하면 카드를 렌더·업로드한다. 둘 다 `DATA_REPO_DIR`을 사용한다.

NAS 환경변수:
- `DATA_REPO_DIR` — NAS에 클론된 이 레포 경로 (push 자격증명 포함). 기본 `/app/data-repo`
- `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` — 선택 (commit identity)
- `RENDER_BROWSER_CHANNEL` — 카드 렌더 브라우저. Docker는 `chromium`(번들) 고정.
  미설정 시 system msedge→chrome→번들 순으로 시도(데스크탑 Code 개발 편의).
- `SKIP_CARDS` — `1/true/yes`면 Phase 3(카드) 건너뜀 (텍스트 리포트만).

> Phase 3 카드는 Phase 2(routine)가 editorial JSON을 push한 **다음** 실행에서 발행된다.
> 따라서 텍스트 리포트보다 보통 하루 늦게 카드가 올라온다(daily cron이 재시도).

## 클라우드 routine

`https://claude.ai/code/routines` 에서 관리. cron `0 10 22-31 * *` (UTC) = 매월
22~31일 18:00 Asia/Shanghai. 소스: 이 GitHub 레포
(`https://github.com/Sh-InSoo/cn-isbn-cards`). 커넥터: Slack(`#match_cn_isbn`).
모델 claude-sonnet-4-6. routine ID `trig_012kD3EST1CPi1fDbqe42oCA`.

routine은 매월 (1) **분석 Canvas**(`#match_cn_isbn`)와 (2) **편집 레이어 JSON**
(`data/cn-isbn-YYYYMM-editorial.json`, 위 스키마)을 만들어 repo에 push해야 한다.
인스타 카드뉴스 5장(PNG)은 NAS의 `render_cards.py`가 그 editorial JSON으로 렌더하고
`slack_client.py`(봇 토큰 `files_upload_v2`)로 같은 채널에 업로드한다 — 카드 생성·업로드는
NAS 책임, Canvas·editorial 생성은 클라우드 책임으로 분리. (Slack 커넥터(MCP)에는 파일
업로드 도구가 없어 클라우드 routine은 이미지를 직접 못 올린다.)

routine 프롬프트가 산출해야 하는 것:
- 스포트라이트 게임 선정(수입 1종 + 국산 1종 또는 주목작 3~4종) — 영문/한글명, 개발사,
  퍼블리셔/대리, 플랫폼, 판매고·사전등록 등 **웹검색으로 조사**한 편집 정보
- 📊 수입게임 분석 / 📊 국산게임 분석 문구 (각 1~2문장)
- CTA 카피(`cta.*`)
- editorial JSON을 스키마대로 작성해 `data/cn-isbn-YYYYMM-editorial.json`로 commit·push
- 멱등: editorial JSON이 이미 있으면 덮어쓰기만(무해)
