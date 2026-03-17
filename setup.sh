#!/usr/bin/env bash
#
# Claude Code CJK IME Fix - 설치/관리 스크립트
#
# 사용법:
#   git clone https://github.com/astron8t-voyagerx/claude-code-korean-fix.git
#   cd claude-code-korean-fix
#   ./setup.sh              # 설치 (기본)
#
# 업데이트:
#   cd claude-code-korean-fix
#   git pull
#   ./setup.sh update
#
# 기타:
#   ./setup.sh uninstall    # 완전 제거
#   ./setup.sh status       # 상태 확인
#
set -euo pipefail

# ─── 상수 ──────────────────────────────────────────────
CLAUDE_VERSION="2.1.77"
INSTALL_DIR="$HOME/.claude-ime-fix"
CLI_JS="$INSTALL_DIR/node_modules/@anthropic-ai/claude-code/cli.js"
WRAPPER="$INSTALL_DIR/bin/kclaude"
PATCH_SCRIPT_NAME="patch-claude-ime.py"

# ─── 색상 / 유틸 ──────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { printf "${BLUE}${BOLD}[INFO]${NC} %s\n" "$*"; }
success() { printf "${GREEN}${BOLD}[OK]${NC} %s\n" "$*"; }
warn()    { printf "${YELLOW}${BOLD}[WARN]${NC} %s\n" "$*"; }
error()   { printf "${RED}${BOLD}[ERROR]${NC} %s\n" "$*" >&2; }

# ─── 스크립트 위치 감지 ───────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 패치 스크립트가 같은 디렉토리에 있는지 확인
if [ ! -f "$SCRIPT_DIR/$PATCH_SCRIPT_NAME" ]; then
    error "패치 스크립트를 찾을 수 없습니다: $SCRIPT_DIR/$PATCH_SCRIPT_NAME"
    error ""
    error "이 스크립트는 git 저장소에서 실행해야 합니다:"
    error "  git clone https://github.com/astron8t-voyagerx/claude-code-korean-fix.git"
    error "  cd claude-code-korean-fix"
    error "  ./setup.sh"
    exit 1
fi

# ─── 전제조건 확인 ─────────────────────────────────────
check_prerequisites() {
    local missing=0

    for cmd in node npm python3; do
        if ! command -v "$cmd" &>/dev/null; then
            error "'$cmd'을(를) 찾을 수 없습니다. 설치 후 다시 시도하세요."
            missing=1
        fi
    done

    if [ "$missing" -ne 0 ]; then
        echo ""
        info "필요한 도구:"
        info "  - Node.js 18+ (https://nodejs.org)"
        info "  - npm (Node.js와 함께 설치됨)"
        info "  - Python 3 (https://python.org)"
        exit 1
    fi

    # Node 버전 확인 (>= 18)
    local node_major
    node_major=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "$node_major" -lt 18 ]; then
        error "Node.js 18 이상이 필요합니다 (현재: $(node -v))"
        exit 1
    fi

    info "Node.js $(node -v) | npm $(npm -v) | Python $(python3 --version 2>&1 | awk '{print $2}')"
}

# ─── 래퍼 스크립트 생성 ───────────────────────────────
generate_wrapper() {
    cat > "$WRAPPER" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Claude Code with CJK IME fix
# Managed by claude-ime-fix - do not edit manually
exec "$HOME/.claude-ime-fix/node_modules/.bin/claude" "$@"
WRAPPER_EOF
    chmod +x "$WRAPPER"
    info "래퍼 스크립트 생성: $WRAPPER"
}

# ─── 셸 RC 통합 ──────────────────────────────────────
get_shell_rc() {
    local shell_name
    shell_name="$(basename "${SHELL:-/bin/bash}")"

    case "$shell_name" in
        zsh)  echo "$HOME/.zshrc" ;;
        fish) echo "$HOME/.config/fish/config.fish" ;;
        *)    echo "$HOME/.bashrc" ;;
    esac
}

