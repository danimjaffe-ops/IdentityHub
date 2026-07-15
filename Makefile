.PHONY: install install-backend install-frontend dev dev-backend dev-frontend build serve clean init-db

install: install-backend install-frontend

install-backend:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

dev:
	@trap 'kill 0' EXIT; \
		.venv/bin/flask run --port 5000 & \
		cd frontend && npm run dev & \
		wait

dev-backend:
	.venv/bin/flask run --port 5000

dev-frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

serve: build
	.venv/bin/flask run --port 5000

clean:
	rm -rf frontend/dist frontend/node_modules

init-db:
	.venv/bin/flask db upgrade
