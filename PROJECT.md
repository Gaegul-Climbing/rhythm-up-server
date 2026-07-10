# 인프라 연습 프로젝트

## 프로젝트 목적

이 프로젝트의 목적은 복잡한 비즈니스 서비스를 만드는 것이 아니라, 작은 API 서비스를 재료로 삼아 개발부터 배포, 운영, 관측, 클라우드 확장까지의 전체 흐름을 처음부터 직접 설계하고 경험하는 것이다.

현재 업무에서는 이미 구축된 운영 환경에 기능을 추가하는 경우가 많으므로, 평소 경험하기 어려운 초기 설계와 인프라 구축 과정을 학습 대상으로 삼는다.

## 목표

> 최소한의 API 서비스를 만들고, 로컬 환경에서 배포·운영 자동화와 관측 체계를 완성한 뒤, 이를 클라우드 인프라로 확장한다.

최종적으로 코드 변경, 테스트, 릴리스, 이미지 생성, 배포, 장애 발견, 원인 분석 및 복구까지의 흐름을 스스로 재현하고 설명할 수 있는 상태를 목표로 한다.

## 핵심 원칙

- 애플리케이션 기능보다 인프라와 운영 경험을 우선한다.
- 서비스를 지나치게 복잡하게 만들지 않는다.
- 각 기술은 단순 설치가 아니라 실제 사용과 장애 시나리오를 통해 학습한다.
- 로컬에서 검증한 구조를 클라우드로 확장할 수 있도록 구성한다.
- 자동화할 수 있는 작업은 가급적 수동 절차로 남기지 않는다.
- 회사의 기술 스택을 참고하되 동일하게 복제하는 것에 얽매이지 않는다.
- 개인 학습 환경의 자원과 향후 클라우드 비용을 고려해 가볍게 시작한다.

## 전체 진행 단계

1. 간단한 API 서비스 구축
2. 로컬 Kubernetes 배포 환경 구축
3. CI/CD 및 GitOps 자동화 구축
4. 로컬 로깅·관측 시스템 구축
5. Terraform을 활용한 클라우드 인프라 구축 및 실제 배포
6. 여유가 있을 경우 Elasticsearch MCP와 AI 모델을 연동한 로그 분석 환경 실험

각 단계에서는 가능하면 다음 학습 사이클을 완결한다.

> 구축 → 요청 발생 → 실패 유도 → 관측 → 수정 → 자동 재배포

## 기술 스택 초안

### 애플리케이션

- Python
- FastAPI
- PostgreSQL
- Redis

Python과 FastAPI는 인프라 학습을 방해하지 않을 정도로 가볍고, Python 자체를 함께 학습할 수 있으며, 향후 클라우드 비용도 고려한 선택이다.

### CI/CD 및 배포

- GitHub Actions
- release-please
- pre-commit 또는 Husky
- Argo CD
- Docker Desktop 또는 Podman
- Kubernetes
- Helm

Python 프로젝트의 로컬 품질 검사 도구는 Husky보다 `pre-commit`을 우선 검토하되, 최종 선택은 `practice-server` 설계 과정에서 결정한다.

### 로깅 및 관측

- Elasticsearch
- Filebeat
- Kibana
- 필요할 경우 Prometheus 및 Grafana 추가

애플리케이션은 구조화된 로그와 요청 ID를 제공해야 하며, 오류율·처리 시간·실패 패턴을 실제로 분석할 수 있는 시나리오를 마련한다.

### 클라우드

- AWS 우선 검토
- Terraform

클라우드 단계에서는 로컬 구성을 단순 복제하는 데 그치지 않고, Kubernetes 및 PostgreSQL·Redis·로깅 구성 요소를 직접 운영할지 관리형 서비스로 전환할지도 비교한다.

## 저장소 구성

### `practice-server`

무엇을 실행할 것인지를 담당한다.

- FastAPI 애플리케이션
- PostgreSQL 마이그레이션
- Redis 연동
- 테스트 및 코드 품질 검사
- 환경변수 기반 설정
- 구조화된 로그
- Dockerfile
- 로컬 개발용 Compose
- GitHub Actions
- release-please
- 버전이 지정된 컨테이너 이미지 생성

### `practice-deploy`

애플리케이션을 어떻게 실행할 것인지를 담당한다.

- Kubernetes manifest
- Helm chart
- Argo CD Application
- 환경별 배포 설정
- 로컬 Kubernetes 구성
- ELK 및 Filebeat 구성
- Kibana 대시보드와 Transform

### `practice-terraform` (향후 생성)

애플리케이션을 어디에서 실행할 것인지를 담당한다.

- 네트워크와 보안 구성
- Kubernetes 또는 컴퓨팅 기반
- 컨테이너 레지스트리
- IAM
- 데이터베이스와 캐시
- 스토리지, DNS 및 기타 AWS 리소스

클라우드 학습을 시작하기 전까지는 저장소를 만들지 않고, 실제로 필요해지는 시점에 별도 생성한다.

## 현재 범위

첫 단계에서는 다음 두 작업 영역만 준비한다.

- `practice-server`
- `practice-deploy`

먼저 `practice-server`에서 배포 실습에 필요한 최소 서비스를 만든다. 서비스가 완성될 때까지 기다리는 것이 아니라, 상태 확인 API, PostgreSQL·Redis 연동, 테스트, 컨테이너 이미지, 구조화된 로그가 준비되면 `practice-deploy` 단계로 이동한다.

## 첫 번째 이정표

> `practice-server`를 내려받은 사람이 간단한 절차로 실행하고, PostgreSQL과 Redis를 사용하는 API를 호출하며, 구조화된 로그까지 확인할 수 있다.

이 이정표를 달성한 후 로컬 Kubernetes와 배포 자동화 작업을 시작한다.