setup_shell() {
    local rc_file
    rc_file="$(get_shell_rc)"
    local shell_name
    shell_name="$(basename "${SHELL:-/bin/bash}")"

    # 이미 존재하면 스킵
    if [ -f "$rc_file" ] && grep -q "claude-ime-fix" "$rc_file" 2>/dev/null; then
        info "셸 설정 이미 존재: $rc_file"
        return
    fi

    # RC 파일 없으면 생성
    mkdir -p "$(dirname "$rc_file")"
    touch "$rc_file"

    # fish는 문법이 다름
    if [ "$shell_name" = "fish" ]; then
        cat >> "$rc_file" << 'FISH_EOF'

# >>> claude-ime-fix >>>
fish_add_path $HOME/.claude-ime-fix/bin
# <<< claude-ime-fix <<<
FISH_EOF
    else
        cat >> "$rc_file" << 'SHELL_EOF'

# >>> claude-ime-fix >>>
export PATH="$HOME/.claude-ime-fix/bin:$PATH"
# <<< claude-ime-fix <<<
SHELL_EOF
    fi

    success "셸 설정 추가: $rc_file"
}

remove_shell_integration() {
    local rc_files=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.config/fish/config.fish")

    for rc_file in "${rc_files[@]}"; do
        if [ -f "$rc_file" ] && grep -q "claude-ime-fix" "$rc_file" 2>/dev/null; then
            # 마커 사이 블록 제거 (빈 줄 포함)
            local tmp_file
            tmp_file="$(mktemp)"
            awk '
                />>> claude-ime-fix >>>/ { skip=1; next }
                /<<< claude-ime-fix <<</ { skip=0; next }
                !skip { print }
            ' "$rc_file" > "$tmp_file"
            mv "$tmp_file" "$rc_file"
            info "셸 설정 제거: $rc_file"
        fi
    done
}

# ─── 메타데이터 ──────────────────────────────────────
save_metadata() {
    cat > "$INSTALL_DIR/.metadata" << EOF
CLAUDE_VERSION=$CLAUDE_VERSION
INSTALLED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
NODE_PATH=$(command -v node)
REPO_DIR=$SCRIPT_DIR
EOF
}

