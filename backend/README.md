
# 백엔드 환경 (Django)

백엔드·크롤링·전처리의 Python 의존성은 `backend/requirements.txt`로 관리합니다.
모든 명령은 프로젝트 루트 기준입니다.

```bash
conda activate skn34-backend
python -m pip install -r backend/requirements.txt
python -m django --version
```

환경이 없으면 먼저 `conda create -n skn34-backend python=3.12`로 생성합니다.
Django API와 PostgreSQL/pgvector 모델이 구현되어 있습니다. DB 접속값은 환경변수와
`backend/.env`에서 읽으며, 컨테이너 내부에서는 `DB_HOST=db`, 로컬 Docker DB에
호스트에서 접속할 때는 `DB_HOST=127.0.0.1`을 사용합니다.

## 인증 API

| 기능 | Django 직접 호출 | Nginx 경유 |
|---|---|---|
| 회원가입 | `POST /auth/signup/` | `POST /api/auth/signup/` |
| 로그인 | `POST /auth/signin` | `POST /api/auth/signin` |
| 토큰 갱신 | `POST /auth/token/refresh/` | `POST /api/auth/token/refresh/` |
| 사용자 조회 | `GET /auth/user` | `GET /api/auth/user` |
| 로그아웃 | `POST /auth/logout` | `POST /api/auth/logout` |
| 비밀번호 변경·재설정 | `POST /auth/password` | `POST /api/auth/password` |
| 재설정 메일 요청 | `POST /auth/password/request` | `POST /api/auth/password/request` |

로그인은 `access`와 `refresh`를 반환합니다. 사용자 조회에는
`Authorization: Bearer <access>`가 필요하며, 성공하면 `id`, `username`, `email`을
반환합니다. 토큰 미전달은 `401 {"detail":"인증이 필요합니다."}`, 잘못되거나 만료된
토큰은 JWT 검증 오류와 함께 `401`을 반환합니다.

### 로그아웃 계약

```http
POST /api/auth/logout
Content-Type: application/json

{"refresh":"<로그인에서 발급받은 refresh>"}
```

- 성공 응답은 `200 {}`입니다. 기존의 본문 없는 요청은 더 이상 지원하지 않습니다.
- refresh 누락·빈 값·객체/배열 등 잘못된 본문 형식은 `400`입니다.
- 위조·만료·이미 폐기된 refresh 또는 access token 제출은 `401`입니다. 반복 요청도 `401`입니다.
- Authorization 헤더는 필요하지 않으며, 잘못되거나 만료된 access 헤더가 있어도 본문의 refresh를 검증합니다.
- 제출한 refresh만 폐기합니다. 같은 사용자라도 다른 로그인에서 발급한 토큰은 유지합니다.
- 이미 발급한 access는 남은 유효기간(최대 5분) 동안 유효합니다. refresh 유효기간은 1일이며 rotation은 사용하지 않습니다.
- 클라이언트는 로그아웃 처리 후 저장한 access·refresh와 로그인 상태를 삭제해야 합니다. 요청 실패 시에는 서버 폐기 성공을 단정하지 않습니다.
- 비밀번호 변경·재설정 시 기존 access와 refresh를 거부하는 비밀번호 해시 검증은 유지합니다.

프론트 인증 화면과 토큰 저장·삭제는 아직 구현되어 있지 않습니다.

### 마이그레이션과 만료 토큰 정리

Simple JWT의 기본 blacklist 앱과 migration을 사용합니다. API 실행 전에 적용합니다.

```bash
python backend/manage.py migrate
```

Compose는 백엔드 시작 전에 `migrate`를 실행합니다. 기존 로그인에서 발급한 유효한
refresh도 로그아웃 시 blacklist에 등록됩니다. 토큰 원문은 로그나 공유 문서에 남기지 않습니다.

운영 스케줄러에서 다음 명령을 **하루 한 번** 실행하여 만료된 outstanding·blacklist
레코드를 정리합니다. 이 저장소는 스케줄러를 자동 설치하지 않습니다.

```bash
docker compose exec -T backend python manage.py flushexpiredtokens
```

### 회귀 테스트

