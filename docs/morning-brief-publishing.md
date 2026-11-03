# 송팀장 아침 시황 게시 규격

화~토 ChatGPT 자동화 `6ab723988af88191aed9e5c216ac69db`는 미국 동부 월~금 16:40 ET에 실행되어 한국시간 다음날 EDT 05:40/EST 06:40에 검증한 8개 섹션의 일일시황을 채팅에 출력하고 공개 가능한 동일 본문을 이 저장소에 게시한다. 월요일 전용 ChatGPT 자동화 `6abacf0979d48191819b1c19a8af7fc6`는 05:40 KST에 국내 개장 전 시황과 AI 데이터센터·반도체 주간 산업분석 PART A+B를 한 번 채팅에 발송하고 비공개 투자보드에 기록한다. 두 자동화는 KST 요일이 겹치지 않으며 월요일 자료로 화~토의 `latest.json`을 덮어쓰지 않는다. 시장 데이터 수집/워치독 결과를 브리핑으로 대체하지 않는다. 게시 실패해도 채팅 출력은 완료하고 실패 사실을 알린다.

## 경로

- 화면: https://mauveplace.github.io/jjooni-control-tower/market-observatory/#morning-brief
- 최신 원문: `market-observatory/data/morning-brief/latest.json`
- 날짜별 원문: `market-observatory/data/morning-brief/YYYYMMDD.json` (한국 작성일)
- 목록: `market-observatory/data/morning-brief/index.json`

## 본문 JSON

```json
{
  "schema": "JJOONI_MORNING_BRIEF_V1",
  "title": "송팀장 아침 시황 브리핑",
  "report_date_kst": "YYYY-MM-DD",
  "market_date_us": "YYYY-MM-DD",
  "generated_kst": "YYYY-MM-DDTHH:mm:ss+09:00",
  "published_kst": "YYYY-MM-DDTHH:mm:ss+09:00",
  "author": "송팀장 아침 시황 · ChatGPT",
  "content_status": "WEB_VERIFIED_WITH_DISCLOSED_GAPS",
  "verification_note": "해당 실행에서 확인한 출처·시각·미확인 항목은 본문 참조",
  "read_only": true,
  "contains_account_data": false,
  "body_markdown": "채팅에 출력할 완성된 동일 본문"
}
```

작성시각과 게시시각은 실제 시각을 사용한다. 보고서에 적힌 시간을 그대로 메타데이터에 반영하며, 미국장 기준일은 실제 확인된 완료 세션이다. 상단 메타와 본문의 기준일을 맞춘다. 미확인 수치는 임의 추정하지 않고 본문에 공개한다. 외부 링크는 실제 URL의 Markdown 링크로 저장하고 채팅 전용 citation 토큰은 게시 원문에 남기지 않는다. 본문 제목은 `## ①`부터 `## ⑧`까지 포함하고 표는 Markdown 표로 작성한다. 개인 계좌번호·잔고·비밀정보를 공개 저장소에 게시하지 않는다. 이 저장본은 해설 계층이며 시장 SSOT를 덮어쓰지 않는다.

오늘 최초 이관본의 `USER_PROVIDED_NOT_REVERIFIED`는 사용자 제공 원문이며 이번 게시에서 수치를 재검증하지 않았음을 뜻한다. 이후 웹 검증을 수행한 신규 실행에서만 `WEB_VERIFIED_WITH_DISCLOSED_GAPS`를 사용한다.

## 목록 JSON

```json
{
  "schema": "JJOONI_MORNING_BRIEF_INDEX_V1",
  "updated_kst": "YYYY-MM-DDTHH:mm:ss+09:00",
  "entries": [
    {
      "report_date_kst": "YYYY-MM-DD",
      "market_date_us": "YYYY-MM-DD",
      "title": "송팀장 아침 시황 브리핑",
      "generated_kst": "YYYY-MM-DDTHH:mm:ss+09:00",
      "published_kst": "YYYY-MM-DDTHH:mm:ss+09:00",
      "path": "YYYYMMDD.json"
    }
  ]
}
```

## 쓰기 순서 및 검증

1. 현재 main HEAD와 tree, 최신 원문 및 목록을 새로 읽는다. 같은 날짜는 교체, 다른 날짜는 보존하고 한국 작성일 내림차순으로 정렬한다.
2. 날짜별 원문과 latest는 동일 JSON이다. 기존 latest가 더 최신 작성일/작성시각이면 오래된 재실행은 날짜별 기록만 쓰고 latest를 이전 날짜로 되돌리지 않는다.
3. JSON 형식/작성일/미국장 기준일/8개 섹션/실제 원문 링크를 확인한다. `python tools/validate_morning_brief.py`는 최신 원문과 보관본·목록의 정합성을 검사한다.
4. GitHub 도구의 create_tree(base_tree_sha) → create_commit(parent_sha) → update_ref(main, expected_sha, force=false)를 사용해 날짜별 원문, latest, 목록을 한 커밋으로 게시한다. 다른 파일은 수정하지 않는다.
5. HEAD가 달라졌으면 다시 읽어 목록을 합친 뒤 재시도한다. 강제 push를 사용하지 않는다.
6. 반환 성공을 확인하고 해당 날짜별 원문을 다시 읽어 제목/작성일/미국장 기준일/본문이 일치하는지 확인한다. Pages 배포 완료를 확인한 경우에만 화면 반영 완료라고 보고한다. 진행 중이면 저장 완료/화면 배포 중으로 구분한다.

## 자동화와 시간

최종 실행시간(2026-10-27 변경): **월요일 05:40 KST** 고정, 화~토 **미국 뉴욕 정규장 종료 후 16:40 ET**(서머타임에는 KST 05:40 / 표준시간에는 KST 06:40). 두 예약은 서로 다른 KST 요일을 담당하여 중복 발송하지 않는다. 예약 시각은 실행 시작이며 검증·작성·Git 공개 게시·비공개 투자보드 기록 완료 시각은 별도다. 빠른 실행에 Observatory 최신 완료세션의 FINAL 값이 아직 갱신되지 않았으면 미확인/STALE로 구분하고 추정값을 게시하지 않는다. 월요일은 PART A+B 1개 보고서를 내고 기존 daily latest는 보존한다. 화~토 8섹션 공개본은 기존 JSON V1 스키마와 원자적 커밋으로 게시한다. 비공개 `AI_BOARD`에는 한국 작성일·보고 유형별 1개 행만 추가하고 로이·짱구 승인/매매를 생성하지 않는다. 페이지는 아침 시황 탭의 최신 원문을 60초마다 재조회한다. 페이지 조회 자체는 보고서나 원천 수집을 실행하지 않는다.


## 2026-11-03 일일시황 재구성 적용

[일일시황 구성·검증 계약](song-daily-editorial-contract.md)이 기존 섹션 순서보다 우선합니다. 오늘의 시장 이야기·숫자 대시보드·핵심 이슈의 인과 설명을 구성하고 완료 세션/DST/NDX·SOX 독립 가격 검증을 수행합니다. 같은 완성 본문을 채팅과 Observatory에 게시하며 PR·CI 통과만으로 반영 완료라고 하지 않습니다. 예약시간·개인정보·계좌 SSOT·주문 경계는 유지합니다.
