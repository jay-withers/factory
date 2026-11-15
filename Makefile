.DEFAULT_GOAL := help

.PHONY: help install login lint sync task verify status clean-worktrees

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install pre-commit hooks (run once after cloning)
	mise install
	pre-commit install
	pre-commit install --hook-type commit-msg

login: ## Log gh in to GitHub if it isn't already, then sync
	@scripts/login.sh

lint: ## Run all pre-commit hooks against every file
	pre-commit run --all-files

sync: ## Clone every repo into repos/, fast-forward clean ones, regenerate CATALOG.md
	scripts/sync.sh

task: ## Start a task: make task REPO=<repo> BRANCH=<branch> (prints the worktree path)
	@test -n "$(REPO)" -a -n "$(BRANCH)" || { echo "usage: make task REPO=<repo> BRANCH=<branch>"; exit 2; }
	@scripts/task.sh "$(REPO)" "$(BRANCH)"

verify: ## Lint + test a worktree and record it as fit to push: make verify DIR=worktrees/<name>
	@test -n "$(DIR)" || { echo "usage: make verify DIR=worktrees/<name>"; exit 2; }
	@scripts/verify.sh "$(DIR)"

status: ## List uncommitted/unpushed work and every open PR
	@scripts/status.sh

clean-worktrees: ## Remove worktrees whose PR is merged or closed
	scripts/clean-worktrees.sh
