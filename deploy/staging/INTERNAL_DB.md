# 기존 PostgreSQL 내부 연결 준비

프론트·FastAPI는 Docker를 유지한다. 서버 PostgreSQL의 기존 `kant-moa` DB를 사용하고,
팀원용 TCP ngrok 주소와 DB 데이터·계정 비밀번호는 유지한다.

최신 사전 확인: 앱 네트워크 `172.22.0.0/16`, 호스트 게이트웨이 `172.22.0.1`,
DB·계정 `kant-moa`. 연결 실패는 SQLSTATE 28000 / `PG_HBA_REJECTED`였다.
Docker 서비스는 enabled/active, 앱 서비스 3개는 restart=unless-stopped다.

## 1. 접속 허용 준비

`allow_internal_db.py --apply`는 학원 서버의 관리자 권한이 필요하다.
배포 프로젝트·API 이미지·Docker 네트워크가 사전 확인과 다르면 변경 없이 중단한다.

추가할 규칙은 다음 한 줄이다. 현재 앱 네트워크의 해당 DB·계정에만 SCRAM 인증을 허용한다.

```text
host "kant-moa" "kant-moa" 172.22.0.0/16 scram-sha-256
```

- 외부 연결과 호스트 PostgreSQL의 DB OID·서버 시작 시간을 먼저 대조한다.
- 기존 HBA에 문법 오류가 없고 기존 계정이 SCRAM 비밀번호를 쓰는지 확인한다.
- root 전용 원본 백업을 만들고 파일 소유자·권한을 보존해 원자적으로 변경한다.
- 문법을 검사한 뒤 `pg_reload_conf()`로 적용하며 PostgreSQL은 재시작하지 않는다.
- 컨테이너의 내부 연결이 외부 연결의 실제 세션을 볼 수 있어야 성공으로 판단한다.
- 실패하면 원본을 복구하고 reload한다. 다른 관리자가 파일을 바꾼 경우 덮어쓰지 않는다.
- SQL·비밀번호·연결 문자열을 오류 출력에 노출하지 않는다.

