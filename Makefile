.PHONY: init up down test lint build logs model k8s
init:
	python scripts/init_env.py
up:
	docker compose up -d --build
down:
	docker compose down
test:
	python -m pytest -q
lint:
	python -m ruff check .
	cd apps/web && pnpm lint
build:
	cd apps/web && pnpm build
logs:
	docker compose logs -f api
model:
	docker compose exec ollama ollama pull qwen2.5:1.5b
k8s:
	kubectl apply -k infrastructure/k8s
