# Makefile

# ─── Configurable constants ────────────────────────────────────────────
PREFECT_API_URL := http://127.0.0.1:4200/api
FASTAPI_HOST    := 127.0.0.1
FASTAPI_PORT    := 8000
MAX_TRIES       := 3
SLEEP           := 5
LOG_DIR         := logs

# Export so child scripts see them
export PREFECT_API_URL FASTAPI_HOST FASTAPI_PORT MAX_TRIES SLEEP LOG_DIR

.PHONY: start stop help

start: ## Run the end-to-end launcher (FastAPI + Prefect + Dask)
	@echo "[MAKE] Using:"
	@echo "       PREFECT_API_URL = $(PREFECT_API_URL)"
	@echo "       FASTAPI_HOST    = $(FASTAPI_HOST)"
	@echo "       FASTAPI_PORT    = $(FASTAPI_PORT)"
	@echo "       MAX_TRIES       = $(MAX_TRIES)"
	@echo "       SLEEP           = $(SLEEP)"
	@echo "       LOG_DIR         = $(LOG_DIR)"
	@bash scripts/e2e.sh

stop: ## Stop all running services (FastAPI, Prefect, worker jobs)
	@echo "[MAKE] Stopping services..."
	-@pkill -f "uvicorn .*--host $(FASTAPI_HOST) --port $(FASTAPI_PORT)" || true
	-@pkill -f "python -m prefect_dag.eo_monthly_mosaic"                 || true
	-@pkill -f "prefect server start"                                   || true
	@echo "[MAKE] Done."

help: ## Show available make commands
	@echo "===================================================="
	@echo "                Available Make Targets"
	@echo "===================================================="
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