공식 근거: [HBA 규칙과 적용](https://www.postgresql.org/docs/18/auth-pg-hba-conf.html),
[설정 reload](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADMIN-SIGNAL).

로컬 검증: 일회용 PostgreSQL 18에서 규칙 문법·DB/계정 범위·reload·원복 통과.
별도 네트워크 차단 컨테이너에서 성공·연결 실패 복구·문법 실패·동시 수정 보호 통과.

## 2. 후보와 운영 교체

1단계 성공은 접속 허용 완료를 뜻하며 실행 중 API의 DATABASE_URL을 바꾸지 않는다.
이후 최신 팀 main으로 후보 API를 만들고 내부 DB 동일성·인증 설정 보존·상품·이미지·Google
로그인 진입 경로를 읽기 전용으로 검증한 뒤 운영에 반영한다. SQL·시드·마이그레이션은 실행하지 않는다.
향후 Docker 네트워크를 새로 만들거나 서브넷을 바꾸면 이 내부 주소와 HBA 범위를 다시 검증해야 한다.

## 1단계 서버 적용 결과

사용자 결과 `INTERNAL_DB_ACCESS_READY`, `SSH_EXIT=0`, 동일 DB 세션 검증 통과.
백업: `~/kant-moa/backups/internal-hba-20261028T021938127007Z`.
내부 쿼리 왕복 1.28/0.68/0.60ms, API 연결 주소와 DB 데이터는 변경하지 않았다.

## 후보 검증 도구

`internal_db_candidate.py`는 최신 팀 main을 고정한 소스 묶음을 검증·빌드한다.
현재 API의 유효 설정과 JWT·Google client ID를 개인 파일로 보존하고 DB URL의 호스트·포트만
내부 게이트웨이로 바꾼다. 비밀 파일은 빌드 컨텍스트 밖에 두며 로그·출력에 노출하지 않는다.

후보 컨테이너는 운영 서비스와 다른 이름을 쓰고, 승인된 기존 앱 네트워크에 연결한다.
프록시는 localhost의 빈 포트만 사용한다. 후보의 assets·uploads 마운트는 읽기 전용이다.
후보 설정·공개 상품/상세/이미지·Google nonce 쿠키·미인증 401·OpenAPI와 공개 DB 전체 지문을 대조한다.
공용 DB에 회원 생성·실제 로그인·주문·재고 쓰기를 하지 않는다.

실패 시 후보 컨테이너만 정리하고 현재 API·프론트·프록시와 DB 데이터는 유지한다.
성공 보고 `INTERNAL_SITE_CANDIDATE_READY`를 확인한 뒤 운영 교체는 별도 단계에서 수행한다.

## 후보 서버 검증 완료

- 앱 커밋 `9aa513889060ab39dd07d836c21fb03f271c95b7`.
- 소스 SHA256 `754a96c75f5918e97a262aad1af0a77f8ddd244311d238799e34bbb893b53dcc`.
- release `~/kant-moa/internal-releases/internal-20261028T023408Z-9aa5138`.
- 사용자 결과 `INTERNAL_SITE_CANDIDATE_READY`, 공개 상품 387개·API 경로 49개.
- Google 설정·보호 API 401·동일 DB·DB 전후 지문·기존 인증 설정 보존 확인.
- 후보 내부 전체 HTTP 응답: health 0.005초, 홈 0.290초, 상품 0.043초, 로그인 0.039초.
  공개 ngrok 방문 시간·실제 영상 시작 시간과는 구분한다.

## 운영 전환 도구

`switch_internal_db.py`는 위 후보의 소스 지문·현재 컨테이너·운영 포인터를 다시 대조한다.
Google 설정·JWT·동일 DB·원본 이미지/업로드 마운트를 재확인하고, 검증된 이미지 ID로 API와 web만
`--no-deps --no-build` 교체한다. 프록시 컨테이너는 유지하고 새 IP를 인식하도록 Nginx만 reload한다.

기존 이미지와 환경·운영 포인터는 `internal-db-state/<release>/`와 before 이미지 태그에 보존한다.
실패하면 이전 API·web 이미지와 설정을 복구하며 DB 데이터를 자동 복원하지 않는다.
다른 배포가 운영 포인터를 바꿨다면 덮어쓰지 않고 수동 복구 필요를 보고한다.
성공 시 후보 컨테이너만 정리하고 활성 상태에 `api_override`와 `web_override`를 기록한다.

**후속 배포는 api_override → web_override 순서로 둘 다 포함하고, 같은 파일이면 한 번만 포함한다.**
`deploy_web.py`도 이 순서를 유지하도록 보완했다. 이전 외부 DB 환경 파일만으로 전체 스택을 다시
올리면 내부 연결을 잃을 수 있으므로 현재 `active-site.json`을 먼저 확인한다.

로컬 검증: 운영 교체 성공·공개 실패 복구·부분 교체 실패·인증값 변경·동시 DB/포인터 변경 보호 통과.
프론트 단독 배포 성공/복구에서 내부 DB override 유지·중복 방지 통과.
별도의 네트워크 없는 실제 로컬 Compose 서비스에서도 이미지 ID 교체와 복구를 확인했다.

## 운영 전환 완료 (2026-10-28 KST)

사용자 실행 결과 `INTERNAL_DB_DEPLOY_SUCCESS`, `SSH_EXIT=0`, rollback 없이 성공했다.
앱 커밋·소스 SHA256·release는 위 후보와 같다. 설정·이전 이미지·DB 지문 백업은
`~/kant-moa/internal-db-state/internal-20261028T023408Z-9aa5138`에 보존했다.

- Docker 프론트·API 유지, API DB 주소는 `172.22.0.1:5432`, DB는 기존 `kant-moa`.
- 동일 DB·DB 전후 지문·Google/JWT 설정 보존, 공개 상품 387개·API 경로 49개·미인증 401 확인.
- assets/uploads 원본 마운트와 쓰기 권한 보존. 프록시 컨테이너와 외부 접속 주소 유지.
- 서버 내부 전체 HTTP 응답: health 0.004초, 홈 0.212초, 상품 0.049초, 로그인 0.030초.
- 공개 전체 HTTP 응답: health 0.249초, 홈 4.147초, 상품 1.941초, 로그인 1.269초.
  이 배포 검사는 urllib 기본 요청으로 전체 응답을 읽는 시간이며 브라우저 화면 표시·압축 응답·
  영상 재생 시작과 구분한다. 외부 전송 시간은 별도로 확인해야 한다.
- 첫 전환 시도는 ID 비교에서 서비스 변경 전 중단했다. `docker ps -q`의 12자리와
  `compose ps -q`의 64자리를 raw 비교한 도구 오류를 실제 로컬 컨테이너로 재현했다.
  운영 컨테이너의 inspect 전체 ID로 비교하도록 수정하고, 길이 차이 성공·복구 및 실제 다른
  컨테이너일 때 변경 전 중단을 검증한 후 위 두 번째 실행이 성공했다.

### 전환 후 공개 gzip 응답 확인

PC에서 `Accept-Encoding: gzip`을 명시한 읽기 전용 요청으로 실제 gzip 응답을 확인했다.
동시 요청 최대 2개의 단일 표본이며, 브라우저 렌더링 완료나 장기 평균 성능을 뜻하지 않는다.

| 경로 | 압축 전 HTML | 전송 bytes | 응답 전체 수신 |
| --- | ---: | ---: | ---: |
| `/` | 339,564 | 47,273 | 1.197초 |
| `/products` | 118,643 | 17,025 | 0.706초 |

두 페이지 모두 200·`Content-Encoding: gzip`이었다. 배포 검사에 나온 홈 4.147초·상품 1.941초와는
요청 압축 조건·시점이 다르므로 그대로 대조하지 않는다. 추가 서버 설정은 바꾸지 않았다.
