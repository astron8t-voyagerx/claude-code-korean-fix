#!/usr/bin/env python3
"""
Claude Code Korean/CJK IME 커서 위치 패치

한국어/중국어/일본어 IME 사용 시 조합 창이 터미널 좌하단 (0,0)에 표시되는
문제를 해결합니다. Claude Code v2.1.77 기준.

사용법:
  # 권장: setup.sh를 통한 자동 설치
  ./setup.sh

  # 수동 패치
  python3 patch-claude-ime.py <cli.js 경로>
  python3 patch-claude-ime.py --unpatch <cli.js 경로>

  # 유틸리티
  python3 patch-claude-ime.py --version     # 지원 버전 출력
  python3 patch-claude-ime.py --check <경로>  # 패치 가능 여부만 확인

원리:
  Claude Code는 React Ink로 터미널 UI를 렌더링하며, 앱 시작 시 실제 터미널
  커서를 숨기고(ESC[?25l) chalk.inverse로 가짜 커서를 그립니다.
  IME는 실제 터미널 커서 위치에 의존하므로 조합 창이 (0,0)에 표시됩니다.

  이 패치는:
  1. TextInput의 커서 위치(yogaX+col, yogaY+line)를 추적하여
  2. 매 렌더 후 실제 커서를 해당 위치로 이동시키고
  3. TextInput 커서가 보일 때만 실제 커서를 표시합니다.

  Ink의 내부 cursor(0, v.height)는 원본을 유지하여 스크롤/클리어 등
  렌더링 로직에 영향을 주지 않습니다.

주의:
  - cli.js는 minified 번들이므로 변수명은 버전마다 다릅니다.
  - 이 패치는 v2.1.77 기준이며, 다른 버전에서는 패치 포인트가 달라질 수 있습니다.
  - Bun 바이너리 버전에는 적용 불가, npm 패키지(cli.js)에만 적용 가능합니다.
"""

import sys
import os
import shutil

SUPPORTED_VERSION = "2.1.77"

# globalThis.__ic: 모든 함수 스코프에서 접근 가능한 전역 상태
G = 'globalThis.__ic'


