# PB 공용 아침 시황 통합분석 핸드오프

기준: 2026-10-21 KST. 이 문서는 PB들이 참고하는 분석 계약이며 주문 명령이나 계좌 SSOT가 아니다.

## 데이터 우선순위
1. JJOONI Investment Control Tower PB LIVE/Consumer Snapshot·Brief, canonical SSOT/Health: snapshot_id, generated_kst, stale_after_kst/freshness, LIVE/STALE, decision_gate, source_health 확인. STALE 또는 gate != CLEAR면 마지막 검증값으로만 표시.
2. Market Observatory: 시장 데이터 timestamp/source/freshness 및 이전 morning brief 검증. 원천 SSOT와 충돌 시 원천 우선.
3. Finviz 시장 폭, TradingView NDX/DXY/USDKRW/US10Y, Slickcharts NDX 상위 10종목 비중, CNN Fear & Greed(원문 차단 시 최신 미러 2개 교차), 경제·실적 캘린더, 해당 연도 KRX 거래일.
4. 최근 24시간 뉴스 및 6시간 뉴스 브리핑. 기존 브리핑 비활성·접근 불가 시 명시하고 공개 최신 뉴스로 대체.

## 매일 산출물
- 채팅: ① 결론 3줄 ② Finviz 시장 폭·섹터 ③ NDX/DXY/USDKRW/US10Y 표 ④ NDX 집중도 ⑤ 심리 ⑥ 일정 ⑦ Risk-on/off·국내/미국 관전·오늘 대응전략·통합 포트폴리오 참고 ⑧ 바로가기. 각 수치 기준시각과 원문 링크 필수.
- 통합 논리: **뉴스 → 가격/금리/환율/신용 전달경로 → 확인된 직접보유/ETF 간접노출/미보유 관찰 → 집중도·현금·레버리지·TRI-POD 리스크 → 기존 전략 기준상 관찰 트리거**. AI 반도체, 메모리, 전력 인프라, 로봇은 필요시 분리.
- 전일 예측/관찰선과 실제 결과 비교. 미검증 수치는 추정하지 않음. 기존 매매전략·의사결정·주문기준은 변경 금지. 주문/체결은 별도 실행계통 원천이 최종 권위.

## 공용 게시 및 PB 접근
- 게시 명세: [morning-brief-publishing.md](morning-brief-publishing.md)
- 최신 공개 브리핑: `market-observatory/data/morning-brief/latest.json`
- 날짜별: `market-observatory/data/morning-brief/YYYYMMDD.json`
- 색인: `market-observatory/data/morning-brief/index.json`
- PB는 색인→최신→필요한 날짜별 기록을 읽고 출처/시각/신선도를 검증. 동일 날짜 최신본과 이전본의 차이를 추적.
- 게시 원자성: publishing 명세에 따른 단일 커밋·검증·Pages 반영 확인. 게시 실패는 성공으로 표시하지 않음.
- **공개 GitHub/Pages에는 개인 계좌번호·계좌식별정보·잔고·NAV·현금·손익 절대금액·개별 계좌 비중 등 민감한 포트폴리오 사실을 저장하지 않는다.** 공개용은 익명화된 섹터 노출과 시장 영향만 기록. 개인 상세 분석은 권한이 분리된 PB LIVE/SSOT에서 각 PB가 실행 시점에 직접 조회해야 한다.
- 데이터 상태가 STALE 또는 decision_gate != CLEAR이면 보유·비중·손익을 현재 사실처럼 인용하지 않는다.

## 자동화
**보고 체계는 하나, 예약은 요일별 2개(2026-10-27 최종)**: ① 월요일 05:40 KST `시장·AI산업 브리핑 · 월요일 통합판`(ID `6abacf0979d48191819b1c19a8af7fc6`) — PART A 국내장 개장 전 시황 + PART B AI 데이터센터·전력·반도체 산업 지난주 심층분석, 1회 발송. ② 화~토 `시장·AI산업 브리핑 · 화~토 일일시황`(ID `6ab723988af88191aed9e5c216ac69db`) — 뉴욕 현지 월~금 16:40 ET 예약, 한국시간 서머타임 05:40 / 미국 표준시간 06:40, 전체 ①~⑧ 일일시황(토요일 주간 정리 포함). 2개가 서로 다른 KST 요일을 담당해 하루 한 건만 발송한다. 미국 2026-11-01 서머타임 종료 시 뉴욕 타임존이 자동 변환을 담당한다. 화~토 익명화 공개 시황은 Observatory에 게시하며 월요일 PART A+B는 기존 morning-brief/latest를 덮어쓰지 않는다. 모든 실행은 비공개 MAIOS `AI_BOARD`에 날짜·유형별 중복 없이 핵심 판단과 원문 링크를 기록하고 로이·짱구 독립 교차검증 대기로 둔다. 보드 쓰기/공개 게시 실패를 정직하게 기록한다. market pulse와 Observatory 데이터가 이른 시각에 미완료이면 최종값을 가정하지 않고 검증 가능 최신 세션과 STALE/확인불가 항목을 명시한다. 계좌원천 STALE/비CLEAR은 market-only로 제한하며 매매·주문·승인을 자동 실행하지 않는다.
6시간 뉴스 브리핑은 2026-10-21 확인 당시 비활성화. 재가동 여부를 실행 때 확인하며 비활성 시 별도 최신 뉴스 검색.


## 2026-11-03 일일시황 재구성 적용

[일일시황 구성·검증 계약](song-daily-editorial-contract.md)이 기존 섹션 순서보다 우선합니다. 오늘의 시장 이야기·숫자 대시보드·핵심 이슈의 인과 설명을 구성하고 완료 세션/DST/NDX·SOX 독립 가격 검증을 수행합니다. 같은 완성 본문을 채팅과 Observatory에 게시하며 PR·CI 통과만으로 반영 완료라고 하지 않습니다. 예약시간·개인정보·계좌 SSOT·주문 경계는 유지합니다.
