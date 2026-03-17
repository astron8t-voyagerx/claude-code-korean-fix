# Claude Code CJK IME Fix

Claude Code에서 한국어/중국어/일본어 입력 시 **IME 조합 창이 터미널 좌하단 (0,0)에 표시**되는 문제를 자동으로 해결합니다.

> **이 프로젝트는 Anthropic이 공식 수정을 제공하기 전까지의 임시 해결책입니다.**
> 공식 수정이 나오면 `./setup.sh uninstall`로 깔끔하게 제거하고 공식 버전을 사용하세요.
>
> 기존에 설치된 Claude Code를 수정하지 않고, **독립된 공간에 설치 + 패치**합니다.

## 문제

Claude Code는 [React Ink](https://github.com/vadimdemedes/ink)로 터미널 UI를 렌더링합니다. Ink은 앱 시작 시 **실제 터미널 커서를 숨기고**, 텍스트 입력 위치에 `chalk.inverse()`로 **가짜 커서를 시각적으로 그립니다**. 그러나 macOS/Windows의 IME는 **실제 터미널 커서의 물리적 위치**에 의존하여 조합 창을 배치하므로, 숨겨진 커서의 기본 위치인 (0,0)에 조합 창이 표시됩니다.

- 관련 이슈: [anthropics/claude-code#25186](https://github.com/anthropics/claude-code/issues/25186)
- 영향: 모든 CJK (한국어/중국어/일본어) 사용자

### 왜 이렇게 복잡한 패치가 필요한가?

Claude Code는 오픈소스가 아니며, 배포되는 `cli.js`는 **minified된 단일 번들 파일** (15,000줄 이상)입니다. 소스 코드에 접근할 수 없으므로, minified 코드의 특정 지점을 문자열 매칭으로 찾아 패치하는 방식을 사용합니다.

또한 Ink의 렌더링 파이프라인은 여러 단계 (React 렌더 → yoga 레이아웃 → 스크린 버퍼 → ops 배열 → ANSI 출력)로 구성되어 있어, 커서 위치를 올바르게 추적하려면 **5개 지점**을 정밀하게 수정해야 합니다. 단순히 커서 위치를 바꾸면 Ink의 스크롤/클리어 로직이 깨지기 때문에, Ink의 내부 커서는 원본을 유지하면서 별도의 IME 전용 좌표를 추가하는 방식으로 구현합니다.

## 설치

### 방법 1: 한 줄 설치

```bash
curl -fsSL https://raw.githubusercontent.com/astron8t-voyagerx/claude-code-korean-fix/main/setup.sh | bash
```

### 방법 2: clone

```bash
git clone https://github.com/astron8t-voyagerx/claude-code-korean-fix.git
cd claude-code-korean-fix
./setup.sh
```

설치가 완료되면 새 터미널을 열고 `kclaude` 명령으로 패치된 Claude Code를 사용할 수 있습니다.

### 환경 요구사항

- **OS**: macOS 또는 Linux
- **Node.js**: 18 이상 (NVM, fnm, volta 등 모두 지원)
- **Python**: 3.x

### 설치 구조

`setup.sh`는 기존 Claude Code를 수정하지 않고, `~/.claude-ime-fix/`에 **독립된 복사본**을 설치합니다:

```
~/.claude-ime-fix/
├── bin/kclaude             # 래퍼 스크립트
├── node_modules/           # 격리된 Claude Code 설치
├── patch-claude-ime.py     # 패치 스크립트
└── .metadata               # 설치 정보
```

기존 글로벌 설치 (`npm -g`, `~/.local/bin/claude`)와 **완전히 독립**됩니다.

## 관리

### curl로 설치한 경우

```bash
# 업데이트 (재설치)
curl -fsSL https://raw.githubusercontent.com/astron8t-voyagerx/claude-code-korean-fix/main/setup.sh | bash
```

```bash
# 제거
rm -rf ~/.claude-ime-fix
# 그리고 ~/.zshrc (또는 ~/.bashrc)에서 아래 블록 삭제:
#   # >>> claude-ime-fix >>>
#   export PATH="$HOME/.claude-ime-fix/bin:$PATH"
#   # <<< claude-ime-fix <<<
```

### 클론 설치한 경우

```bash
# 업데이트
git pull && ./setup.sh update
```

```bash
# 제거
./setup.sh uninstall
```

## 지원 버전

| Claude Code 버전 | 상태 |
|---|---|
| v2.1.77 | ✅ 지원 |

> cli.js는 minified 번들이므로 변수명이 버전마다 달라집니다.
> 새 버전이 나오면 패치 스크립트를 업데이트해야 합니다.

## FAQ

**Q: 기존에 설치된 Claude Code와 충돌하나요?**

A: 아닙니다. `~/.claude-ime-fix/` 에 독립적으로 설치되며, 기존 설치를 수정하지 않습니다. PATH 우선순위로 패치 버전이 먼저 실행됩니다. 제거하면 기존 설치가 그대로 사용됩니다.

**Q: Bun 바이너리 (`~/.local/bin/claude`)에도 적용되나요?**

A: 아닙니다. Bun 바이너리는 JS가 내부에 임베딩된 단일 실행 파일이라 패치가 불가능합니다. 이 도구는 npm 패키지의 `cli.js`를 패치합니다.

**Q: Claude Code가 업데이트되면 패치가 사라지나요?**

A: 이 도구는 격리된 공간에 **버전을 고정**하여 설치하므로 자동 업데이트되지 않습니다. 새 버전을 사용하려면 `git pull && ./setup.sh update`를 실행하세요.

**Q: 공식 수정이 나오면?**

A: `./setup.sh uninstall`로 깔끔하게 제거하고 공식 버전을 사용하세요.

---

## English

**Claude Code CJK IME Fix** — Fixes the issue where the IME composition window appears at terminal position (0,0) instead of the actual cursor location when using Korean, Chinese, or Japanese input methods in Claude Code.

### Quick Install

```bash
# One-liner
curl -fsSL https://raw.githubusercontent.com/astron8t-voyagerx/claude-code-korean-fix/main/setup.sh | bash

# Or clone for easier updates
git clone https://github.com/astron8t-voyagerx/claude-code-korean-fix.git
cd claude-code-korean-fix && ./setup.sh
```

This installs Claude Code in an **isolated directory** (`~/.claude-ime-fix/`) separate from your existing installation, applies the IME cursor position patch, and sets up your PATH. Run `kclaude` to use the patched version.

**Requirements**: macOS/Linux, Node.js 18+, Python 3

**Update**: `git pull && ./setup.sh update`
**Uninstall**: `./setup.sh uninstall`

---

## License

MIT — See [LICENSE](LICENSE)

## 관련 정보

- Ink 6.7.0에서 [`useCursor`](https://github.com/vadimdemedes/ink/pull/866) 훅이 추가되었으나, Claude Code는 아직 이를 사용하지 않습니다
