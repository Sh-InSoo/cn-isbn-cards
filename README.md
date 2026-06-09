# cn-isbn-cards

중국 NPPA 게임 판호(ISBN) 월간 발표를 추적해 Slack으로 리포트하는 파이프라인.

## 아키텍처 (2단계 · NAS + 클라우드 routine)

```
[NAS / Docker]  — 중국망에서 NPPA 직접 접근, 매월 22일~ 매일
  scraper.py        NPPA 3종(进口/国产/变更) 스크래핑
  state_manager.py  중복 발송 방지 (state.json)
  image_gen.py      인스타 카드 5장 렌더링 → Slack 업로드 (slack_client.py)
  data_export.py    3종 모두 발표된 달의 결과를 JSON으로 덤프 → git push
                          │
                          ▼   data/cn-isbn-YYYYMM.json
                    [GitHub repo]  ← 공개적으로 도달 가능한 핸드오프 지점
                          │
                          ▼
[Cloud routine]  — Anthropic 클라우드, 매일 18:00 CST (매월 22~31일)
  repo clone → data/ 최신 월 JSON 확인
    · JSON 없음            → no-op (조용히 종료)
    · 이미 Slack에 게시됨  → no-op (중복 방지: 채널 검색)
    · 신규 완성본          → Claude가 분석·요약 → Slack Canvas (#cn-isbn)
```

NAS는 중국 사이트 접근·렌더링·원본 카드 전송을 담당하고, 클라우드 routine은
Claude의 강점(분석·인사이트 요약)을 얹어 **Canvas 리포트**를 추가로 발행한다.
routine은 NPPA에 직접 붙지 않으므로 도달성 리스크가 없다.

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

## NAS 측 배포 (data_export 연동)

`main.py`에서 `state.mark_sent(...)` 직전에:

```python
from data_export import export_and_push
export_and_push(year, month, results, ytd, comparison)
```

NAS 환경변수:
- `DATA_REPO_DIR` — NAS에 클론된 이 레포 경로 (push 자격증명 포함). 기본 `/app/data-repo`
- `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` — 선택

## 클라우드 routine

`https://claude.ai/code/routines` 에서 관리. cron `0 10 22-31 * *` (UTC) = 매월
22~31일 18:00 Asia/Shanghai. 소스: 이 GitHub 레포. 커넥터: Slack.
