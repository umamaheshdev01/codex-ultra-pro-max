.PHONY: dev

dev:
	cd backend && ./.venv/bin/python -m uvicorn src.main:app --reload --port 3001
