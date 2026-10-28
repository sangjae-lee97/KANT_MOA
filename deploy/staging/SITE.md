# 학원 서버 홈페이지·API 배포

한 서버에서 Next.js, FastAPI, Nginx를 각각 컨테이너로 실행한다.
기존 ngrok는 그대로 `127.0.0.1:8022`에 연결한다.

| 외부 경로 | 처리 |
| --- | --- |
| `/` | Next.js 홈페이지 |
| `/api/` | FastAPI, 접두 경로 제거 후 전달 |
| `/api/docs` | Swagger UI (인증 주소 `auth/login`은 `/api` 기준 상대 경로) |
| `/api/chat` | 기존 Next.js 챗봇 Route Handler |
| `/health` | 기존 FastAPI health 호환 경로 |
| `/static/`, `/uploads/` | 기존 이미지 주소 호환 경로 |

## 보존 대상

- 서버의 기존 `~/kant-moa/backend.env`를 Compose `env_file`로 읽는다. JWT와 DATABASE_URL을 다시 만들지 않는다.
- 현재 외부 DB 이름은 **kant-moa**다. 과거 Docker 내부 `kant_moa`와 구분한다.
- 기존 원본 assets 디렉터리를 읽기 전용으로 연결한다. products 1,800개·artists 47개 파일을 보존한다.
- 기존 업로드 볼륨의 실제 디렉터리를 그대로 연결한다. 빈 새 볼륨으로 교체하지 않는다.
- Dockerfile·컨테이너 시작 명령에는 SQL·Alembic·시드 실행이 없다.
- `.dockerignore`로 비밀 환경 파일·로컬 DB 덤프·원본 이미지·가상환경을 빌드 컨텍스트에서 제외한다.
- Docker Official Image의 ECR Public 배포본을 사용한다. Docker Hub 인증 서버의 TLS 연결 실패를 우회하기 위해 인증서 검사를 끄지 않는다.

## 배포 순서

1. `site_preflight.py`로 기존 API·DB 식별·JWT·마운트·여유 공간을 조회한다.
2. `site_candidate.py`로 별도 release 디렉터리와 별도 Compose 프로젝트를 생성한다.
   기존 API가 점유한 8022는 유지하고, 후보 Nginx만 localhost 8030에서 확인한다.
3. 후보에서 health·OpenAPI·카탈로그·페이지·이미지와 DB 전후 지문을 확인한다.
   공용 DB의 쓰기 테스트나 테스트 계정 생성은 하지 않는다.
4. 후보 검증 결과를 확인한 뒤 `site_switch.py`에서 소스·JWT·DB·이미지 마운트를 다시 확인한다.
   기존 API 이미지·Compose·환경 파일의 복구 사본을 확보하고 8022를 Nginx로 전환한다.
   이 단계는 후보 스크립트에 포함하지 않는다. 빌드·SQL·마이그레이션을 다시 실행하지 않는다.
5. 공개 홈페이지·`/api/docs`·인증 없는 보호 API 401을 확인한다.
   실패하면 새 gateway를 중지하고 기존 API를 다시 시작한다. DB를 자동 복원하거나 초기화하지 않는다.

배포 변수: `SITE_RELEASE`, `SITE_PUBLIC_ORIGIN`, `SITE_API_ENV_FILE`, `SITE_ASSET_DIR`,
`SITE_UPLOAD_DIR`, `SITE_PORT`. 실제 비밀값을 포함한 env 파일이나 펼쳐진 Compose 설정은 Git·채팅에 올리지 않는다.
전체 스택에 `down -v`를 실행하지 않는다. 기존 stage5·catalog·backups 디렉터리도 보존한다.

전환 성공 시 `~/kant-moa/active-site.json`에 실행 release·Compose 프로젝트·환경 파일 위치를 기록한다.
새 배포 관리 시 해당 프로젝트와 release의 `site.env`를 사용한다.
홈페이지 단독 배포 후에는 `active-site.json`의 `web_override`도 Compose `-f` 인수에 추가한다.
해당 override는 실제 web 환경값을 포함할 수 있는 서버 전용 비밀 파일이므로 Git·채팅에 복사하지 않는다.
2026-10-28 배너 개선 web 커밋 `cf82ef7` 단독 배포 완료. API 컨테이너·DB 내용 동일 확인.
web release는 `~/kant-moa/web-releases/web-20261027T231624Z-cf82ef7`이며,
측정 범위·소스 식별·백업 정보는 [배너 배포 기록](../../docs/products/P2_HERO_LOADING.md)을 참조한다.
이후 2026-10-28 경량 영상 web 커밋 `28e695e`를 단독 배포했다. 현재 web release는
`~/kant-moa/web-releases/web-20261027T234206Z-28e695e`다. API 컨테이너·DB 내용 동일을 확인했다.
새 영상 URL·파일 크기·해시·다운로드 측정은 [경량 영상 배포 기록](../../docs/products/P2_HERO_VIDEO_ENCODING.md)을 따른다.
과거 `compose.backend.yml up`을 실행하면 8022를 두 서비스가 차지하려 하므로 기존 API용 명령을 재사용하지 않는다.

## 학원 서버 후보 검증 (사용자 실행 결과)

