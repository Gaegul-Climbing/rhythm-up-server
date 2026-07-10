# Practice Server

프랜차이즈 공유 연습실 예약 서비스인 **리듬업 연습실**의 FastAPI 기반 연습 프로젝트입니다.

서비스는 회원가입/로그인, 지점과 연습실 조회, 예약 가능 시간 조회, Redis 기반 임시 선점, 예약 확정, 로컬 목 결제, 토스페이먼츠 테스트 결제 흐름을 제공합니다.

## 기술 스택

- FastAPI
- SQLAlchemy Async ORM
- Alembic
- PostgreSQL
- Redis
- Jinja2 + Vanilla JavaScript
- Pytest
- Docker Compose

## 로컬 실행

Python 3.12 이상이 필요합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

PostgreSQL과 Redis를 실행합니다.

```powershell
docker compose up -d postgres redis
```

Docker Compose 플러그인이 없는 환경에서는 아래처럼 `docker-compose`를 사용해도 됩니다.

```powershell
docker-compose up -d postgres redis
```

DB 마이그레이션을 적용합니다.

```powershell
python -m alembic upgrade head
```

서버를 실행합니다.

```powershell
fastapi dev app/main.py
```

접속 주소:

- 웹 화면: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## 결제 provider 전환

`.env`의 `PAYMENT_PROVIDER` 값으로 결제 방식을 전환합니다.

```env
PAYMENT_PROVIDER=local
```

또는:

```env
PAYMENT_PROVIDER=toss
TOSS_PAYMENTS_CLIENT_KEY=test_ck_...
TOSS_PAYMENTS_SECRET_KEY=test_sk_...
```

토스페이먼츠 테스트 결제는 브라우저에서 결제창을 띄운 뒤, 성공 URL로 돌아오면 서버가 `paymentKey`, `orderId`, `amount`를 검증하고 토스 승인 API를 호출합니다.

주의:

- `TOSS_PAYMENTS_SECRET_KEY`는 절대 프론트 코드나 Git에 올리지 않습니다.
- 로컬 테스트 중에는 `localhost`와 `127.0.0.1`을 섞지 않는 것이 좋습니다.
- 만료되었거나 DB와 맞지 않는 로그인 토큰을 받으면 프론트는 자동 로그아웃 후 로그인 화면으로 이동합니다.

## Docker 이미지 실행 준비

앱 컨테이너는 `app` profile로 분리되어 있습니다. 기본 DB/Redis만 실행하려면 기존처럼 실행합니다.

```powershell
docker compose up -d postgres redis
```

앱 이미지까지 함께 빌드/실행하려면 다음 명령을 사용합니다.

```powershell
docker compose --profile app up --build
```

또는:

```powershell
docker-compose --profile app up --build
```

컨테이너 환경에서는 DB 주소가 Compose 서비스 이름을 사용합니다.

```env
DATABASE_URL=postgresql+asyncpg://practice:practice@postgres:5432/practice
REDIS_URL=redis://redis:6379/0
```

최초 실행 전에는 마이그레이션을 적용해야 합니다.

```powershell
docker compose --profile app run --rm app alembic upgrade head
```

`docker compose config` 또는 `docker-compose config` 명령은 `.env` 값을 펼쳐서 보여줄 수 있습니다. 토스 시크릿 키가 포함된 출력은 외부에 공유하지 마세요.

## 주요 API 흐름

예약과 결제는 다음 순서로 진행됩니다.

```text
회원가입/로그인
→ 지점 조회
→ 연습실 조회
→ 예약 가능 시간 조회
→ Redis 임시 선점
→ 결제 주문 생성
→ 결제 요청
→ 결제 승인
→ 예약 확정
```

대표 API:

- `POST /auth/signup`
- `POST /auth/login`
- `GET /users/me`
- `GET /branches`
- `GET /branches/{branch_id}/rooms`
- `GET /branches/{branch_id}/rooms/{room_id}/availability`
- `POST /reservation-holds`
- `POST /payment-orders`
- `POST /payments`
- `POST /payments/toss/confirm`
- `GET /reservations`
- `DELETE /reservations/{reservation_id}`

## 프로젝트 구조

```text
app/
├─ api/                 # API router 조립
├─ cache/               # Redis client
├─ core/                # 설정, 예외 처리, 공통 기반
├─ database/            # SQLAlchemy Base와 DB session
├─ domains/
│  ├─ accounts/         # 회원과 인증
│  ├─ branches/         # 지점과 연습실
│  ├─ reservations/     # 임시 선점과 예약
│  └─ payments/         # 결제 주문, provider, 승인 이벤트
├─ web/                 # Jinja2 + 정적 프론트
└─ main.py              # FastAPI 앱 진입점

alembic/                # DB 마이그레이션
tests/                  # 자동 테스트
```

각 도메인은 보통 다음 구조를 따릅니다.

```text
router.py      # HTTP endpoint
schemas.py     # 요청/응답 모델
service.py     # 비즈니스 로직
repository.py  # DB 조회/저장
models.py      # ORM 모델
```

## 테스트

일반 단위/서비스 테스트:

```powershell
pytest
```

린트:

```powershell
ruff check app tests
```

통합 테스트용 PostgreSQL/Redis:

```powershell
Copy-Item .env.test.example .env.test
docker compose --profile test up -d postgres-test redis-test
pytest -m integration
docker compose --profile test down
```

## 운영 전 주의사항

이 프로젝트는 연습용 서비스입니다. 실제 운영 전에 최소한 다음 항목은 다시 검토해야 합니다.

- JWT를 localStorage가 아닌 HttpOnly Cookie로 전환할지 여부
- CSRF 정책
- Toss Payments webhook 검증
- 운영용 secret 관리
- DB 마이그레이션 실행 전략
- 컨테이너 이미지 태깅과 배포 파이프라인
- 로그 수집과 모니터링
