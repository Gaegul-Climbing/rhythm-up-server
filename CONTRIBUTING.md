# Contributing Guide

이 문서는 `rhythm-up-server` 저장소를 GitHub 기반으로 운영하기 위한 기본 협업 규칙을 정리합니다.

현재 단계의 목표는 복잡한 자동화를 바로 강제하는 것이 아니라, 이후 CI, Release Please, Docker 이미지 릴리즈를 붙일 수 있도록 저장소 운영 흐름을 먼저 안정시키는 것입니다.

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

Release Please를 사용할 예정이므로 커밋/PR 제목은 Conventional Commit 형식을 따르는 것을 권장합니다.

기본 형식:

```text
<type>: <description>
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

Breaking change가 필요한 경우는 다음 단계에서 별도 정책을 정합니다.

## Branch protection 권장 설정

GitHub 저장소에서 `main` 브랜치에 다음 설정을 권장합니다.

- Require a pull request before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict force pushes
- Restrict deletions

초기에는 혼자 사용하는 저장소라면 리뷰 필수까지 강제하지 않아도 됩니다. 다만 CI가 생긴 뒤에는 `main` 병합 전 CI 통과는 필수로 두는 것을 권장합니다.

## CI 도입 후 필수 체크 예정

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

GitHub Actions에서 필요한 secret은 GitHub Repository Settings의 `Secrets and variables`에 등록합니다.

토스페이먼츠 실제 API 호출은 기본 CI에서 수행하지 않습니다. 기본 CI는 local/mock provider 중심으로 유지하고, 토스 연동 검증은 수동 테스트 또는 별도 manual workflow로 분리합니다.

## 릴리즈 방향

릴리즈 자동화는 다음 단계에서 Release Please로 구성할 예정입니다.

목표 흐름:

```text
PR merge to main
→ Release Please가 release PR 생성
→ release PR merge
→ GitHub Release와 tag 생성
→ Docker image build/push
```

현재 버전은 `pyproject.toml`의 `version` 값을 기준으로 관리합니다.
