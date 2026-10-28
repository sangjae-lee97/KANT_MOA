# 이상재(P2) 새 채팅 인계 및 작업 계획

기준: 2026-10-26 KST. 현재 대화, 사용자 서버 실행 결과, 로컬 파일 확인 기준.
이 문서는 새 채팅에서 먼저 읽을 인계 자료다. 계획은 구현 완료를 의미하지 않는다.

**2026-10-27 9단계 최신 업데이트:** 로컬 팀 통합 검사 **515 passed / 0 skipped** 후
사용자 승인으로 동일 학원 서버에 Next.js·FastAPI·Nginx를 배포했다.
사용자 결과 `SITE_DEPLOY_SUCCESS`, `SSH_EXIT=0`, 내부·공개 홈페이지/Swagger 200,
API 경로 45개·공개 상품 387개·미인증 보호 API 401·`database_unchanged=true` 확인.
브라우저에서도 공개 홈페이지·상품 상세·원본 이미지 렌더링을 확인했다. 공용 DB 쓰기 검사는 하지 않았다.
홈페이지는 기존 ngrok 주소 `/`, API는 `/api/`, Swagger는 `/api/docs`.
현재 운영 관리는 `~/kant-moa/active-site.json`과 [최신 배포 기록](../deploy/staging/SITE.md)을 따른다.
기존 API 전용 `compose.backend.yml up` 명령을 재실행하지 않는다.
배포 소스는 main `adfc4e6`에 미커밋 배포 구성·Swagger 상대 인증 주소 수정이 포함된 SHA256으로 식별한다.
9단계 `212f0ca` 커밋·push 및 [PR #75](https://github.com/hiju200208-png/KANT_MOA_develop/pull/75) 생성 완료.
이 인계 문서와 기존 5단계 배포 문서의 미커밋 변경은 보존하고 9단계 PR에서 제외했다.
아래 각 단계의 미진행 문구는 해당 단계 종료 시점의 과거 기록이다.
[9단계 통합·배포 검증](products/P2_TEAM_INTEGRATION.md).

**2026-10-27 5단계 업데이트:** 상품 목록·검색·상세 및 활성 카테고리 API를 실행 앱에 연결하고
새 로컬 Docker DB에서 전체 **246 passed / 0 skipped**, Alembic check 변경 없음 확인.
실제 공개 상품 387개 전체 페이지·상세와 hidden 2개 404 검증.
[5단계 계약·검증·재현 기록](products/P2_CATALOG_API.md).
[PR #57](https://github.com/hiju200208-png/KANT_MOA_develop/pull/57) 병합 후 main `64e7d47` 서버 배포 완료.
사용자 실행 결과 `STAGE5_API_DEPLOY_SUCCESS`, 공개 상품 387개, `DB snapshot unchanged: True`, `SSH_EXIT=0`.
오전에 바꾼 외부 DB `kant-moa`를 사용하며 DB 데이터·스키마·Alembic은 변경하지 않았다.
서버의 기존 `app/` 작업 트리는 그대로이고 고정 커밋을 이미지로 배포했다. 다음에 예전 소스로 재빌드하지 않도록
[배포 기록](products/P2_CATALOG_API.md#공용-서버-배포-완료-로컬-검증-후-후속-실행)을 먼저 확인한다.
위 내용은 5단계 종료 기록이다. 이후 사용자의 6단계 요청으로 아래 작업을 완료했다.

**2026-10-27 6단계 업데이트:** 미커밋 5단계 배포 문서를 백업·보존하고 최신 팀 main `b6252a7`로
fast-forward했다. P1 실제 인증을 재사용한 찜 목록/IDs/멱등 PUT·DELETE 구현과 로컬 검증 완료.
찜·ORM 집중 **18 passed**, P1·P2·P3·P4 전체 **482 passed / 0 skipped**, Alembic 추가 변경 없음.
[6단계 계약·검증·재현 기록](products/P2_WISHLIST_API.md).
공용 DB·배포 서버·프론트는 변경하지 않았다. 6단계 commit·push·PR·배포는 아직 미진행이며
**6단계 종료 당시 기록**이다. 이후 6단계 PR #61이 팀 main에 병합됐다.

**2026-10-27 7단계 업데이트:** 팀 main `b75580d` 반영 후 상품·검색·상세·찜 화면과
사용자가 승인한 P1 최소 인증 연결을 구현했다. 로컬 Docker DB의 실제 카탈로그로
검색→상세→로그인→찜→새로고침 유지, 계정 분리, 오류 원복, PC·모바일 화면을 확인했다.
프론트 29개 테스트·typecheck·lint 및 CORS 2개 테스트 통과. Next.js·eslint-config-next를
16.4.3으로 패치하고 기존 외부 데이터 영역의 요청 시 렌더를 보완해 **production build 통과**.
빌드된 앱에서도 회원가입→자동 로그인→찜→새로고침 유지→로그아웃과 로컬 DB 저장을 확인했다.
[7단계 구현·검증·남은 작업](products/P2_FRONTEND_CONNECTION.md).
7단계는 미커밋이며 push·PR·공용 DB 변경·서버 배포는 하지 않았다. 8단계는 시작하지 않았다.

**2026-10-27 8단계 업데이트:** 미커밋 문서를 별도 백업·stash 보존 후 최신 팀 main `65bf153` 반영.
아티스트·멤버·배너·공지·인기 상품·공개 설정·아티스트 좋아요 API 및 기존 화면 연결 완료.
P3 shipping-policy·주문 계산과 P4 관리자 쓰기는 변경하지 않았다. 최초 Alembic 이력·migration 변경 없음.
신규 API 테스트 9개, 프론트 테스트 34개 통과. 공식 검사 마이그레이션 DB **414 passed / 97 skipped**,
P2/P3 별도 Docker DB **325 passed / 0 skipped**. lint·typecheck·build·Alembic check 통과.
빌드된 앱에서 홈·멤버 모달·공지·로그인 후 아티스트 좋아요·새로고침·PC/모바일·장애 복구 확인.
[8단계 계약·검증 기록](products/P2_DISCOVERY_API.md). 미커밋이며 push·PR·공용 DB·서버 배포 미진행.
**8단계에서 정지하며 9단계·배포는 별도 요청 전 진행하지 않는다.**

## 1. 사용자와 프로젝트

- 사용자: 이상재, 팀 리더, P2 상품·카탈로그 담당. 백엔드 개념과 명령을 단계별로 설명받고 싶어 한다.
- 로컬: `C:\dev\KANT_MOA_develop`, Windows PowerShell.
- 팀 GitHub: https://github.com/hiju200208-png/KANT_MOA_develop
- 인수한 원본: https://github.com/jin-park0115/KANT_MOA
- 개인 작업 브랜치: `feature/sangjae`. PR은 **팀 저장소의 main**으로 보낸다.
- 목표: 기존 Next.js + Supabase 쇼핑몰을 FastAPI + PostgreSQL로 전환.
- 제출: 2026-10-28 14:00, 발표 14:30 (기존 팀 문서 기준).
- 각자 화면 → API → Application → Domain → Repository → 실제 DB까지 구현·검증해야 한다.
- 비동기 SQLAlchemy Repository, 순수 Python 도메인, 트랜잭션, 인증·권한·예외 처리가 필요하다.
- 로그인은 일반 이메일/비밀번호 + Google 로그인 둘 다 사용하기로 선택했다.

## 2. 링크

| 자료 | 주소 |
|---|---|
| 팀 Notion | https://app.notion.com/p/teamsparta/2-4022dc3ef51480c5886cd568134e58d6 |
| 팀 개인 일지 원본 | https://app.notion.com/p/teamsparta/3ea2dc3ef514827eac8901841142b1d8 |
| 팀 공유 자료 표 | https://app.notion.com/p/teamsparta/a3f2dc3ef5148238a23f012b4d881dbb |
| 개인 Notion 프로젝트 | https://app.notion.com/p/405db49922e5814e8210e65fc7d2fd11 |
| 작성한 ERD | https://app.notion.com/p/405db49922e58127aca1e84966e7756f |
| 서버 구축 기록 | https://app.notion.com/p/405db49922e581979ebfc66ad1d42b1b |
| 이상재 구축 일지 | https://app.notion.com/p/teamsparta/4052dc3ef51480cd8c1decbd1ee4b8b5 |
| 공개 Swagger | https://letdown-kilometer-nutcase.ngrok-free.dev/docs |
| 공개 health | https://letdown-kilometer-nutcase.ngrok-free.dev/health |
| 팀 Slack | https://2026kant.slack.com/archives/C0CBAJV8309 |
| Redmine | https://sulfite-footbath-next.ngrok-free.dev/projects/2_project/activity |

학원 Notion은 연결 도구에서 404가 났지만, 로그인된 인앱 브라우저에서는 편집 가능했다.
Slack에는 명시적인 전송 요청 없이 메시지를 보내지 않는다.

## 3. 역할과 팀원 최근 보고

| 담당 | 범위 | 최근 알려진 상태 |
|---|---|---|
| 노희주 P1 | 공통 환경, auth, 회원, JWT, blacklist, USER/ADMIN, 인증 의존성 | 사용자에게 전달된 메시지: 회원 도메인·ORM·Repository·해싱·JWT 작성 및 테스트. signup/login API·인증 의존성 연결 진행 중 |
| 이상재 P2 | 상품·카탈로그·검색·필터·페이지네이션·찜, 아티스트·배너·공지·카테고리·인기 순위, 시드·이미지, 공통 재고 규칙 | 공용 DB·배포 환경을 먼저 구축. 현재 로컬에는 P2 기능 코드가 없음 |
| 김여름 P3 | 장바구니·비회원 병합·배송지·주문·모의 결제·취소 | 주문 도메인·테스트 작업 보고가 있었음. 공통 재고 잠금·증감 함수와 P1 인증을 연결해야 함 |
| 장충만 P4 | 관리자 상품 조회·재고 조정·판매 상태 변경·관리자 화면 | 사용자에게 전달된 메시지: 로컬 Docker DB에서 목록·상세·판매 상태 변경 구현·테스트 완료. 이 작업의 스키마 변경 없음 |

팀원 보고는 이 로컬 HEAD에서 코드 검증한 결과와 구분한다. 최신 main/PR/브랜치를 먼저 확인한다.

### P1과 맞출 사항

- 공용 `users.role`은 TEXT; P1이 로컬 모델을 맞추겠다고 보고했다.
- 공용 UUID 기본값을 유지하면서 Python이 생성한 UUID를 INSERT해도 된다.
- `password_hash IS NOT NULL OR google_sub IS NOT NULL` CHECK 추가 제안에 동의했다.
  현재 초기 SQL에는 없다. 실제 후속 적용 여부는 확인해야 한다.
- 이메일 정규화 CHECK·blacklist 만료 인덱스도 P1이 PR로 정리 예정이라고 보고했다.
- P1 로컬에는 두 인증 테이블의 Alembic 초기 마이그레이션이 이미 적용됨.
  공용 DB에는 18개 테이블이 있으므로 초기 생성 migration을 그대로 실행하면 안 된다.
  실제 스키마와 초기 revision을 비교해 기준을 맞춘 뒤 이력을 등록하고 후속 변경을 적용한다.
  비교 없이 `stamp`하지 않는다. 최초 공용 Alembic 기준 정리는 아직 완료 확인 전이다.

### P4와 맞출 사항

- 관리자 숨김 포함 조회를 P4 조회 전용 Repository에 두는 방식은 허용하는 방향.
- P4가 `infrastructure/product_status.py`에서 products.status를 UPDATE하는 임시 방식을 제안했다.
  이전 대화에서는 허용 상태 검증·관리자 권한·서비스 commit/rollback·재고 미변경을 전제로
  진행해도 된다는 답장 초안을 제시했다. 실제 답장 발송과 최신 코드는 별도 확인한다.
- P2가 공통 상태 변경 함수를 제공할 필요·인터페이스를 P4와 먼저 맞춘다.
- 품절 정책은 기존 TEXT 상태(on_sale/sold_out/hidden)를 유지한다.
  재고 합계 0일 때 계산하는 품절과 수동 sold_out의 관계는 P2/P4와 최종 확정해야 한다.
  hidden은 입고됐다고 자동 on_sale로 바뀌면 안 된다.

## 4. 지금까지 실제 완료한 것

1. 기존 Supabase 테이블을 독립 PostgreSQL로 옮길 초기 SQL 작성.
2. 학원 서버 기존 PostgreSQL 18에 전용 계정·DB `kant_moa` 생성.
3. 18개 테이블의 컬럼·PK·FK·UNIQUE·CHECK·기본값 적용. 테이블 소유자 모두 kant_moa 확인.
4. 별도 임시 PostgreSQL 18에서도 초기 SQL의 18개 테이블·18개 FK 생성 및 중복 실행 실패 검증.
5. FastAPI Docker 이미지 빌드·컨테이너 실행·실제 DB 연결 확인.
6. 개인 ngrok 계정 도메인을 학원 서버 FastAPI에 연결. 외부 health/docs 확인.
7. ngrok를 `kant-moa-ngrok.service`로 등록. enabled·active (running) 확인.
   전환 후 외부 health HTTP 200, `{"status":"ok","database":"ok"}` 재확인.
   SSH 종료와 무관하게 실행하며 부팅 자동 시작·프로세스 종료 시 10초 후 재시작 설정.
   실제 서버 재부팅 테스트는 하지 않았다.
8. GitHub docs·Notion ERD·서버 기록 작성. 공유 자료 표에 ERD 링크 등록.
9. 개인 일지에 전체/노희주/김여름/장충만/이상재 탭과 담당자 필터 구성.
   산출물 링크를 여러 URL을 담을 텍스트로 바꾸고 기존 여섯 링크 보존 확인.
   상세 및 표 순서는 무엇을 어떻게 했나 → 어떻게 풀었나 → 상태 → 산출물 링크로 변경.

초기 SQL에는 데이터 INSERT가 없다. 운영 중 누군가 추가한 데이터 유무는 다시 조회해야 한다.
마지막 배포 검증 당시 기능 경로는 `/health`뿐이었다. 프론트 쇼핑몰 전체 배포는 하지 않았다.

## 5. 서버 정보와 경계

| 항목 | 값 |
|---|---|
| SSH | `ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no kant@10.2.10.104` |
| 서버 | 학원 Ubuntu, 계정 kant, 비밀번호 로그인. 내부 IP라 외부 네트워크 SSH 접속은 보장 안 됨 |
| 작업 경로 | `/home/kant/kant-moa` |
| 소스 | `/home/kant/kant-moa/app` |
| Compose | `/home/kant/kant-moa/compose.backend.yml` |
| API | `kant-moa-api-1`, 호스트 `127.0.0.1:8022` → 컨테이너 8000 |
| PostgreSQL | 기존 `dbresting-db-1`, PostgreSQL 18 |
| DB 네트워크 | `dbresting_default` |
| DB 접속 | 같은 Docker 네트워크에서 `dbresting-db-1:5432`, DB/사용자 `kant_moa`, public 스키마 |
| DB 외부 포트 | 열지 않음. 팀원 PC 직접 DB 접속 경로 미설정 |
| 비밀 파일 | `/home/kant/kant-moa/backend.env`, `/home/kant/kant-moa/ngrok.yml`, 권한 600 |
| ngrok 실행 파일 | `/snap/bin/ngrok`, 확인 버전 3.39.13 |
| ngrok 서비스 | `/etc/systemd/system/kant-moa-ngrok.service`, User=kant |
| 업로드 볼륨 | `kant-moa_uploads_data` |

- ngrok는 사용자 PC가 아니라 **학원 서버**에서 실행 중이다. 사용자 PC를 꺼도 유지된다.
- 서버 자체·인터넷·API·DB가 정상이어야 외부 요청이 성공한다. 무료 ngrok 사용량 제한은 별개다.
- 4040은 서버 ngrok 관리 화면, 8022는 서버 API 포트다. PC localhost와 구분한다.
- 다른 프로젝트가 같은 PostgreSQL 컨테이너를 사용한다. dbresting 전체 down/reset/restart 금지.
- 비밀번호·토큰은 모델이 모른다. 사용자 직접 입력, Git/문서/채팅 출력 금지.

서버 조회 명령:

```bash
cd ~/kant-moa
docker compose -f compose.backend.yml ps
curl --fail --silent --show-error http://127.0.0.1:8022/health
systemctl status kant-moa-ngrok.service --no-pager
```

코드 배포는 배포할 커밋/브랜치와 작업 트리를 확인하고 소스를 갱신한 뒤
`docker compose -f compose.backend.yml up -d --build api`로 수행한다.
단순 push나 container restart로 소스가 자동 배포되지 않는다.

## 6. Git 현재 상태와 주의

2026-10-26 로컬 확인 결과 (원격 fetch는 이번 인계 작성에서 실행하지 않음):

- 브랜치 `feature/sangjae`, origin은 팀 저장소.
- HEAD `b9edd7f`: origin/main을 feature/sangjae에 병합한 커밋.
- 작업 커밋 `72c2cea` (`서버 완료`), 서버 clone 당시 main `9ff2018`.
- feature/sangjae push는 이전에 완료했다. 이후 PR 생성·머지 상태는 확인하지 않았다.
- 과거 PR이 원본 저장소 `jin-park0115/KANT_MOA`의 #172로 잘못 생성된 적이 있다.
  새 PR의 base repository는 반드시 `hiju200208-png/KANT_MOA_develop`인지 확인한다.
- 인계 작성 전 미커밋 파일: `docs/STAGING.md`, `deploy/staging/README.md`.
  ngrok 서비스 완료와 각 담당자 직접 migration 적용 방식을 갱신한 변경이므로 버리지 않는다.
- 이 인계 문서도 아직 커밋·push하지 않았다. 사용자 요청 없이 임의 push하지 않는다.
- `docs/PROJECT2.md`의 과거 HEAD·인증 미구현·ngrok 미설정 문구 중 일부는 오래된 기록이다.
  최신 상태는 STAGING과 이 인계 및 최신 코드/팀원 보고를 구분해 판단한다.

## 7. 공용 DB 운영 합의

- 각자 **로컬 Docker DB**에서 정상·실패·초기화·동시성 테스트한다.
- 검증 → PR 리뷰·병합 → **담당자가 직접 공용 DB에 적용**한다. 한 사람이 전부 적용하는 방식은 사용자의 선호가 아니다.
- 구조 변경은 Git의 Alembic 마이그레이션으로 남긴다. 공용 DB에서만 ALTER하고 끝내지 않는다.
- 최초 Alembic 기준을 P1과 먼저 맞춘다. 이후 최신 main·현재 revision 확인 → 적용 전 알림
  → 한 번에 한 명씩 적용 → revision·검증 결과 공유.
- migration head가 갈라지면 기준을 정리한다. 각자 초기 생성 revision을 별도로 만들지 않는다.
- 공용 초기화·drop_all/create_all·초기 SQL 재실행·실패 테스트 금지.
- 다른 담당/공통 테이블 변경은 담당자와 먼저 조율한다.
- 각자가 직접 적용하는 권한/접속 정보의 실제 전달 완료 여부는 확인되지 않았다.

## 8. P2가 먼저 읽을 코드

| 목적 | 파일 |
|---|---|
| 과제 공통 계약 | `docs/PROJECT2.md` |
| 공용 서버·DB 상태 | `docs/STAGING.md` |
| 실제 초기 스키마 | `backend/sql/001_create_tables.sql`, `backend/sql/README.md` |
| 공통 Base·세션 | `backend/src/database.py` |
| 공통 오류·목록 | `backend/src/core/errors.py`, `schemas.py` |
| P4 연결 인터페이스 | `backend/src/admin/application/ports.py`, `stock_service.py` |
| P4 설계 | `docs/admin/P4_ADMIN.md` |
| 기존 상품 데이터 변환 | `src/services/products.ts`, `productRows.ts`, `src/types/app.ts` |
| 찜·이미지·주변 카탈로그 | `src/services/wishlist.ts`, `storage.ts` 및 artists 등 실제 서비스 파일 |
| 기존 오류 코드 | `src/constants/error-messages.ts`, `src/services/errors.ts` |
| 데이터·이미지 원본 | 기존 `supabase/` SQL·시드와 로컬 assets 등 실제 보유 파일을 조사 |

프론트 코드 작성 전 AGENTS.md 지시에 따라 설치된 `node_modules/next/dist/docs/`의 관련 가이드를 읽는다.

## 9. 구현 계약

- 기능별 `presentation / application / domain / infrastructure` 4계층.
- Domain은 순수 Python, FastAPI/SQLAlchemy/Pydantic import 금지.
- ORM은 공통 `database.Base` 사용. 같은 테이블의 ORM을 담당별로 중복 정의하지 않는다.
- Repository는 AsyncSession을 받고 ORM↔Domain 변환, 필요한 flush만 한다. commit 금지.
- Application 서비스가 업무 단위 commit/rollback을 소유한다.
- 목록 `{items,total,page,size}`; 422 입력, 401 인증, 403 권한, 404 없음, 409 업무 위반.
- 오류 `{code,message}`; 기존 프론트 코드명 사용. 신규 code 추가는 합의가 필요하다.
- 찜의 user_id는 요청 본문을 믿지 않고 P1의 검증된 인증 사용자 UUID를 사용한다.
- 일반 상품 조회에는 hidden을 제외하고 hidden 상세도 404. 관리자 조회 정책과 구분한다.
- 시드 재실행 시 중복되지 않아야 한다. API 실패를 예비 데이터로 덮어 테스트 성공처럼 보이게 하지 않는다.

### P3/P4가 기다리는 재고 인터페이스 (우선 구현)

- 순수 도메인 `increase_stock(quantity)` / `decrease_stock(quantity)`:
  수량 양수, 재고 음수 불가, 재고 부족 예외.
- P2 Repository `get_variants_for_update(variant_ids)`:
  ID 중복 정리 및 오름차순 잠금, SQLAlchemy `with_for_update()`, 잠금 획득 후 최신 재고 사용.
  반환 객체·누락 ID 처리·save 함수명을 P3/P4와 맞춘다.
- 잠금부터 변경·저장까지 **같은 AsyncSession·같은 트랜잭션**을 유지한다.
  별도 세션/내부 commit/잠금 직후 rollback을 넣지 않는다.
- P4의 현재 로컬 port: lock_variant(id) → id/product_id/stock 객체 또는 None,
  increase/decrease → 도메인 적용·save/flush 후 재고 int 반환. 실제 adapter는 P4 infrastructure에 둔다.
- 모든 잠금 참여자가 같은 순서를 지켜야 한다. 순서 통일만으로 모든 deadlock 가능성이 없어지는 것은 아니다.

## 10. P2 실행 계획표

시간은 권장 배치다. 완료 기준을 충족한 뒤 다음 단계로 진행한다. 남은 기간이 짧아 공통 재고·상품 E2E를 우선한다.

| 순서·권장 시점 | 작업 | 산출물·완료 기준 |
|---|---|---|
| 0 · 10/26 시작 | 미커밋 문서 보존, 최신 팀 main/관련 PR 확인, P1/P3/P4 인터페이스 확인 | 현재 코드와 팀원 보고의 차이를 정리. 중복 모델·migration을 만들지 않을 기준 확정 |
| 1 · 10/26 최우선 | 상품 옵션 순수 도메인과 재고 증감 규칙 | 정상 증감·0/음수 수량·재고 부족 검증. SQL/HTTP 의존성 없는 단위 테스트 |
| 2 · 10/26 우선 | 상품·옵션·아티스트·카테고리 등 필요한 ORM과 재고 Repository | 기존 스키마와 일치. 실제 로컬 PostgreSQL에서 잠금·저장·rollback 검증. P3/P4에 import 경로·함수 계약 전달 |
| 3 · 10/26 | 최소 재현 시드·로컬 이미지 준비 | 판매중/품절/숨김·복수 옵션·검색/정렬을 검증할 데이터. 재실행 중복 없음. 팀원 테스트에도 제공 |
| 4 · 10/26~27 | 상품 목록·검색·필터·정렬·페이지네이션·상세 API | 실제 DB 검색, 안정된 정렬 tie-breaker, 정확한 total, hidden 제외·상세 404, 잘못된 page/size 422 |
| 5 · 10/27 | 찜 API와 P1 인증 연결 | 본인 목록·추가·해제, 중복 방지, 미인증 401, user_id 위조 방지. 없거나 숨긴 상품 정책 명시 |
| 6 · 10/27 | 기존 상품 목록·검색·상세·찜 화면을 FastAPI로 연결 | 실제 화면 → API → Domain → Repository → DB 증명. 새로고침·로딩·빈 결과·오류 처리, 이미지 표시 |
| 7 · 10/27 | 남은 카탈로그 기능과 기존 데이터·이미지 이관 | 아티스트·멤버·배너·공지·카테고리·인기 순위의 실제 화면 호출 조사 후 역할 범위 안에서 구현. 집계 기준 및 hidden 정책 확인 |
| 8 · 10/27 통합 | P3 결제/P4 조정의 공통 재고·판매 상태 통합 | 같은 옵션 동시 수정 시 유실 없음, 재고 부족 실패·주문 rollback 후 DB 일치. P4 임시 상태 UPDATE 대체 여부 결정 |
| 9 · 10/28 제출 전 | PR 리뷰·병합, 담당 변경 배포, 시연·일지·증빙 | 공용 DB 변경이 있으면 합의된 Alembic 순서로 직접 적용. 외부 Swagger와 담당 화면 재확인, 재현 명령·테스트 결과·남은 제약 기록 |

새 API 경로와 응답 필드명은 기존 프론트·팀 코드 확인 후 명세로 확정한다.
상품 핵심 후보는 GET /products, GET /products/{id}, 카테고리 조회, 인증된 찜 조회·추가·해제다.
이 경로들은 계획 후보이며 전부 구현·합의 완료된 것으로 간주하지 않는다.

### 검증 체크리스트

- [ ] 순수 재고 규칙 정상/실패 테스트
- [ ] 실제 PostgreSQL 잠금 대기·동시 차감·rollback 검증 (SQLite나 가짜 저장소만으로 대체하지 않음)
- [ ] 검색어·아티스트·카테고리·정렬·페이지 조합, 빈 결과·total 검증
- [ ] 없는 상품/hidden 404, 페이지 입력 오류 422
- [ ] 찜 인증 401·본인 범위·중복 처리 및 DB 무결성
- [ ] 4계층 책임·실제 ORM↔Domain 변환·Repository commit 없음
- [ ] 시드 중복 방지·이미지 정상·Supabase 대체 완료 범위 확인
- [ ] 담당 화면 E2E와 P3/P4 통합 결과
- [ ] PR 대상이 팀 저장소 main, 비밀값 미포함, DB 변경 이력·담당자 공유

## 11. 할 일별 상세 실행 목록

아래 목록은 앞으로 할 일이다. 아직 구현되지 않은 함수·경로를 이미 존재한다고 가정하지 않는다.

### 1단계. 최신 코드와 연결 계약 확인

- 진행 근거: [P2 연결 계약 확인 기록](products/P2_CONNECTION_CONTRACT.md). 아래 체크는 실제 확인 범위만 반영한다.
- [x] `git status`로 미커밋 문서를 확인하고 보존한다. 강제 reset·덮어쓰기를 하지 않는다.
- [x] 원격을 fetch하고 팀 main·각 담당 PR의 변경을 읽는다. 필요한 변경을 검토 후 작업 브랜치에 통합한다.
- [x] P1의 실제 인증 의존성 import 경로, 반환 사용자 객체, UUID 타입, 토큰 전달 방식과 오류 계약을 확인한다.
- [ ] P3/P4가 기대하는 잠금 함수의 인수·반환형, 누락 옵션 처리, save 함수, 세션 주입 방식을 합의한다.
- [x] P4가 이미 만든 조회 ORM·상태 변경 코드를 확인한다. 동일 테이블 중복 모델을 만들지 않는다.
- [x] 상품 status와 재고 기반 품절의 관계를 확정한다. 수동 sold_out을 유지할지, 옵션 없는 상품을 어떻게 다룰지 명시한다.
- [ ] P1과 Alembic revision 소유권·최초 공용 기준·P2 모델 import 위치·시드 진입점을 맞춘다.
- [x] 실제 프론트 호출을 조사해 API 요청/응답과 변환 위치를 짧은 명세로 남긴다.
- 2026-10-26 추가 확인: 재고 PR #42 병합 후 main은 `20edbcf`, 작업 브랜치도 fast-forward했다.
  P1 실제 코드・공용 Alembic 최종 기준, P3 세부 정책 및 P4 최신 미공개 코드 확인은 대기다.
  품절·수동 상태 유지 합의는 PR #1 댓글에서 확인했고, 옵션 없는 상품의 경계 정책도 후속 P4 답변으로 수락을 확인했다.
  기존 문서 상단의 과거 HEAD·P2 코드 없음 등의 기록과 현재 상태를 구분한다.
- P3 후속 답변(사용자 전달): P2 Repository·재고 메서드 재사용, 같은 세션·트랜잭션,
  전체 주문 항목 검증 후 한 번 commit·오류 rollback 방향 동의. 취소 복구·예외 매핑·구매 제한·중복 처리와
  실제 최신 코드 연결 가능 여부는 추가 확인 대기다. 상세 답변 제안은 연결 문서 3-1에 기록했다.
- P4 후속 답변(사용자 전달): 잠금 조회·누락/다른 상품 옵션 404+rollback·같은 객체 저장·같은 세션의 서비스
  commit/rollback·P2→P4 예외 변환 계약을 수락했다. 옵션 없는 on_sale도 품절로 계산하고 DB status는 유지한다.
  feature/chungman에 조회·상태 변경·재고 adapter를 push 예정이며, 실제 코드·모델 재사용·PR 테스트 결과는 확인 대기다.
- P1 후속 답변(사용자 전달): `auth.presentation.dependencies`의 CurrentUser/get_current_user/require_admin 계약 확인.
  두 의존성은 id(UUID)·email·nickname·role(USER/ADMIN 문자열)을 반환하며 역할은 DB 현재 사용자 기준이다.
  일반 인증 기능과 18개 테스트 통과는 P1 로컬 보고이며 아직 미커밋이다. 실제 PR 검증은 대기다.
  프론트 토큰 저장·복원은 미확정. 최초 로컬 revision/head `cd2b7db3c89b`, down_revision=None,
  users/token_blacklist/만료 인덱스 생성이며 공용 이력은 미확인이다. 전체 모델 수집 전 autogenerate,
  검증 없는 stamp·초기 SQL 재실행은 하지 않는다. 회원·관리자 초기화 P1/카탈로그 시드 P2이며,
  최초 공용 기준·모델 수집·시드 명령/실행 순서는 함께 확정해야 한다.
- 완료: 합의한 import 경로와 함수 계약을 문서에 기록하고 담당자에게 전달할 수 있다.

### 2단계. 순수 재고 도메인 만들기

- [ ] `products/domain/`에 옵션 엔티티를 만든다. 최소 id·product_id·stock 및 필요한 구매 제한 정보를 표현한다.
- [ ] 재고 증가/감소 함수에 0·음수 수량 거부, 재고 부족 거부, 변경 후 재고 음수 금지를 구현한다.
- [ ] 실패 시 객체의 재고가 부분 변경되지 않게 한다. 재고와 실제 판매 상태의 역할을 구분한다.
- [ ] 입력 오류·재고 부족 등의 도메인 예외를 정의하고 HTTP 변환은 presentation으로 분리한다.
- [ ] DB 없는 단위 테스트: 정상 입고, 정상 차감, 전량 차감 후 0, 부족, 0·음수, 실패 전후 재고 동일.
- 완료: P3/P4가 같은 규칙을 재사용할 수 있고 domain에 FastAPI·SQLAlchemy 의존성이 없다.

### 3단계. ORM·공통 재고 Repository 만들기

- 검증 기록: [P2 재고 Repository](products/P2_STOCK_REPOSITORY.md). P2 로컬 구현·검증은 완료,
  P1/P4 최신 미공개 코드 직접 대조·운영 adapter 통합은 대기다.
- [x] 초기 SQL과 최신 P1/P4 모델을 비교해 상품·옵션·아티스트·카테고리 등 필요한 모델을 공통 Base에 매핑한다.
- [x] bigint identity·UUID·timezone·NULL·FK·CHECK·가격 단위가 실제 테이블과 일치하는지 확인한다.
- [x] 옵션 조회와 ORM↔Domain 변환, 재고 저장/flush 함수를 만든다. Repository는 commit하지 않는다.
- [x] `get_variants_for_update(variant_ids)`에서 ID 중복을 제거하고 오름차순 FOR UPDATE를 수행한다.
- [x] 없는 ID·빈 목록·여러 옵션을 어떤 방식으로 반환/거부할지 명시하고 호출자가 누락을 놓치지 않게 한다.
- [x] P3/P4 서비스가 쓰는 AsyncSession을 그대로 주입받고 잠금을 commit/rollback까지 유지한다.
- [x] 실제 로컬 PostgreSQL의 독립 세션 두 개로 같은 옵션 차감 시 최종 재고·재고 부족 처리를 검증한다.
- [x] 테스트는 이벤트/동기화로 실행 순서를 제어한다. 단순 sleep이나 우연한 동시 실행만으로 증명하지 않는다.
- [x] rollback 시 재고 복구·잠금 해제를 검증하고 여러 옵션의 잠금 순서도 확인한다.
- [ ] P4의 VariantStockPort adapter 연결에 필요한 함수·예외·반환형 예시를 공유한다.
- 초기 SQL↔P2 ORM은 전용 로컬 DB로 대조 완료. 위 첫 항목의 최신 P1/P4 미공개 모델 대조는 아직 남았다.
  같은 세션 계약은 Repository와 현재 main의 P4 서비스+테스트용 adapter로 검증했고 실제 P3/P4 운영 연결과 구분한다.
  P4에 공유할 실행 가능한 adapter 예시를 테스트 파일에 작성했으며 아직 새 예시를 외부 전송하지 않았다.
  최종 전체 backend 75 passed(P2 28개 포함). NULL 구매 제한 저장·savepoint 경계 보호를 보완했다.
- 완료: 재고 유실·음수 없이 실제 DB 테스트가 통과하고 P3/P4가 연결할 수 있다.

후속 PR 확인: P1 #49(6644edd)·P4 #50(8b722cf) 대조 결과는 [PR 검토 기록](products/P1_P4_PR_REVIEW.md)에 있다.
P1 인증 반환 계약은 실제 코드와 일치하나 최초 migration의 role 자료형·UUID 기본값 차이가 있다.
P4 상태 변경·품절 규칙은 일치하고 중복 ORM은 없지만 P2 ORM 재사용·재고 adapter는 미완료다.
최초 DB 없는 선택 테스트 150 passed/2 skipped. 이후 Docker 기동 후 전용 로컬 DB에서 동일 PR 조합의
전체 테스트 171 passed(skip 없음)를 확인했다. 실제 revision을 별도 로컬 스키마에 적용해 role/UUID 기본값 차이를
재확인했고, auth metadata만으로는 나머지 16개 테이블의 삭제안이 생성되는 것도 비교만 수행해 확인했다.
삭제안·공용 migration은 실행하지 않았다. 문서 앞쪽의 PR 공개 전 대기 기록은 과거 상태다.

### 4단계. 로컬 재현 시드와 이미지 준비

- 진행 근거(2026-10-27 사용자 시작 지시 후): [4단계 로컬 시드·이미지 기록](products/P2_CATALOG_SEED.md).
  앞선 데모 7개 방식은 폐기하고 실제 프로젝트 SQL 전체·ZIP 이미지 전체 기준으로 교체했다.
  최신 팀 main 172409b에서 최종 210 passed/0 skipped. 아티스트 11·상품 389·옵션 642·상품 이미지 행 1390,
  원본 WebP 1847개 전체 서빙 확인. CLI 두 번 실행 후 ID·전체 값 유지 확인.
  사용자 승인 후 공용 DB 전체 카탈로그 입력·서버 이미지 배포·내부/외부 검증까지 완료했다.
  원본 공지의 고정 상품 ID 8건은 명시적 원본 SKU 경로 기준으로 보정했다.
  **P1 공통 실행 파일 연결은 후속이며, 5단계 상품 API로 진행하지 않았다.**
- [x] 기존 데이터/시드/이미지 파일이 어디에 있는지 조사한다. 원격 Storage 전체를 무작정 복사하지 않는다.
- [x] 검증용 데이터: 서로 다른 아티스트·카테고리, 판매중·품절·숨김, 복수 옵션, 재고 0/양수 상품을 준비한다.
- [x] 검색어가 상품명·아티스트 한글/영문명에 각각 걸리는 데이터와 동일 가격·동일 시각 정렬 데이터를 준비한다.
- [x] FK 순서대로 아티스트/카테고리 → 상품 → 옵션/이미지 등을 넣는다.
- [x] 재실행해도 중복되지 않는 식별 기준을 정한다. 상품명만 유일하다고 가정하지 않는다.
- [x] GENERATED ALWAYS IDENTITY에 기존 ID를 유지할지 새 ID로 매핑할지 결정한다.
  실제 카탈로그의 기존 ID를 OVERRIDING SYSTEM VALUE로 유지하고 sequence를 MAX(id) 이상으로 진행한다.
  기존 ID를 직접 넣는 경우 명시적 처리와 identity sequence 정합성이 필요하다.
- [x] DB 이미지 경로를 `/static/...` 또는 합의된 상대 경로로 변환하고 실제 파일 서빙을 확인한다.
  사용자 제공 ZIP의 원본 WebP 1847개 전체를 변환 없이 준비했다. 카탈로그 참조 이미지 누락은 0개다.
- [ ] P1 공통 시드와 진입점을 맞춘다. 타 담당 회원·주문 데이터를 삭제하거나 덮어쓰지 않는다.
- 완료: 빈 개인 DB에서 재현 가능하고 시드 두 번 실행 후 중복이 없으며 이미지가 표시된다.

### 5단계. 상품 목록·검색·상세 API

- [x] presentation: 검색어·아티스트/카테고리 slug·정렬·page·size 요청 스키마와 응답 스키마를 정의한다.
- [x] application: 조회 흐름과 없음 처리 등을 조율한다. 읽기 전용 조회를 위해 불필요한 commit을 넣지 않는다.
- [x] repository: 상품명·아티스트명 검색, slug 필터, hidden 제외, 정렬, offset/limit와 count를 구현한다.
- [x] 검색어의 빈 값·공백·길이·LIKE 와일드카드(%/_) 처리 정책을 정하고 SQL 값은 바인딩한다.
- [x] 정렬 기준이 같을 때 id로 순서를 안정화한다. count에는 페이지를 제외한 동일 필터를 적용한다.
- [x] JOIN으로 옵션·이미지가 여러 개인 상품이 중복되거나 total이 부풀지 않도록 조회 구조를 확인한다.
- [x] 상세 응답에 아티스트·카테고리·이미지 종류/순서·옵션·추가금액·최종 옵션 가격·재고·구매 제한을 반영한다.
- [x] ORM 관계를 응답 직렬화 중에 암묵적으로 lazy load하지 않도록 필요한 데이터를 명시적으로 로드한다.
- [x] 일반 상세에서는 없는 상품·hidden 모두 404. 품절 상품 상세 노출은 확정 정책을 적용한다.
- [x] 재고 기반 품절은 조회로 계산하고 단순 GET 요청에서 판매 상태를 UPDATE하지 않는다.
- [x] 목록/상세 API와 실제 DB 테스트: 검색·복합 필터·정렬·total·빈 결과·마지막 페이지·404·422.
- 완료: Swagger에서 실제 DB 데이터가 공통 형식으로 나오며 관리자 전용 hidden 정보가 노출되지 않는다.
  실행 앱의 Swagger 문서·OpenAPI 등록과 실제 DB API 호출을 자동 검증했다.
  [검증 결과: 신규 36개, 통합 246개 통과](products/P2_CATALOG_API.md). 서버 배포는 별도다.

### 6단계. 상품 찜·인증 연결

- [x] 현재 프론트의 목록/찜 ID 조회/추가/해제/토글 호출을 읽고 필요한 API를 확정한다.
- [x] add/remove를 멱등하게 할지 toggle을 유지할지 정한다. 동시 요청과 재시도 결과를 명시한다.
- [x] user_id는 P1 인증 의존성이 검증한 사용자에서 가져온다. 클라이언트가 다른 사용자 ID를 지정하지 못하게 한다.
- [x] wishlists의 복합 PK·FK를 유지하고, 본인 데이터만 조회·추가·삭제한다.
- [x] 없는 상품·hidden 상품 추가와 숨겨진 상품의 기존 찜을 어떻게 다룰지 확정한다.
- [x] 중복 INSERT는 DB 무결성과 합의된 API 의미로 처리한다. 모든 IntegrityError를 중복으로 간주하지 않는다.
- [x] 실제 무결성 오류를 처리한 세션은 rollback 또는 savepoint로 복구한다. 실패한 세션으로 계속 조회하지 않는다.
- [x] 테스트: 미인증/만료·블랙리스트 토큰, 사용자 A/B 분리, 중복 추가·반복 해제, 없는 상품·hidden 정책.
  P1이 제공한 인증 통합 테스트를 재사용하고 JWT 구현을 P2에 중복 작성하지 않는다.
- 완료: P1 실제 토큰으로 찜이 동작하고 다른 회원의 찜을 읽거나 변경할 수 없다.
  [집중 18개·전체 482개 통과, 실제 동시 요청·rollback 증거](products/P2_WISHLIST_API.md).

### 7단계. 상품·검색·찜 화면 연결

- [x] 설치된 Next.js 가이드와 AGENTS.md를 읽고 기존 화면·서비스·타입·캐시 사용처를 조사한다.
- [x] P1이 정한 API base URL·토큰 전달·로그인 상태 복원 방식으로 연결한다.
- [x] `products.ts`, `wishlist.ts` 등 필요한 서비스만 FastAPI 요청으로 바꾼다.
- [x] 백엔드 snake_case와 기존 camelCase, page/size와 기존 limit/offset, 이미지 URL 변환을 한곳에서 일관되게 처리한다.
- [x] 공개 상품 조회와 사용자별 찜 조회의 캐시를 구분한다. 개인 토큰/찜 결과가 공용 캐시에 섞이지 않게 한다.
- [x] 오류를 예비 상품 데이터로 덮어 성공한 것처럼 보이게 하지 않는다.
- [x] 로딩·빈 검색 결과·요청 실패·상품 404·미로그인 찜 안내·연타 방지·찜 실패 원복을 확인한다.
- [x] P4가 판매 상태를 바꾼 뒤 사용자 화면에 반영되는 캐시 정책을 맞춘다.
- [x] 실제 화면에서 상품 검색 → 상세 → 로그인 → 찜 → 새로고침 후 유지까지 검증한다.
- [x] 브라우저와 서버 측 fetch의 접근 주소 차이, CORS, /static 이미지 설정을 확인한다.
- 완료: Supabase 카탈로그/찜 호출을 대체한 범위가 명확하고 PC·모바일에서 주요 동작을 확인했다.

- [x] Windows production build 오류 해결 후 `npm run build`와 `next start` 실제 인증·찜 재검증 완료.

### 8단계. 나머지 카탈로그·기존 데이터 이관

- [x] 아티스트 목록/상세·멤버·카테고리·홈/아티스트 배너·공지·인기 상품/아티스트 좋아요의 실제 호출 목록을 만든다.
- [x] 역할표와 남은 화면을 기준으로 필수 구현을 확정한다. 구현하지 않은 기능을 임의로 완료/선택 처리하지 않는다.
- [x] 카테고리 is_active, 배너 is_active·노출 기간·sort_order, 공지 공개 시각 등 기존 필터를 확인한다.
- [x] 인기 순위의 기준을 확정한다. 결제 완료 주문 집계라면 취소·미결제 제외 및 P3 주문 상태 의미를 맞춘다.
- [x] 기존 상품/옵션/멤버/이미지 관계와 내부 링크 ID가 이관 후에도 일치하는지 확인한다.
- [x] shop_settings는 P3 배송비 계산에도 필요하므로 시드·조회 소유권과 값을 합의한다.
- [x] API별로 입력·조회·응답 변환과 실제 화면을 확인한다. 지나치게 일반화한 범용 프레임워크를 만들지 않는다.
- 완료: P2 담당 화면에서 필요한 카탈로그 데이터가 실제 DB와 새 API로 제공된다.

### 9단계. 팀 통합·서버 반영·제출 증빙

- [ ] P3 결제와 P4 재고 조정이 P2 도메인·잠금 조회를 같은 세션에서 호출하는지 실제 코드를 확인한다.
- [ ] 실패 테스트: 재고 부족, 여러 옵션 중 한 옵션 실패, 결제 실패 후 주문/재고 전체 rollback, 잘못된 상태 변경.
- [ ] 동시성 테스트: 같은 옵션을 주문/관리자가 동시에 수정해도 재고 유실·음수가 생기지 않음.
- [ ] 구매 제한의 집계 범위와 취소 주문 처리 방식은 P3와 맞춘다. P2가 주문 계산을 중복 소유하지 않는다.
- [ ] P4 상태 변경 함수 연결 여부와 관리자 403·일반 hidden 404를 확인한다.
- [ ] PR에 변경 내용·실제 검증 결과·미완료·DB 변경 여부를 적고 팀 저장소 main으로 리뷰 요청한다.
- [ ] DB 변경이 있으면 P1과 맞춘 Alembic 이력/단일 head 기준으로 담당자가 순차 적용한다.
- [ ] 초기 데이터 배포와 API 이미지 재빌드를 구분한다. 초기 SQL 재실행·전체 데이터 삭제를 하지 않는다.
- [ ] 공개 /health·/docs와 배포된 담당 API·화면을 확인한다. 로컬 통과를 서버 완료로 기록하지 않는다.
- [ ] 제출 증빙: 검색/페이지·상품 상세·찜 인증·404/409·실제 DB 전후·재고 동시성/rollback 결과.
- [ ] 개인 일지에 역할·문제·수행·해결·결과를 기록하고 PR/커밋·테스트 명령·시연 링크를 연결한다.
- 완료: 다른 팀원이 문서 명령으로 재현 가능하고 제출 시연에서 담당 E2E와 실패 처리를 설명할 수 있다.

## 12. 새 채팅에 붙여넣을 시작 요청

> 이 저장소의 `docs/SANGJAE_HANDOFF.md`, `docs/STAGING.md`, `docs/PROJECT2.md`와 AGENTS.md를 먼저 읽어줘.
> 나는 이상재(P2)이고, 공용 DB·서버 준비를 마쳤으니 이제 내 상품·카탈로그 기능을 구현할 거야.
> 미커밋 문서 변경을 보존하고 최신 팀 코드/PR과 P1·P3·P4 계약부터 확인해줘.
> 가장 먼저 P3·P4가 쓸 순수 재고 도메인과 `get_variants_for_update` Repository를 실제 로컬 PostgreSQL로 검증하고,
> 상품 검색·목록·상세·찜·화면 연결로 진행해줘. 작은 단계별로 설명하며 실제 구현과 테스트까지 해줘.
> 공용 DB는 실패 테스트나 초기화에 사용하지 말고, 새 인증/상품 코드가 이미 배포됐다고 가정하지 마.
> 공통 파일·Alembic 초기 이력은 P1과 맞추고, push나 서버 반영은 요청한 범위를 확인하고 진행해줘.
