# Claude Code CJK IME Fix

Claude Code에서 한국어/중국어/일본어 입력 시 **IME 조합 창이 터미널 좌하단 (0,0)에 표시**되는 문제를 자동으로 해결합니다.

> 기존에 설치된 Claude Code를 수정하지 않고, **독립된 공간에 설치 + 패치**합니다.

## 문제

Claude Code는 [React Ink](https://github.com/vadimdemedes/ink)로 터미널 UI를 렌더링합니다. Ink은 실제 터미널 커서를 숨기고 `chalk.inverse()`로 가짜 커서를 그리는데, IME는 실제 커서 위치에 의존하므로 조합 창이 (0,0)에 표시됩니다.

- 관련 이슈: [anthropics/claude-code#25186](https://github.com/anthropics/claude-code/issues/25186)
- 영향: 모든 CJK (한국어/중국어/일본어) 사용자

## 설치

```bash
git clone https://github.com/astron8t-voyagerx/claude-code-korean-fix.git
cd claude-code-korean-fix
./setup.sh
```

설치가 완료되면 새 터미널을 열고 `kclaude` 명령으로 패치된 Claude Code를 사용할 수 있습니다.

### 환경 요구사항

- **OS**: macOS 또는 Linux
- **Node.js**: 18 이상 (NVM, fnm, volta 등 모두 지원)
- **npm**: Node.js와 함께 설치됨
- **Python**: 3.x

### 설치 구조

`setup.sh`는 기존 Claude Code를 수정하지 않고, `~/.claude-ime-fix/`에 **독립된 복사본**을 설치합니다:

```
~/.claude-ime-fix/
├── bin/kclaude             # 래퍼 스크립트 (PATH에 추가됨)
├── node_modules/           # 격리된 Claude Code 설치
├── patch-claude-ime.py     # 패치 스크립트
└── .metadata               # 설치 정보
```

기존 글로벌 설치 (`npm -g`, `~/.local/bin/claude`)와 **완전히 독립**됩니다.

## 관리

```bash
cd claude-code-korean-fix

# 상태 확인
./setup.sh status

# 업데이트 (새 버전 패치 지원 시)
git pull
./setup.sh update

# 완전 제거
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

<details>
<summary><strong>동작 원리 (기술 상세)</strong></summary>

### 핵심 전략

Ink의 내부 커서 `{x:0, y:T.height}`는 **원본을 100% 유지**하고, 별도의 `__imeX`/`__imeY`/`__imeCursorVisible` 필드로 IME 커서 위치와 가시성을 추적합니다. Ink의 스크롤/클리어/diff 렌더링 로직에 영향을 주지 않으면서 실제 터미널 커서를 올바른 위치로 이동시키고, TextInput이 활성일 때만 커서를 표시합니다.

### 데이터 흐름

```
┌─ React 렌더 단계 ──────────────────────────────────────┐
│                                                         │
│  SK.render(cursorChar)                                  │
│    └→ getPosition() → {line, column}                    │
│    └→ __ic.cursorRequested = !!cursorChar                │
│       __ic.line = line  (cursorChar truthy일 때만)       │
│       __ic.col  = column                                │
│                                                         │
├─ Ink 레이아웃 단계 ────────────────────────────────────┤
│                                                         │
│  yoga 엔진이 각 노드의 절대 좌표 계산                    │
│                                                         │
├─ 스크린 버퍼 쓰기 단계 ───────────────────────────────┤
│                                                         │
│  lw1() → ink-text 노드를 스크린 버퍼에 write            │
│    └→ ESC[7m (inverse) 감지 = 가짜 커서가 있는 TextInput│
│    └→ __ic.yogaX = 노드 절대 X                          │
│       __ic.yogaY = 노드 절대 Y                          │
│       __ic.nodeCol = M8(ESC[7m 앞 텍스트)               │
│         (노드 내 커서의 정확한 display width 오프셋)      │
│                                                         │
├─ 프레임 반환 단계 ─────────────────────────────────────┤
│                                                         │
│  YH8() 렌더러                                           │
│    └→ lastX = yogaX + nodeCol (IME 커서 절대 X)         │
│       lastY = yogaY + line    (IME 커서 절대 Y)         │
│    └→ cursor: {x:0, y:T.height}  ← 원본 유지!          │
│       __imeX: lastX                                     │
│       __imeY: lastY                                     │
│       __imeCursorVisible: cursorRequested                │
│                                                         │
├─ Ops 배열 조작 (onRender) ─────────────────────────────┤
│                                                         │
│  $.unshift(undo)     ← IME 위치 → Ink 위치 복귀         │
│  _H8.render()        ← Ink 위치 기준 정상 실행           │
│  $.push(apply)       ← Ink 위치 → 새 IME 위치           │
│  $.push(cursorShow)  ← 전환: hidden→visible 시          │
│  $.push(cursorHide)  ← 전환: visible→hidden 시          │
│                                                         │
├─ ANSI 출력 (u$8) ─────────────────────────────────────┤
│                                                         │
│  vv7 (sync begin)                                       │
│  undo: cursorMove(-imeX, +dy)  ← Ink 위치로 복귀        │
│  [_H8.render의 모든 ops]       ← 정상 렌더링             │
│  apply: cursorMove(+imeX, -dy) ← IME 위치로 이동        │
│  cursorShow/cursorHide         ← 가시성 전환             │
│  Nv7 (sync end)                                         │
│  stdout.write(전체 ANSI 문자열)                          │
│                                                         │
└─ 결과: TextInput 활성 시에만 커서가 올바른 위치에 표시 ──┘
```

### 5개 패치 상세

| # | 위치 | 변경 | 목적 |
|---|------|------|------|
| 1 | 파일 시작 | `globalThis.__ic` 전역 변수 선언 | 모든 함수 스코프에서 접근 가능한 상태 저장소 |
| 2 | `SK.render()` | `cursorRequested` 설정 + line/col 저장 | TextInput 커서 가시성 의도 + 줄/열 추적 |
| 3 | `lw1()` ink-text | `ESC[7m` 감지 시 yogaX/Y + nodeCol 저장 | 가짜 커서가 있는 노드의 절대 좌표 + 노드 내 오프셋 추적 |
| 4 | `YH8()` 렌더러 | hasInverse 리셋 + lastX/Y 갱신 + `__imeX`/`__imeY`/`__imeCursorVisible` 추가 | 프레임에 IME 위치 + 가시성 정보 포함 (cursor 원본 유지) |
| 5 | `onRender()` | ops 배열에 undo/apply + cursorShow/cursorHide 삽입 | 렌더 전후로 커서 이동 + 가시성 전환 |

### 해결한 기술적 난제들

**1. Ink 렌더링 로직 보존**: cursor.y를 변경하면 스크롤/클리어 로직이 깨지므로 cursor는 원본 유지, `__imeX`/`__imeY`를 별도 필드로 추가.

**2. blit 캐시 대응**: Ink은 변경 없는 노드를 캐시 복사하여 `write`를 호출하지 않음. `lastX`/`lastY`에 마지막 유효 위치를 영구 저장하여 해결.

**3. 전역 스코프 접근**: minified 번들의 함수 스코프 문제를 `globalThis.__ic`로 해결.

**4. ops 배열 조작**: 렌더링 코드를 직접 수정하지 않고 ops 배열에 undo/apply만 추가. Synchronized Update Mode 안에서 실행되어 중간 상태 미표시.

**5. 하이라이트 노드 분할**: 하이라이트 컴포넌트가 텍스트를 분할할 때 `M8(ESC[7m 앞 텍스트)`로 노드 내 정확한 오프셋 계산.

**6. 동적 커서 가시성**: `SK.render`의 `cursorChar` 인자로 TextInput 커서 의도를 추적, ops의 `cursorShow`/`cursorHide`로 동기화.

</details>

<details>
<summary><strong>새 버전 대응 가이드</strong></summary>

### 변수명 찾기

cli.js는 minified이므로 변수명이 버전마다 다릅니다. 각 패치의 고정 앵커를 grep으로 찾아 새 변수명을 확인하세요:

```bash
CLI="<cli.js 경로>"

# 패치 2: SK.render (getPosition 찾기)
grep -oE 'render\([A-Za-z],[A-Za-z],[A-Za-z],[A-Za-z]\)\{let\{line:[A-Za-z],column:[A-Za-z]\}=this\.getPosition\(\)' "$CLI"

# 패치 3: ink-text write
grep -oE '[A-Za-z0-9]+=[A-Za-z0-9]+\([A-Za-z],[A-Za-z0-9]+\),[A-Za-z]\.write\([A-Za-z],[A-Za-z$],[A-Za-z0-9]+\)' "$CLI"

# 패치 4a: 렌더러 초기화
grep -oE '[A-Za-z0-9]+\(\),[A-Za-z0-9]+\(\),[A-Za-z0-9]+\(\);let [A-Za-z]=[A-Za-z0-9]+\(\);[A-Za-z0-9]+\(' "$CLI"

# 패치 5: onRender
grep -oE 'let [A-Za-z0-9]+=performance\.now\(\),[A-Za-z0-9]+=[A-Za-z0-9]+\(\$\)' "$CLI"
```

### 분석 도구

```bash
# 특정 패턴 주변 컨텍스트 추출 (macOS 호환)
python3 -c "
import re
with open('$CLI') as f: c = f.read()
for m in re.finditer(r'.{0,80}PATTERN.{0,80}', c):
    print(m.group()); print()
"

# 구문 오류 검증 (패치 후 반드시 실행)
node --check "$CLI"
```

### 버전별 변수 매핑

| 역할 | v2.1.76 | v2.1.77 |
|------|---------|---------|
| 렌더 팩토리 | `eH8` | `YH8` |
| ops→ANSI 변환 | `SH8` | `u$8` |
| ops 최적화 | `Nj8` | `RH8` |
| 커서 모델 | `RK` | `SK` |
| 텍스트 후처리 | `vU3` | `wm3` |
| display width | `TO1` | `M8` |
| 트리 워커 | `yO1`/`rk7` | `lw1`/`cv7` |

### 포팅 팁

1. **변수명만 바뀌고 구조는 동일**: Ink 렌더링 파이프라인의 구조적 변경 없이 minifier가 생성한 변수명만 바뀜
2. **패치 2의 old 문자열은 안정적**: `render(A,q,K,Y){let{line:z,column:_}=this.getPosition();`은 v2.1.76~v2.1.77에서 동일
3. **Python f-string `}}` 주의**: `}}`는 리터럴 `}` 하나. 복잡한 조합은 `python3 -c "print(repr(f'...'))"` 로 확인
4. **`RH8` optimizer가 cursorShow/cursorHide 자동 상쇄**: 연속된 show+hide 쌍이 상쇄되어 불필요한 ANSI 시퀀스 미출력

</details>

---

## English

**Claude Code CJK IME Fix** — Fixes the issue where the IME composition window appears at terminal position (0,0) instead of the actual cursor location when using Korean, Chinese, or Japanese input methods in Claude Code.

### Quick Install

```bash
git clone https://github.com/astron8t-voyagerx/claude-code-korean-fix.git
cd claude-code-korean-fix
./setup.sh
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
- 공식 수정이 이루어질 때까지의 임시 해결책입니다