def patch(filepath):
    print(f"패치 대상: {filepath}")
    with open(filepath, 'r') as f:
        content = f.read()

    # 이미 패치된 파일이면 백업에서 원본 복원 후 재패치
    if G in content:
        bak = filepath + '.bak'
        if os.path.exists(bak):
            print(f"  기존 패치 감지 → 원본 복원 후 재패치")
            shutil.copy2(bak, filepath)
            with open(filepath, 'r') as f:
                content = f.read()
        else:
            print(f"  ERROR: 이미 패치된 파일이지만 백업({bak})이 없습니다.")
            print(f"  npm install로 원본 cli.js를 복원한 뒤 다시 시도하세요.")
            return False

    orig_len = len(content)
    n = 0

    # ==================================================================
    # 패치 1: 전역 변수 선언 (shebang 다음 줄)
    #
    # line/col       : TextInput 커서의 줄/열 (SK.render에서 저장)
    # yogaX/Y        : TextInput ink-text 노드의 절대 좌표 (lw1에서 저장)
    # hasInverse     : 현재 렌더에서 ESC[7m(가짜 커서) 감지 여부
    # nodeCol        : 노드 내 커서 display width 오프셋
    # lastX/Y        : 마지막으로 감지된 IME 커서 절대 좌표
    #                  (blit 캐시 시에도 유지하기 위해 별도 저장)
    # cursorRequested: SK.render에서 cursorChar가 truthy인지 여부
    #                  (TextInput이 커서를 표시하려는 상태 추적)
    # ==================================================================
    init = (
        f'{G}={{line:0,col:0,yogaX:0,yogaY:0,hasInverse:false,'
        f'nodeCol:0,lastX:void 0,lastY:void 0,cursorRequested:false}};'
    )
    if G not in content:
        nl = content.find('\n')
        content = content[:nl + 1] + init + '\n' + content[nl + 1:]
        n += 1
        print(f"  [1] 전역 변수 선언")
    else:
        print(f"  [1] 스킵 (이미 존재)")

    # ==================================================================
    # 패치 2: SK.render()에서 커서 상태 저장
    #
    # SK는 TextInput의 커서 모델 클래스.
    # render(cursorChar, mask, invert, ghostText) 호출 시
    # getPosition()이 {line, column}을 반환.
    #
    # cursorChar(A)가 truthy → 커서가 보이는 상태
    #   → line/col 저장 + cursorRequested=true
    # cursorChar(A)가 falsy → 커서 안 보임
    #   → cursorRequested=false
    #
    # cursorRequested는 렌더 사이클마다 리셋하지 않음.
    # SK.render가 호출되지 않는 blit 캐시 시에도 이전 값 유지.
    # ==================================================================
    old = 'render(A,q,K,Y){let{line:z,column:_}=this.getPosition();'
    new = (
        f'render(A,q,K,Y){{let{{line:z,column:_}}=this.getPosition();'
        f'{G}.cursorRequested=!!A;'
        f'if(A){{{G}.line=z;{G}.col=_}}'
    )
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        n += 1
        print(f"  [2] SK.render() → cursorRequested + line/col 저장")
    elif new in content:
        print(f"  [2] 스킵")
    else:
        print(f"  [2] ERROR: 패치 포인트 없음")
        return False

    # ==================================================================
    # 패치 3: lw1() ink-text 노드에서 yoga 절대좌표 저장
    #
    # lw1은 React 노드 트리를 스크린 버퍼에 렌더링하는 함수.
    # ink-text 노드의 write(O, $, T) 호출 시:
    #   O = yogaX (노드의 절대 X좌표)
    #   $ = yogaY (노드의 절대 Y좌표)
    #   T = 렌더링된 텍스트 (ANSI 포함)
    #
    # ESC[7m (ANSI inverse)이 포함된 텍스트 = 가짜 커서가 있는 TextInput.
    # M8()은 ANSI를 strip한 뒤 display width를 계산하는 함수.
    #
    # 멀티라인 처리: 붙여넣기 등으로 노드 텍스트에 \n이 포함될 수 있음.
    # ESC[7m 앞 전체 텍스트의 display width를 구하면 이전 줄 너비가 포함됨.
    # lastIndexOf("\n")로 현재 줄만 추출하여 정확한 열 오프셋 계산.
    # ==================================================================
    old = 'T=wm3(A,T),q.write(O,$,T)'
    new = (
        f'T=wm3(A,T),q.write(O,$,T);'
        f'if(T&&T.indexOf("\\x1b[7m")!==-1)'
        f'{{var __p=T.substring(0,T.indexOf("\\x1b[7m")),__nl=__p.lastIndexOf("\\n");'
        f'{G}.hasInverse=true;{G}.yogaX=Math.floor(O);{G}.yogaY=Math.floor($);'
        f'{G}.nodeCol=M8(__nl===-1?__p:__p.substring(__nl+1))}}'
    )
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        n += 1
        print(f"  [3] lw1() → yogaX/yogaY/nodeCol 저장")
    elif new in content:
        print(f"  [3] 스킵")
    else:
        print(f"  [3] ERROR: 패치 포인트 없음")
        return False

    # ==================================================================
    # 패치 4: YH8() 렌더러 수정
    #
    # YH8은 Ink의 렌더 팩토리 함수. 매 렌더 사이클마다:
    #   (a) cv7/lw1 실행 전에 hasInverse를 리셋
    #   (b) cv7/lw1 실행 후, hasInverse가 true면 lastX/lastY 갱신
    #   (c) return 객체에 __imeX/__imeY/__imeCursorVisible 추가
    #
    # cursor는 원본 {x:0, y:T.height} 유지! (스크롤/클리어 로직 보존)
    # ==================================================================

    # 4a: hasInverse 리셋 (cv7 실행 전)
    old = 'mv7(),gv7(),pv7();let N=pT7();cv7('
    new = f'mv7(),gv7(),pv7();{G}.hasInverse=false;let N=pT7();cv7('
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        n += 1
        print(f"  [4] YH8() hasInverse 리셋 + lastX/Y + __imeX/Y/Visible")
    elif new in content:
        print(f"  [4] 스킵")
    else:
        print(f"  [4] ERROR: 패치 포인트 없음")
        return False

    # 4b: lastX/lastY 갱신 (return 직전)
    # hasInverse가 true인 렌더에서만 갱신, false면 이전 값 유지.
    # 이렇게 해야 유휴 재렌더(blit 캐시)에서도 IME 위치가 유지됨.
    old = 'if(y)jk(y);return{scrollHint:'
    new = (
        f'if(y)jk(y);'
        f'if({G}.hasInverse){{{G}.lastX={G}.yogaX+{G}.nodeCol;{G}.lastY={G}.yogaY+{G}.line}}'
        f'return{{scrollHint:'
    )
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        print(f"       lastX/lastY 갱신")
    elif new in content:
        print(f"       스킵 (lastX/lastY)")
    else:
        print(f"       ERROR: lastX/lastY 패치 포인트 없음")
        return False

    # 4c: __imeX/__imeY/__imeCursorVisible을 프레임 객체에 추가
    #
    # __imeX/__imeY: IME 커서의 절대 좌표 (lastX/lastY 기반, blit 캐시 시에도 유효)
    # __imeCursorVisible: Ink 커서가 보이는 상태인지 여부
    #   - cursorRequested: SK.render에서 A(cursorChar)가 truthy였는지
    #   - blit 캐시 시에도 이전 값 유지 (SK.render 미호출 → 값 변경 없음)
    #   - TextInput 비활성: SK.render(A=falsy) → cursorRequested=false
    #   - altScreen: 항상 false
    old = 'visible:!w||T.height===0}}}}'
    new = (
        f'visible:!w||T.height===0}},'
        f'__imeX:!Y.altScreen?{G}.lastX:void 0,'
        f'__imeY:!Y.altScreen?{G}.lastY:void 0,'
        f'__imeCursorVisible:!Y.altScreen&&{G}.cursorRequested'
        f'}}}}}}'
    )
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        print(f"       __imeX/__imeY/__imeCursorVisible 추가")
    elif new in content:
        print(f"       스킵 (__imeX/__imeY/__imeCursorVisible)")
    else:
        print(f"       ERROR: __imeX/__imeY 패치 포인트 없음")
        return False

    # ==================================================================
    # 패치 5: onRender()에서 ops 배열에 undo/apply + 커서 가시성 삽입
    #
    # Ink의 렌더 파이프라인:
    #   _H8.render() → ops 배열($) → RH8(최적화) → u$8(ANSI 출력)
    #
    # ops 배열에:
    #   - unshift(undo): 실제 커서(IME)에서 Ink 위치(0, T.height)로 복귀
    #   - push(apply): Ink 위치에서 새 IME 위치로 이동
    #   - push(cursorShow/cursorHide): Ink 커서 가시성 전환 시
    #
    # 이렇게 하면:
    #   - _H8.render의 모든 ops는 Ink 위치 기준으로 정상 실행
    #   - 최종 커서는 IME 위치에 있음
    #   - Ink 커서가 보일 때만 실제 커서도 보임
    #   - _H8.render, u$8, parking 코드를 일절 수정하지 않음
    #
    # w = prev frame, Y = new frame
    # undo: cursorMove(-w.__imeX, w.cursor.y - w.__imeY) [왼쪽+아래]
    # apply: cursorMove(Y.__imeX, Y.__imeY - Y.cursor.y) [오른쪽+위]
    #
    # RH8(optimizer)이 연속된 cursorShow+cursorHide를 자동 상쇄하므로
    # 불필요한 ANSI 시퀀스가 출력되지 않음.
    # ==================================================================
    old = 'let X=performance.now(),P=RH8($)'
    new = (
        f'if(w.__imeY!=null)'
        f'$.unshift({{type:"cursorMove",x:-w.__imeX,y:w.cursor.y-w.__imeY}});'
        f'if(Y.__imeX!=null)'
        f'$.push({{type:"cursorMove",x:Y.__imeX,y:Y.__imeY-Y.cursor.y}});'
        f'if(Y.__imeCursorVisible&&!w.__imeCursorVisible)'
        f'$.push({{type:"cursorShow"}});'
        f'if(w.__imeCursorVisible&&!Y.__imeCursorVisible)'
        f'$.push({{type:"cursorHide"}});'
        f'let X=performance.now(),P=RH8($)'
    )
    if old in content and new not in content:
        content = content.replace(old, new, 1)
        n += 1
        print(f"  [5] onRender() → undo/apply + cursorShow/cursorHide")
    elif new in content:
        print(f"  [5] 스킵")
    else:
        print(f"  [5] ERROR: 패치 포인트 없음")
        return False

    # ==================================================================
    # 패치 6, 7은 제거됨.
    #
    # 이전 버전에서는 componentDidMount와 SIGCONT 핸들러에서 커서 숨김
    # (Nu6/ESC[?25l)을 무조건 제거했지만, 이제는 패치 5에서 ops를 통해
    # cursorShow/cursorHide를 동적으로 제어하므로 불필요.
    #
    # - 앱 시작: Ink이 커서를 숨김 (기본 동작 유지)
    # - TextInput 활성: cursorShow ops → 실제 커서 표시 + IME 위치 이동
    # - TextInput 비활성: cursorHide ops → 실제 커서 숨김
    # - 앱 종료: Ink이 커서를 복원 (componentWillUnmount에서 cursorShow)
    # ==================================================================
    print(f"  [6] 스킵 (커서 가시성을 ops로 동적 제어)")
    print(f"  [7] 스킵 (커서 가시성을 ops로 동적 제어)")

    # 저장
    bak = filepath + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(filepath, bak)
        print(f"\n  백업: {bak}")
    with open(filepath, 'w') as f:
        f.write(content)

    delta = len(content) - orig_len
    print(f"\n완료: {n}개 패치 적용 (+{delta} bytes)")
    print(f"\n실행: node {filepath}")
    return True


