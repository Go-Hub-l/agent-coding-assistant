#!/usr/bin/env bash
# ============================================================
#  agent-assist 一键启动脚本
#  用法:
#    ./run.sh build "实现一个用户登录功能"        # 运行 pipeline
#    ./run.sh build "重构 API 层" -p ./my-project # 迭代已有项目
#    ./run.sh build "..." --intervene             # 人工审查模式
#    ./run.sh setup                               # 仅做环境初始化
#    ./run.sh test                                # 运行测试
#    ./run.sh help                                # 查看帮助
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_MIN="3.10"

# ── 颜色 ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[info]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
err()   { echo -e "${RED}[error]${NC} $*"; }

# ── 查找 Python ───────────────────────────────────────────────
find_python() {
    local candidates=("python3.13" "python3.12" "python3.11" "python3.10" "python3")
    for py in "${candidates[@]}"; do
        if command -v "$py" &>/dev/null; then
            local ver
            ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            # 比较版本
            if python3 -c "exit(0 if tuple(map(int,'$ver'.split('.'))) >= tuple(map(int,'$PYTHON_MIN'.split('.'))) else 1)" 2>/dev/null; then
                echo "$py"
                return 0
            fi
        fi
    done
    return 1
}

# ── 环境初始化 ────────────────────────────────────────────────
setup_env() {
    # 1) 查找 Python
    local py
    if [[ -f "$VENV_DIR/bin/python" ]]; then
        py="$VENV_DIR/bin/python"
        ok "使用已有虚拟环境: $VENV_DIR"
    else
        info "查找 Python >= $PYTHON_MIN ..."
        py=$(find_python) || {
            err "未找到 Python >= $PYTHON_MIN，请先安装"
            echo "  macOS:  brew install python@3.11"
            echo "  Ubuntu: sudo apt install python3.11 python3.11-venv"
            exit 1
        }
        local ver
        ver=$("$py" --version 2>&1)
        ok "找到 $ver"

        # 2) 创建虚拟环境
        info "创建虚拟环境: $VENV_DIR"
        "$py" -m venv "$VENV_DIR"
        ok "虚拟环境已创建"
    fi

    # 3) 激活虚拟环境
    source "$VENV_DIR/bin/activate"

    # 4) 安装/更新依赖
    if ! pip show agent-coding-assistant &>/dev/null 2>&1; then
        info "安装项目依赖 (pip install -e .) ..."
        pip install -e "$SCRIPT_DIR" --quiet
        ok "依赖安装完成"
    else
        ok "依赖已安装"
    fi

    # 5) .env 文件
    if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
        if [[ -f "$SCRIPT_DIR/.env.example" ]]; then
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
            warn ".env 文件已从 .env.example 创建，请编辑并填入 DEEPSEEK_API_KEY"
        fi
    else
        ok ".env 文件已存在"
    fi

    # 6) 检查 API Key
    source "$SCRIPT_DIR/.env" 2>/dev/null || true
    if [[ -z "${DEEPSEEK_API_KEY:-}" || "${DEEPSEEK_API_KEY}" == "your-api-key-here" ]]; then
        warn "DEEPSEEK_API_KEY 未配置"
        echo ""
        echo "  请编辑 $SCRIPT_DIR/.env 并填入你的 API Key:"
        echo "    DEEPSEEK_API_KEY=sk-xxxxxxxx"
        echo ""
    else
        ok "API Key 已配置 (${DEEPSEEK_API_KEY:0:6}...)"
    fi
}

# ── 运行测试 ──────────────────────────────────────────────────
run_tests() {
    setup_env
    info "运行测试 ..."
    python -m pytest "$SCRIPT_DIR/tests" -v "$@"
}

# ── 帮助信息 ──────────────────────────────────────────────────
show_help() {
    echo ""
    echo -e "${BLUE}Agent Coding Assistant — 一键启动脚本${NC}"
    echo ""
    echo "用法:"
    echo "  ./run.sh <command> [args...]"
    echo ""
    echo "命令:"
    echo "  build <需求描述> [options]   运行多 Agent 开发流水线"
    echo "  setup                        仅初始化环境（虚拟环境 + 依赖 + .env）"
    echo "  test                         运行测试套件"
    echo "  help                         显示此帮助信息"
    echo ""
    echo "build 选项:"
    echo "  -p, --project-dir <path>     指定已有项目目录（迭代模式）"
    echo "  -i, --intervene              每个阶段暂停审查"
    echo "  --intervene-at <stages>      指定阶段暂停（如 pm,coder）"
    echo "  -e, --env-file <path>        指定 .env 文件路径"
    echo ""
    echo "示例:"
    echo "  ./run.sh build \"实现用户注册和登录 REST API\""
    echo "  ./run.sh build \"添加 JWT 刷新机制\" -p ./my-project"
    echo "  ./run.sh build \"重构数据库查询层\" --intervene"
    echo "  ./run.sh build \"添加 WebSocket 通知\" --intervene-at pm,architect"
    echo "  ./run.sh setup"
    echo "  ./run.sh test"
    echo ""
}

# ── 主入口 ────────────────────────────────────────────────────
main() {
    local cmd="${1:-help}"

    case "$cmd" in
        setup)
            setup_env
            ok "环境初始化完成，可以直接运行: ./run.sh build \"你的需求\""
            ;;
        test)
            shift
            run_tests "$@"
            ;;
        build)
            shift
            setup_env
            agent-assist build "$@"
            ;;
        version)
            setup_env
            agent-assist version
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            err "未知命令: $cmd"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