별도 PostgreSQL/pgvector 테스트 DB를 생성할 수 있는 테스트 전용 접속값을 사용합니다.
아래 명령은 `test_<DB_NAME>` DB를 생성·삭제합니다. 운영 DB 계정으로 실행하지 않습니다.

```bash
python backend/manage.py test accounts.test.test_logout accounts.test.test_tokens accounts.test.tests --noinput
```

실제 로그인 JWT로 로그아웃·갱신 거부·5분 access 수명·다른 로그인 유지·입력 검증과
기존 비밀번호 변경·재설정을 검증합니다. CI의 `manage.py check`는 API 테스트를 대신하지 않습니다.

[Postman 컬렉션](../docs/postman/auth.postman_collection.json)을 가져와 `01 자동 회귀`만
실행합니다. `base_url`은 Django 직접 호출 시 `http://127.0.0.1:8000`, Nginx 경유 시
`http://localhost/api`이며 끝에 `/`를 붙이지 않습니다. 테스트 계정은 DB에 남으므로
테스트 전용 환경에서 실행하고, 실행 후 저장된 토큰은 지우고 공유합니다.

[전체 실행 안내](../README.md) · [VS Code 설정](../docs/환경설정_my_venv.md)

## 커뮤니티 임시저장·게시 API

모든 임시저장 API는 JWT가 필요하고 본인 소유의 미게시 초안만 조회합니다. `PATCH`는
현재 `revision`과 선택적인 `imageIds`(최대 10개)를 받으며, 다른 초안·게시글에 연결된
이미지는 가져올 수 없습니다. revision 충돌은 `409`입니다.

| 기능 | Django 직접 호출 | Nginx 경유 |
|---|---|---|
| 목록·생성 | `GET\|POST /community/drafts/` | `GET\|POST /api/community/drafts/` |
| 조회·수정·삭제 | `GET\|PATCH\|DELETE /community/drafts/<uuid>/` | `GET\|PATCH\|DELETE /api/community/drafts/<uuid>/` |
| 게시 | `POST /community/drafts/<uuid>/publish/` | `POST /api/community/drafts/<uuid>/publish/` |

게시는 본문 `{"revision": <현재 revision>}`과 1~128자 `Idempotency-Key` 헤더가
필수입니다. 게시글 검증과 이미지 이동은 한 트랜잭션에서 수행하며, 같은 키·revision·
내용의 성공 재시도는 기존 게시글을 `200`으로 반환합니다. 키·revision·내용이 달라진
재시도는 `409`이고, 실패한 초안은 삭제하거나 비우지 않습니다. 성공한 초안은 일반
임시저장 조회·수정·삭제에서 `404`로 숨깁니다.
게시글을 삭제하면 소비된 초안도 함께 삭제되어 같은 내용을 다시 게시할 수 없습니다.

## 커뮤니티 이미지 API

Compose의 `minio` 서비스는 이미지를 private bucket에 저장하고 Django만 파일을
읽습니다. `.env.example`의 `MINIO_ROOT_PASSWORD` placeholder를 로컬 전용 비밀값으로
교체한 뒤 사용합니다. 업로드는 JWT와 multipart `image` 필드가 필요합니다.

| 기능 | Django 직접 호출 | Nginx 경유 |
|---|---|---|
| 업로드 | `POST /community/images/` | `POST /api/community/images/` |
| 읽기 | `GET /community/images/<uuid>/` | `GET /api/community/images/<uuid>/` |
| 삭제 | `DELETE /community/images/<uuid>/` | `DELETE /api/community/images/<uuid>/` |

JPEG, PNG, WebP 정지 이미지만 허용하며 입력·정규화 결과는 5MiB 이하, 해상도는
2천만 픽셀 이하입니다. 서버가 다시 인코딩해 EXIF를 제거합니다. 연결되지 않은
이미지와 draft 이미지는 소유자만 읽을 수 있고, 게시글에 연결된 이미지는 공개되며
삭제 요청은 `409`입니다.

오래된 미연결 이미지 자동 정리는 이번 범위에서 제외했습니다. 안전한 draft/post
연결과 보존 기간 정책이 확정되면, DB 행을 잠근 뒤 여전히 미연결·기한 초과인지
재검사하는 dry-run 기본 관리 명령으로 추가해야 합니다.