# ─── 설치 ────────────────────────────────────────────
do_install() {
    echo ""
    printf "${BOLD}Claude Code CJK IME Fix${NC} - v${CLAUDE_VERSION}\n"
    printf "한국어/중국어/일본어 IME 커서 위치 수정 패치\n"
    echo ""

    check_prerequisites
    echo ""

    # 설치 디렉토리 생성
    mkdir -p "$INSTALL_DIR/bin"

    # npm 설치 (격리된 공간)
    info "Claude Code v${CLAUDE_VERSION} 설치 중... (1-2분 소요)"
    npm install --prefix "$INSTALL_DIR" "@anthropic-ai/claude-code@${CLAUDE_VERSION}" --no-fund --no-audit 2>&1 | tail -1
    echo ""

    # cli.js 존재 확인
    if [ ! -f "$CLI_JS" ]; then
        error "cli.js를 찾을 수 없습니다: $CLI_JS"
        exit 1
    fi

    # 패치 스크립트 복사 (항상 repo에서 최신 복사)
    cp "$SCRIPT_DIR/$PATCH_SCRIPT_NAME" "$INSTALL_DIR/$PATCH_SCRIPT_NAME"
    info "패치 스크립트 복사: $SCRIPT_DIR/$PATCH_SCRIPT_NAME"
    echo ""

    # 패치 적용
    info "패치 적용 중..."
    python3 "$INSTALL_DIR/$PATCH_SCRIPT_NAME" "$CLI_JS"
    echo ""

    # 문법 검증
    if node --check "$CLI_JS" 2>/dev/null; then
        success "JavaScript 문법 검증 통과"
    else
        error "패치된 cli.js에 문법 오류가 있습니다!"
        error "복원 중..."
        python3 "$INSTALL_DIR/$PATCH_SCRIPT_NAME" --unpatch "$CLI_JS"
        exit 1
    fi

    # 래퍼 생성
    generate_wrapper

    # 셸 통합
    setup_shell

    # 메타데이터 저장
    save_metadata

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    success "설치 완료!"
    echo ""
    info "새 터미널을 열거나 다음 명령을 실행하세요:"
    printf "  ${BOLD}source $(get_shell_rc)${NC}\n"
    echo ""
    info "그 후 패치된 Claude Code를 실행하세요:"
    printf "  ${BOLD}kclaude${NC}\n"
    echo ""
    info "관리:"
    printf "  상태 확인:  ${BOLD}./setup.sh status${NC}\n"
    printf "  업데이트:   ${BOLD}git pull && ./setup.sh update${NC}\n"
    printf "  제거:       ${BOLD}./setup.sh uninstall${NC}\n"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ─── 제거 ────────────────────────────────────────────
do_uninstall() {
    echo ""
    printf "${BOLD}Claude Code CJK IME Fix${NC} - 제거\n"
    echo ""

    if [ ! -d "$INSTALL_DIR" ]; then
        warn "설치 디렉토리가 없습니다: $INSTALL_DIR"
        # 셸 설정만 정리
        remove_shell_integration
        return
    fi

    remove_shell_integration
    rm -rf "$INSTALL_DIR"

    echo ""
    success "제거 완료!"
    info "새 터미널을 열면 변경사항이 반영됩니다."
    info "이 git 저장소도 필요 없으면 삭제하세요: rm -rf $SCRIPT_DIR"
}

# ─── 상태 확인 ───────────────────────────────────────
do_status() {
    echo ""
    printf "${BOLD}Claude Code CJK IME Fix${NC} - 상태\n"
    echo ""

    # 설치 확인
    if [ ! -d "$INSTALL_DIR" ]; then
        warn "설치되지 않음"
        return
    fi
    success "설치 디렉토리: $INSTALL_DIR"

    # 버전 확인
    if [ -f "$INSTALL_DIR/.metadata" ]; then
        local version
        version=$(grep "^CLAUDE_VERSION=" "$INSTALL_DIR/.metadata" 2>/dev/null | cut -d= -f2)
        local installed_at
        installed_at=$(grep "^INSTALLED_AT=" "$INSTALL_DIR/.metadata" 2>/dev/null | cut -d= -f2)
        info "Claude Code 버전: ${version:-알 수 없음}"
        info "설치 일시: ${installed_at:-알 수 없음}"
    fi

    # 패치 상태
    if [ -f "$CLI_JS" ]; then
        if grep -q "globalThis.__ic" "$CLI_JS" 2>/dev/null; then
            success "패치 상태: 적용됨"
        else
            warn "패치 상태: 미적용"
        fi
    else
        error "cli.js 없음: $CLI_JS"
    fi

    # 래퍼 확인
    if [ -f "$WRAPPER" ] && [ -x "$WRAPPER" ]; then
        success "래퍼 스크립트: $WRAPPER"
    else
        warn "래퍼 스크립트 없음"
    fi

    # PATH 확인
    local claude_path
    claude_path="$(command -v kclaude 2>/dev/null || true)"
    if [ -n "$claude_path" ]; then
        if [[ "$claude_path" == *"claude-ime-fix"* ]]; then
            success "kclaude 명령: $claude_path (패치 버전)"
        else
            warn "kclaude 명령: $claude_path (패치 버전 아님!)"
            info "  PATH에서 $INSTALL_DIR/bin이 우선순위가 높은지 확인하세요"
        fi
    else
        warn "kclaude 명령을 찾을 수 없음 (셸을 재시작하세요)"
    fi

    # 셸 설정 확인
    local rc_file
    rc_file="$(get_shell_rc)"
    if [ -f "$rc_file" ] && grep -q "claude-ime-fix" "$rc_file" 2>/dev/null; then
        success "셸 설정: $rc_file"
    else
        warn "셸 설정 없음: $rc_file"
    fi

    # repo 최신 여부 힌트
    echo ""
    info "업데이트 방법: cd $SCRIPT_DIR && git pull && ./setup.sh update"
}

# ─── 메인 ────────────────────────────────────────────
case "${1:-install}" in
    install)    do_install ;;
    update)     do_install ;;
    uninstall)  do_uninstall ;;
    status)     do_status ;;
    -h|--help)
        echo "사용법: $0 {install|update|uninstall|status}"
        echo ""
        echo "  install    Claude Code를 격리된 공간에 설치하고 IME 패치 적용"
        echo "  update     재설치 + 재패치 (git pull 후 실행)"
        echo "  uninstall  완전 제거"
        echo "  status     현재 상태 확인"
        ;;
    *)
        error "알 수 없는 명령: $1"
        echo "사용법: $0 {install|update|uninstall|status}"
        exit 1
        ;;
esac
