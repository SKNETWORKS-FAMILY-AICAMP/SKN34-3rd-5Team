# 팀 GitHub 규칙 정리

확인일: 2026-09-13 (한국 시간). 사용자의 요청으로 실제 Notion 본문, 코드 블록, 하위 링크, Workflow의 브랜치 구조 그림을 확인했습니다. 이 파일은 확인 당시 규칙의 작업용 요약이며, 팀 규칙이 바뀌면 원문을 다시 확인해 갱신합니다.

## 확인한 원문과 범위

1. [GitHub 협업 규칙 — Fork & Pull Request Workflow](https://app.notion.com/p/GitHub-Fork-Pull-Request-Workflow-3d3fd55884fd801b90c5f746984c4141): Fork, remote, Push, PR, 팀장 리뷰, 금지사항과 체크리스트
2. [Git 브랜치 이름 규칙](https://app.notion.com/p/Git-3d3fd55884fd81a2b547f2b00ccba17f): 접두어, 작업명, Issue 번호, 브랜치 생성 기준과 정리
3. [Git 커밋 메시지 규칙](https://app.notion.com/p/Git-3d3fd55884fd81d0bf1dda9546e3efa9): 유형, 한글 메시지, 커밋 단위, 민감정보 제외와 리뷰 수정
4. [Git Workflow 규칙 — main / develop / feat](https://app.notion.com/p/Git-Workflow-main-develop-feat-3d3fd55884fd8182964ed5ccba8c7b6d): 개발 시작부터 통합·배포·동기화까지의 실제 순서

상위 본문의 하위 문서는 2~4번입니다. 각 하위 문서의 본문 링크까지 확인했으며, 추가 링크는 이 네 문서 사이의 상호 참조였습니다. 상위 페이지는 9월 7일, 하위 세 페이지는 9월 6일 편집으로 화면에 표시되었습니다. 편집일만으로 충돌하는 내용의 우선순위를 결정하지 않았습니다.

## 저장소와 브랜치

| 항목 | 역할 |
| --- | --- |
| `upstream` | 팀 공용 원본 저장소 |
| `origin` | 개인 계정으로 Fork한 저장소 |
| `main` | 배포·최종 제출 가능한 안정 버전 |
| `develop` | 팀의 개발 결과를 통합하는 기준 브랜치 |
| `feat/...` | 모든 실제 작업을 수행하는 브랜치 |

- 새 작업은 최신 `develop`에서 시작합니다. `main`에서 기능 브랜치를 만들지 않습니다.
- 기능 개발, 버그 수정, 리팩터링, 문서, 테스트, 설정 변경 모두 `feat/` 접두어를 사용합니다.
- `fix/`, `hotfix/`, `release/`, `refactor/`, `docs/`, `test/`, `chore/` 브랜치를 만들지 않습니다.
- 형식은 `feat/<work-name>`, Issue를 사용하는 작업은 `feat/<issue-number>-<work-name>`입니다.
- 작업명은 영어 소문자와 하이픈으로 구체적이고 간결하게 작성합니다. 한 브랜치에 하나의 작업 목적을 담습니다.
- 예: `feat/course-save`, `feat/27-route-overlap` (설명용 예시이며 실제 브랜치를 만든 것은 아닙니다.)

## 실제 개발 순서

최초 설정에서는 팀 저장소를 Fork하고 개인 Fork를 Clone한 다음, 팀 저장소를 `upstream`으로 등록합니다. 실제 remote URL은 작업 전에 확인하며 문서의 placeholder를 그대로 실행하지 않습니다.

새 작업 전 동기화:

```bash
git switch develop
git fetch upstream
git merge --ff-only upstream/develop
git push origin develop
git switch -c feat/<work-name>
```

개발 후에는 status/diff와 로컬 실행·테스트 결과를 확인하고, 해당 작업의 파일만 커밋한 뒤 `git push -u origin feat/<work-name>`으로 개인 Fork에 Push합니다.

작업 도중 다른 PR이 Merge되면 필요한 최신 내용을 현재 작업 브랜치에 반영합니다:

```bash
git fetch upstream
git switch feat/<work-name>
git merge upstream/develop
```

충돌을 해결한 경우 다시 검증하고 커밋/Push합니다. 문서의 예시 커밋은 `chore: develop 변경사항 반영`입니다.

PR이 `develop`에 Merge되면 다음 작업 전에 `upstream/develop → local develop → origin/develop`을 동기화합니다. Merge된 개인 작업 브랜치는 로컬과 개인 Fork에서 정리합니다. 원문 로컬 삭제 명령은 `git branch -d feat/<work-name>`입니다.

배포·최종 제출 상태가 되면 팀 저장소의 `develop → main` PR을 만들고 팀장이 확인해 Merge합니다. 그때 다음 절차로 `main`도 동기화합니다:

```bash
git switch main
git fetch upstream
git merge --ff-only upstream/main
git push origin main
```

이 절의 명령은 절차 설명입니다. 진행 중인 변경을 보존하고 실제 요청 범위와 Git 상태를 확인한 뒤 실행합니다. fast-forward가 불가능하면 상태를 확인하며 강제 reset/force-push로 덮어쓰지 않습니다.

## 커밋

형식: `type: 구체적인 한글 작업 내용`

| 유형 | 용도 |
| --- | --- |
| `feat` | 새 기능 |
| `fix` | 버그·오류 수정 |
| `refactor` | 기능 변화 없는 구조 개선 |
| `docs` | 문서 수정 |
| `test` | 테스트 추가·수정 |
| `chore` | 설정·패키지·빌드·환경 관련 변경 |

- 콜론 뒤 한 칸을 띄우고 끝에 마침표를 붙이지 않습니다.
- `수정`, `업데이트`, `fix: 수정`처럼 불명확한 메시지를 쓰지 않습니다.
- 하나의 의미 있는 목적 단위로 나눕니다. 코드·문서·설정·테스트 등 성격이 다른 변경은 가능한 한 나누되, 파일 수보다 변경 목적을 기준으로 판단합니다.
- 예: `feat: 코스 이름 입력과 저장 기능 구현`, `fix: 겹친 경로의 구간 색상 표시 오류 수정`
- Issue 번호는 메시지 끝에 `(#12)`처럼 선택적으로 표시할 수 있습니다. 실제 사용 여부는 팀의 Issue 운영 기준에 맞춥니다.
- `git add .`를 쓰기 전에도 반드시 status/diff를 확인합니다. 현재 작업과 관계없는 변경을 섞지 않습니다.

## PR과 리뷰

- Base repository: 팀 공용 저장소, base branch: `develop`
- Head repository: 개인 Fork, compare branch: `feat/<work-name>`
- 일반 기능 PR을 `main`으로 직접 보내지 않습니다.
- PR 제목은 커밋처럼 유형과 구체적인 작업 내용을 표시합니다.
- PR 하나에 하나의 목적만 담습니다.
- 기본 본문 구성은 `작업 내용`, `변경 사항`, `테스트`, `참고 사항`입니다. 테스트 체크박스에는 실제 수행한 검증 결과만 씁니다.
- 리뷰는 팀장만 담당합니다. 팀장 Approve가 있어야 Merge할 수 있으며, 작성자가 임의로 Merge하지 않습니다.
- 기본 Merge 방식은 **Squash and merge**입니다.
- 수정 요청에는 기존 `feat/...` 브랜치에서 추가 커밋/Push로 대응합니다. 기존 PR에 자동 반영되므로 새 PR을 만들지 않습니다.
- 실행 오류·테스트 실패가 있으면 Merge하지 않습니다. 최신 `develop`과의 충돌도 Merge 전에 확인합니다.

PR 본문 틀:

```markdown
## 작업 내용
- 구현한 사용자 동작

## 변경 사항
- 검토에 필요한 변경 요약

## 테스트
- [ ] 실제 수행한 검증과 결과

## 참고 사항
- 리뷰에 필요한 제한 또는 결정 사항
```

## 포함하지 않는 파일과 금지 행동

- 실제 `.env`, API 키, Access Token, 비밀번호, DB 비밀번호, 개인 인증서, Secret 파일을 커밋하지 않습니다.
- 불필요한 개인 IDE 설정, 로그, 임시 파일, 실행에 필요하지 않은 대용량 파일을 제외하고 필요한 제외 패턴을 `.gitignore`에 등록합니다.
- 팀 공용 `main` 또는 `develop`에 직접 Push하거나 그 브랜치에서 기능을 개발하지 않습니다.
- 다른 팀원의 작업 브랜치를 임의로 수정하지 않습니다.
- 팀장 Review/Approve 없이 Merge하지 않습니다.
- 실행되지 않거나 검증하지 않은 코드, 관계없는 여러 목적을 한 PR에 묶어 Merge하지 않습니다.

## 문서 간 차이와 적용 기준

확인한 차이를 숨기지 않고 다음과 같이 구분합니다.

1. 상위 협업 문서의 Repository 설명에는 `feat/...`, `fix/...`가 함께 있지만, 브랜치 이름 문서와 Workflow는 모든 작업에 **`feat/...`만 사용**한다고 명시합니다. 상위 문서도 이름 작성은 브랜치 문서에서 관리한다고 위임하므로 세부 문서를 적용합니다.
2. 상위 문서의 마지막 체크리스트에는 최신 `main`에서 다음 작업을 시작하는 항목이 남아 있습니다. 같은 본문의 여러 절에서는 개발 흐름을 Workflow 문서에서 관리한다고 명시하고, 두 하위 문서는 **최신 `develop`에서 생성**한다고 반복해 정합니다. 일상 개발은 `develop` 기준을 적용하고 `main` 동기화는 배포 PR Merge 이후에 수행합니다.
3. Workflow의 브랜치 구조 그림에는 일반 Git Flow의 `Master`, `Hotfix`, `Release`, `Develop`, `Feature`가 표시되어 있습니다. 같은 문서 본문은 `hotfix/release` 등을 사용하지 않는다고 명확히 정하므로 그림에서 해당 브랜치를 사용하라는 규칙을 추론하지 않습니다.
4. `main/develop 직접 Push 금지`라는 문구와 개인 Fork 동기화 명령 `git push origin develop/main`이 함께 있습니다. 구체적인 저장소 역할과 절차에 따라, 팀 공용 저장소 직접 Push는 금지하고 개인 Fork의 동기화는 문서가 지정한 절차로 구분합니다.

위 기준은 상위 문서가 세부 Workflow/브랜치 문서에 관리를 위임한 점과 명시적인 명령을 바탕으로 한 적용 판단입니다. 이 판단으로 Notion 원문을 수정하지 않았습니다.