def unpatch(filepath):
    """백업에서 원본 복원"""
    bak = filepath + '.bak'
    if os.path.exists(bak):
        shutil.copy2(bak, filepath)
        print(f"복원 완료: {bak} → {filepath}")
        return True
    print(f"백업 파일 없음: {bak}")
    return False


def check_patchable(filepath):
    """패치 적용 가능 여부만 확인 (dry-run)"""
    if not os.path.exists(filepath):
        print(f"파일 없음: {filepath}")
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    if G in content:
        print(f"이미 패치됨: {filepath}")
        return True

    # 핵심 패치 포인트 존재 여부 확인
    markers = [
        ('패치 2', 'render(A,q,K,Y){let{line:z,column:_}=this.getPosition();'),
        ('패치 3', 'T=wm3(A,T),q.write(O,$,T)'),
        ('패치 4a', 'mv7(),gv7(),pv7();let N=pT7();cv7('),
        ('패치 5', 'let X=performance.now(),P=RH8($)'),
    ]

    all_found = True
    for name, marker in markers:
        if marker in content:
            print(f"  {name}: OK")
        else:
            print(f"  {name}: 패치 포인트 없음")
            all_found = False

    if all_found:
        print(f"\n패치 가능: {filepath}")
    else:
        print(f"\n패치 불가: 일부 패치 포인트가 없습니다 (버전 불일치?)")
    return all_found


if __name__ == '__main__':
    # --version: 지원 버전 출력
    if '--version' in sys.argv:
        print(SUPPORTED_VERSION)
        sys.exit(0)

    do_unpatch = '--unpatch' in sys.argv
    do_check = '--check' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]

    if not args:
        print("사용법:")
        print("  python3 patch-claude-ime.py <cli.js 경로>")
        print("  python3 patch-claude-ime.py --unpatch <cli.js 경로>")
        print("  python3 patch-claude-ime.py --check <cli.js 경로>")
        print("  python3 patch-claude-ime.py --version")
        print()
        print("권장: ./setup.sh 를 사용하면 설치부터 패치까지 자동으로 진행됩니다.")
        sys.exit(1)

    target = args[0]

    if do_check:
        sys.exit(0 if check_patchable(target) else 1)
    elif do_unpatch:
        unpatch(target)
    else:
        if not os.path.exists(target):
            print(f"파일 없음: {target}")
            sys.exit(1)
        patch(target)
