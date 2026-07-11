# Contributing Guide

이 문서는 `rhythm-up-server` 저장소를 GitHub 기반으로 운영하기 위한 기본 협업 규칙을 정리합니다.

현재 저장소는 GitHub Actions CI, Release Please, GHCR Docker 이미지 릴리즈를 사용합니다. 이 문서는 해당 자동화가 예측 가능하게 동작하도록 커밋과 PR의 운영 규칙을 정리합니다.

## 기본 브랜치 전략

기본 브랜치는 `main`입니다.

일반 작업은 별도 브랜치에서 진행한 뒤 Pull Request로 `main`에 병합합니다.

추천 브랜치 이름:

```text
feature/<short-description>
fix/<short-description>
docs/<short-description>
chore/<short-description>
```

예시:

```text
feature/github-actions-ci
fix/expired-token-logout
docs/release-process
chore/dependabot-config
```

## Pull Request 규칙

PR에는 다음 내용을 간단히 적습니다.

- 무엇을 변경했는지
- 왜 변경했는지
- 어떻게 확인했는지

권장 PR 설명 형식:

```markdown
## 변경 사항

- ...

## 확인 방법

- [ ] `ruff check app tests`
- [ ] `pytest`
- [ ] 필요한 경우 수동 테스트

## 참고

- 관련 이슈 또는 추가 메모
```

## Merge 방식

권장 merge 방식은 **Squash merge**입니다.

이유:

- `main` 브랜치 히스토리를 깔끔하게 유지할 수 있습니다.
- Release Please가 Conventional Commit 기반으로 릴리즈 노트를 만들 때 PR 단위 변경을 이해하기 쉽습니다.

Squash merge 제목은 이후 Conventional Commit 규칙을 따르는 것을 권장합니다.

예:

```text
feat: add github actions ci
fix: handle expired access token globally
docs: describe docker run process
chore: configure release please
```

## 커밋 메시지 방향

Release Please가 `main` 브랜치의 커밋 제목을 읽어 다음 릴리즈 버전을 결정하므로, 커밋/PR 제목은 Conventional Commit 형식을 따릅니다.

기본 형식:

```text
<type>(<scope>): <description>
```

자주 사용할 type:

```text
feat      사용자에게 보이는 기능 추가
fix       버그 수정
docs      문서 변경
test      테스트 추가/수정
refactor  동작 변경 없는 구조 개선
chore     설정, 빌드, 자동화 등 보조 작업
ci        GitHub Actions 등 CI 설정
```

예시:

```text
feat: add toss payments provider
fix: clear expired local token
docs: add contributing guide
ci: add release please workflow
```

`scope`는 선택 사항입니다. 예를 들어 Dependabot이 생성하는 `chore(deps): ...` 커밋은 의존성 관리 작업임을 뜻합니다.

### 버전 정책

Release Please는 마지막 릴리즈 이후 `main`에 병합된 커밋을 하나의 Release PR에 누적합니다. 그중 가장 큰 변경 수준을 기준으로 다음 버전을 결정합니다.

| 커밋 타입 | 버전 변화 | 예시 |
| --- | --- | --- |
| `feat` | Minor | `0.2.0` → `0.3.0` |
| `fix` | Patch | `0.2.0` → `0.2.1` |
| `feat!` 또는 본문의 `BREAKING CHANGE:` | Major | `0.2.0` → `1.0.0` |
| `docs`, `test`, `refactor`, `chore`, `ci`, `chore(deps)` | 버전 변화 없음 | 문서·테스트·운영 설정 변경 |

새 사용자 기능은 `feat`, 이미 존재하는 동작의 오류 수정은 `fix`를 사용합니다. 기능과 무관하게 Release Please 동작만 확인해야 한다면 아래처럼 빈 `feat` 커밋을 만들 수 있습니다.

```powershell
git commit --allow-empty -m "feat: prepare initial release"
git push origin main
```

## Branch protection 권장 설정

GitHub 저장소에서 `main` 브랜치에 다음 설정을 권장합니다.

- Require a pull request before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict force pushes
- Restrict deletions

초기에는 혼자 사용하는 저장소라면 리뷰 필수까지 강제하지 않아도 됩니다. 다만 CI가 생긴 뒤에는 `main` 병합 전 CI 통과는 필수로 두는 것을 권장합니다.

## CI 필수 체크

GitHub Actions는 PR마다 아래 검사를 실행합니다.

```text
ruff check app tests
pytest
docker build
```

PostgreSQL/Redis 통합 테스트는 GitHub Actions service container를 사용합니다.

현재 GitHub Actions에서 생성되는 주요 status check 이름은 다음과 같습니다.

```text
Lint and test
PostgreSQL and Redis integration test
Docker build
```

Branch protection을 설정할 때는 위 세 check를 필수 통과 대상으로 지정하는 것을 권장합니다.

## Secret 관리

다음 값들은 Git에 커밋하지 않습니다.

- `.env`
- Toss Payments secret key
- 운영 JWT secret
- 운영 DB/Redis 접속 정보

현재 CI와 GHCR 배포는 GitHub가 제공하는 `GITHUB_TOKEN`을 사용하므로 별도 secret이 필요하지 않습니다. 이후 외부 서비스 인증값이 CI에 필요해지면 GitHub Repository Settings의 `Secrets and variables`에 등록합니다.

토스페이먼츠 실제 API 호출은 기본 CI에서 수행하지 않습니다. 기본 CI는 local/mock provider 중심으로 유지하고, 토스 연동 검증은 수동 테스트 또는 별도 manual workflow로 분리합니다.

## 릴리즈 운영 흐름

실제 릴리즈 흐름은 다음과 같습니다.

```text
feat/fix PR을 main에 병합
→ CI 실행
→ Release Please가 Release PR 생성 또는 갱신
→ 이후 feat/fix 커밋은 같은 Release PR에 누적
→ Release PR 병합
→ GitHub Release와 버전 tag 생성
→ Docker Release가 GHCR 이미지 build/push
```

`docs`, `chore`, Dependabot 등의 버전 변화 없는 커밋도 CI와 Release Please는 실행하지만 Release PR을 새로 만들지 않습니다.

현재 버전은 `pyproject.toml`의 `version` 값을 기준으로 관리하며, Release Please가 Release PR에서 이를 갱신합니다.