- 후보: `site-20261027T112518Z-602d436c`, 기준 main `adfc4e6`와 배포 구성 변경.
- 소스 SHA256: `602d436c308c187da34377f31ee36b8b53ad5835cc6fb281ed68185de2e475c0`.
- `SITE_CANDIDATE_READY`, `SSH_EXIT=0`, 공개 상품 387개.
- 후보 홈페이지·상품·아티스트·로그인·health·OpenAPI·Swagger 모두 200.
- `public_api_changed=false`, `database_unchanged=true`. 공개 포트 전환 완료와 구분한다.
- 전환 스크립트의 성공·공개 확인 실패 시 기존 API 복구 흐름을 mock 검사로 확인했다.
  실제 서버에서의 전환·복구 수행 결과는 별도 기록한다.

## 공개 전환 완료 (2026-10-27 KST, 사용자 실행 결과)

- `SITE_DEPLOY_SUCCESS`, `SSH_EXIT=0`, 위 후보와 동일한 release·소스 SHA256.
- 내부·공개 모두 홈페이지 200, Swagger 200, API 경로 45개, 공개 상품 387개.
- 보호 API에 토큰 없이 접근하면 401. 실제 계정 생성·주문·재고 쓰기 검사는 공용 DB에서 하지 않았다.
- `database_unchanged=true`, `rollback=null`. SQL·시드·마이그레이션 실행 없음.
- 복구 사본: `~/kant-moa/backups/before-site-20261027T112518Z-602d436c`.
- 실행 release: `~/kant-moa/site-releases/site-20261027T112518Z-602d436c`.
- 홈페이지: https://letdown-kilometer-nutcase.ngrok-free.dev/
- Swagger: https://letdown-kilometer-nutcase.ngrok-free.dev/api/docs
- 기존 공개 `/products`는 이제 웹 페이지다. API 클라이언트는 `/api/products` 등 `/api` 접두 경로를 사용한다.
- 기준 main은 `adfc4e6`이며 배포 구성·Swagger 상대 인증 주소 수정은 당시 미커밋 소스다.
  실행 소스는 위 SHA256으로 식별한다. 후속 Git 정리 전 main과 실행 이미지가 완전히 같다고 표현하지 않는다.

## 로컬 검증 (2026-10-27)

- Linux Docker에서 API·Next.js standalone 이미지 빌드 성공.
- 별도 UUID 프로젝트의 일회용 PostgreSQL에만 기존 migration·실제 카탈로그를 적용했다.
- Nginx 경유 `/`, `/products`, `/artists`, `/login`, `/health`, `/api/health`,
  `/api/openapi.json`, `/api/products?size=1`, `/api/docs` 모두 200.
- OpenAPI servers `/api`, 상대 인증 경로 `auth/login` 확인. 공통 회귀 검사 2개 통과.
- 실제 브라우저에서 원본 이미지·회원가입→자동 로그인→상품 찜→새로고침 유지 확인.
- 이 결과는 로컬 검증이며 학원 서버 배포 완료를 의미하지 않는다.

## 최신 운영 반영 완료 (2026-10-28)

아래는 사용자의 SSH 실행 결과로 확인한 후속 운영 상태다. 위 최초 배포 기록과 구분한다.

- `LATEST_MAIN_DEPLOY_SUCCESS`, `INTERNAL_DB_DEPLOY_SUCCESS`, `SSH_EXIT=0`, rollback 없음.
- API·프론트 애플리케이션 커밋: `e0c7ad8f3f0d551d4b849fa513db34acffcda0a0` (PR #85 포함).
- 배포 소스 SHA256: `dabcb253bfd3c7cf44c55bcb2896e7e084d39907cabb15ec50c2ee6c1b6dd298`.
- release: `/home/kant/kant-moa/internal-releases/main-20261028T090748285927Z-e0c7ad8`.
- 이전 이미지·활성 설정·DB 지문 백업: `/home/kant/kant-moa/internal-db-state/main-20261028T090748285927Z-e0c7ad8`.
- 후보·내부·공개 검증: 공개 상품 388개, OpenAPI 경로 51개, Google 설정 보존, 보호 API 미인증 401.
- `/forgot-password`·`/reset-password` 200, 비밀번호 재설정 API 2개 등록 확인.
- `PASSWORD_RESET_DEMO=false` 유지. 메일 발송은 미구현이므로 이 기록을 실제 회원의 비밀번호 찾기 전달 경로 완성으로 표시하지 않는다.
- 후보·내부·공개 칸트봇 실제 AI 답변 200. 기존 서버 Gemini 키를 보존하고 재입력하지 않았다.
- API→DB는 `172.22.0.1:5432 / kant-moa`, 같은 DB·DB 지문 보존. 추가 migration·초기 SQL·시드는 실행하지 않았다.
- 기존 JWT·Google 설정·원본 assets/uploads 마운트·프록시 컨테이너를 유지했다.
- 이번 도구는 `deploy_latest_site.py`가 기존 후보·전환/복구 도구를 재사용한다. 도구·운영 문서의 미커밋 변경과 애플리케이션 main 커밋을 구분한다.

후속 배포는 `~/kant-moa/active-site.json`의 `api_override`와 `web_override`를 함께 읽는다.
이전 API 단독 Compose를 실행하거나 실패 시 DB를 자동 복원하지 않는다.
