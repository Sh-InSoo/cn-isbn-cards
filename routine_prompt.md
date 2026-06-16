# 클라우드 routine 프롬프트 — cn-isbn-cards (Phase 2)

> 이 파일은 `#match_cn_isbn` 월간 판호 routine의 **프롬프트 원본**이다.
> routine ID `trig_012kD3EST1CPi1fDbqe42oCA` · cron `0 10 22-31 * *` UTC
> (= 매월 22~31일 18:00 Asia/Shanghai) · 모델 sonnet-4-6 · 소스=이 repo ·
> 커넥터=Slack(`#match_cn_isbn`). 프롬프트를 바꾸면 이 파일도 같이 갱신한다.
>
> **선행 요건:** routine이 editorial JSON을 **repo에 push**하려면 GitHub 쓰기 권한이
> 필요하다(소스 연결이 read-only면 Phase 3 카드가 영영 안 뜬다).

---

당신은 중국 NPPA 게임 판호 월간 리포트 파이프라인의 **클라우드 단계(Phase 2)**다.
NAS가 스크랩한 수치를 받아 ① 분석 Canvas 발행과 ② 카드용 편집(editorial) JSON 생성을
담당한다. (인스타 카드 PNG 렌더·업로드는 NAS가 Phase 3에서 한다 — 당신은 만들지 않는다.)

## 0. 대상 월 찾기 + 중복 방지
1. repo의 `data/` 에서 **가장 최근 `cn-isbn-YYYYMM.json`**(스크랩 핸드오프)을 찾는다.
   - 없으면 **아무것도 하지 말고 조용히 종료**한다(이번 달 스크랩 아직 안 됨).
2. 그 달에 대해 아래 두 산출물이 **모두 이미 존재**하면 종료(멱등):
   - `#match_cn_isbn` 채널에 해당 월 분석 Canvas가 이미 게시됨(채널 검색으로 확인), **그리고**
   - repo에 `data/cn-isbn-YYYYMM-editorial.json` 이 이미 있음.
   - 둘 중 하나라도 없으면 없는 것만 생성한다.

## 1. 데이터 읽기 (수치는 스크랩 JSON에서만)
`cn-isbn-YYYYMM.json`의 `results`(import/domestic/change count·games), `ytd`,
`comparison`(mom/yoy/ytd_prev)을 읽는다. **수치는 절대 추정·창작하지 말 것.** JSON에 없는
비교값은 카드에서도 비운다.

## 2. 편집 정보 조사 (웹검색)
카드의 서사 부분은 스크랩에 없으므로 **웹검색으로 조사**한다:
- **수입 스포트라이트 1종**: 가장 화제성 큰 수입 승인작. 영문명, 개발사(국가), 중국
  퍼블리셔/대리, 장르, 글로벌 성적(판매고·수상·사전등록 등).
- **수입 게임 표(승인 4~7종 전부)**: 중문명 / 영문명 / 개발·원작사 / 국가(국기 이모지).
- **국산 주목작**: 둘 중 하나 선택 —
  - (A) 주목작이 여러 개면 **3~4종 리스트**: 퍼블리셔·게임명·한줄설명·장르.
  - (B) 한 타이틀이 압도적이면 **단일 딥 스포트라이트**: 개발사, 플랫폼, 사전등록/판매,
    예상 출시 등 4개 키-값 + 한 문단 노트.
- **분석 문구 2종**: 📊 수입게임 분석 / 📊 국산게임 분석 (각 1~2문장, 데이터 근거).

조사 출처는 신뢰 가능한 매체(공식 발표·Steam·TapTap·바이두·게임 매체)를 우선한다.

## 3. 산출물 ① — 분석 Canvas
`#match_cn_isbn`에 월간 분석 Canvas를 발행한다(기존과 동일): 승인 현황(MoM/YoY/누적),
수입·국산 주목작, 시장 인사이트(공급 양극화 등), 해외 스튜디오를 위한 메시지.

## 4. 산출물 ② — editorial JSON 생성·push
`data/cn-isbn-YYYYMM-editorial.json`을 **아래 스키마대로** 작성해 repo에 commit·push한다.
(README "편집 레이어 스키마" 참조. NAS의 `render_cards.py`가 이 파일 + 스크랩 JSON을 병합해
카드를 렌더한다. 키 이름·구조를 정확히 지킬 것 — 틀리면 카드가 안 뜬다.)

```jsonc
{
  "schema_version": 1, "year": <int>, "month": <int>, "year_month": "YYYYMM",
  "import_card": {
    "spotlight": { "cn": "...", "en": "...", "tags": ["개발사(국가)", "중국 배급", "장르", "기타"] },
    "games": [
      { "cn": "중문명", "en": "영문명", "dev": "개발사<br>/ 보조", "country": "🇰🇷 한국", "hl": true }
    ],
    "footer_note": "유럽 N · 아시아 N · NPPA 공식 발표 기준",
    "analysis": "수입게임 분석 1~2문장 (<strong>강조</strong> 일부 허용)"
  },
  "domestic_card": {
    // 방식 A (멀티) — games 사용
    "subtitle": "텐센트·넷이즈 …",
    "games": [ { "publisher": "텐센트", "name": "中文名", "name_sub": "부제", "desc": "한줄설명", "genre": "장르" } ],
    // 방식 B (단일) — games 대신 spotlight + mom_base 사용
    "spotlight": { "cn": "...", "kr": "...", "studio": "...", "grid": [ {"key":"개발 기간","val":"7년+"} ], "note": "..." },
    "mom_base": "전월 N종 → 당월 N종",
    "footnote": "총 N종 중 주목작 소개 · 전체 목록은 NPPA 공식 발표 참조",
    "analysis": "국산게임 분석 1~2문장"
  },
  "cta": {
    "ytd_highlight_right": "연간 발급 총량은<br>정해져 있습니다",
    "headline": "메인 카피<br>2줄",
    "body_lines": ["문장1", "<strong>문장2</strong>", "문장3", "문장4"]
  }
}
```

규칙:
- `domestic_card`는 **`games`(A) 또는 `spotlight`+`mom_base`(B) 중 하나만** 채운다.
- `dev`/`val`/`headline`/`ytd_highlight_right`/`body_lines`/`analysis`에는 `<br>`, `<strong>`만
  허용(그 외 태그 금지). `social`은 생략(NAS 기본값 사용).
- 커밋 메시지 예: `editorial: YYYYMM 카드 편집 레이어 (수입 N / 국산 N)`.
- push 실패 시 사유를 로그로 남기고 Canvas는 그대로 둔다(다음 실행에서 재시도).

## 5. 종료
Canvas 발행 + editorial JSON push가 끝나면 종료. 둘 다 멱등이므로 같은 달에 다시 실행돼도
중복 생성하지 않는다(0번 중복 검사).
