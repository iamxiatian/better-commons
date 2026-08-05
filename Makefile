.PHONY: help install test lint fmt build clean
help:  ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:   ## 安装虚拟环境+依赖
	uv sync

test:      ## 跑测试
	uv run pytest

lint:      ## 代码检查
	uv run ruff check --fix src/
	uv run pyright src/

fmt:       ## 格式化
	uv run ruff format src/

build:     ## 构建 wheel
	uv build

fine:      ## 代码检查(lint)
	uv run ruff check --fix src tests
	uv run ruff format src tests
	uv run basedpyright src tests --level warning


clean:     ## 删缓存+临时文件
	uv cache clean
	rm -rf dist/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
