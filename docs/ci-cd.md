# CI/CD 자동화 가이드

이 문서는 `rhythm-up-server`의 GitHub Actions 기반 검증, 릴리즈, 컨테이너 이미지 배포 흐름을 설명합니다.

## 전체 흐름

```text
일반 PR 생성·갱신
→ CI: 린트, 테스트, 통합 테스트, Docker 빌드 검증

main 브랜치에 push
├→ CI: 린트, 테스트, 통합 테스트, Docker 빌드 검증
└→ Release Please: Conventional Commit 분석, Release PR 생성·갱신

Release PR 병합
→ GitHub Release와 버전 tag 발행
→ Docker Release: GHCR에 컨테이너 이미지 push

Dependabot 정기 실행
→ 의존성 업데이트 PR 생성
→ PR CI 실행
```

`feat`은 Minor, `fix`는 Patch 버전을 올립니다. `docs`, `test`, `refactor`, `chore`, `ci`, `chore(deps)`는 릴리즈 버전을 올리지 않습니다. 상세 커밋 규칙은 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고합니다.

## 자동화 파일

| 파일 | 실행 조건 | 하는 일 |
| --- | --- | --- |
| [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | PR 생성·갱신, `main` push | 코드와 컨테이너 이미지가 정상적으로 만들어지는지 검증합니다. |
| [`.github/workflows/release-please.yml`](../.github/workflows/release-please.yml) | `main` push | 커밋 타입을 읽어 Release PR을 생성하거나 갱신합니다. Release PR 병합 시 GitHub Release를 발행합니다. |
| [`.github/workflows/docker-release.yml`](../.github/workflows/docker-release.yml) | GitHub Release `published` | 애플리케이션 이미지를 빌드하고 GHCR에 배포합니다. |
| [`.github/dependabot.yml`](../.github/dependabot.yml) | 매주 월요일 지정 시각 | GitHub Actions, Python, Docker 의존성의 업데이트 PR을 생성합니다. |
| [`release-please-config.json`](../release-please-config.json) | Release Please 실행 시 | Python 릴리즈 방식, 패키지 표시 이름, CHANGELOG 경로를 정의합니다. |
| [`.release-please-manifest.json`](../.release-please-manifest.json) | Release Please 실행 시 | 마지막 릴리즈 버전을 기록해 다음 버전 계산의 기준으로 사용합니다. |

## CI 검증 항목

`ci.yml`은 서로 독립적인 세 job을 실행합니다.

| Job | 환경 | 검증 내용 |
| --- | --- | --- |
| `Lint and test` | Python 3.12, local 결제 provider | 개발 의존성을 설치하고 `ruff check app tests`, `pytest`를 실행합니다. 기본 테스트는 SQLite와 메모리 구현을 사용합니다. |
| `PostgreSQL and Redis integration test` | PostgreSQL 17, Redis 7, Python 3.12 | GitHub Actions service container로 실제 PostgreSQL·Redis를 띄우고, Alembic 마이그레이션 후 `pytest -m integration`을 실행합니다. |
| `Docker build` | Docker | [Dockerfile](../Dockerfile)로 애플리케이션 이미지를 만들 수 있는지 검증합니다. 이미지는 이 단계에서 외부 Registry에 올리지 않습니다. |

통합 테스트의 DB 주소, Redis 주소, JWT 테스트 값은 workflow의 환경 변수로만 주입합니다. 실제 `.env`나 Toss Payments 키는 CI에서 사용하지 않습니다.

## 컨테이너 이미지 배포

GitHub Release가 발행되면 `docker-release.yml`은 `GITHUB_TOKEN`으로 GitHub Container Registry(`ghcr.io`)에 로그인합니다. 별도 PAT이나 Docker Hub 계정은 필요하지 않습니다.

현재 이미지 이름은 다음과 같습니다.

```text
ghcr.io/gaegul-climbing/rhythm-up-server
```

예를 들어 `v0.2.0` 릴리즈는 아래 태그를 배포합니다.

```text
0.2.0
0.2
latest
```

GHCR에서 다른 사용자나 다른 서버가 이미지를 pull해야 한다면, GitHub Packages 페이지에서 패키지를 공개로 설정하거나 `read:packages` 권한이 있는 토큰을 사용해야 할 수 있습니다.

## GitHub에서 필요한 설정

자동화 파일 외에 다음 저장소 또는 조직 설정이 필요합니다.

| 설정 | 목적 |
| --- | --- |
| Actions `GITHUB_TOKEN` 쓰기 권한 | Release Please의 Release PR·Release 생성 및 GHCR 이미지 업로드를 허용합니다. |
| GitHub Actions의 PR 생성 허용 | `GITHUB_TOKEN`이 Release Please PR을 만들 수 있게 합니다. |
| PR workflow 승인 정책 | 봇 또는 외부 기여자가 만든 PR의 CI가 `Action required` 상태가 되지 않도록 조직 정책을 조정합니다. |
| `main` 브랜치 보호 규칙 (선택) | `Lint and test`, `PostgreSQL and Redis integration test`, `Docker build` 통과 후에만 병합하게 합니다. |

조직 정책이 저장소 설정보다 우선할 수 있습니다. 저장소에서 옵션이 비활성화되어 있으면 `Gaegul-Climbing` 조직의 `Settings → Actions → General`에서 변경합니다.

## 로컬 재현

GitHub Actions를 기다리지 않고 다음 명령으로 핵심 검증을 재현할 수 있습니다.

```powershell
python -m ruff check app tests
python -m pytest
docker build --tag rhythm-up-server:local .
```

통합 테스트는 별도로 테스트용 PostgreSQL·Redis를 실행한 뒤 수행합니다.

```powershell
Copy-Item .env.test.example .env.test
docker compose --profile test up -d postgres-test redis-test
python -m alembic upgrade head
python -m pytest -m integration
docker compose --profile test down
```

## 자주 보이는 상태

| 상태 | 의미와 대응 |
| --- | --- |
| `Queued` | GitHub-hosted runner를 기다리는 상태입니다. 잠시 기다리면 실행됩니다. |
| `Action required` / `Awaiting approval` | 봇·외부 기여자 PR에 대한 보안 승인 대기입니다. 변경 내용을 확인한 뒤 `Approve and run`을 누르거나 조직의 PR workflow 승인 정책을 조정합니다. |
| Dependabot PR 여러 개 | 첫 검사나 정기 검사에서 각각의 의존성 업데이트가 PR로 생성된 상태입니다. CI 통과 여부를 확인한 뒤 하나씩 병합합니다. |
| Docker Release 실패 | GitHub Actions의 `packages: write` 권한, 조직의 `GITHUB_TOKEN` 정책, GHCR 패키지 권한을 먼저 확인합니다. |

## 운영 원칙

- 실제 Toss Payments 키, 운영 DB 비밀번호, 운영 JWT secret은 Git에 커밋하거나 CI 로그에 출력하지 않습니다.
- Dependabot과 Release Please가 만든 PR도 변경 내용과 CI 결과를 확인한 뒤 병합합니다.
- CI는 검증만, Docker Release는 GitHub Release 이후의 이미지 배포만 담당합니다. 실제 서버 배포는 아직 자동화하지 않습니다.
