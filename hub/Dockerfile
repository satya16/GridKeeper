# Multi-stage: build the React+Ant Design dashboard, then bundle it into a
# slim Python runtime alongside the FastAPI app -- one self-contained
# image, no separate Node server or local frontend-build step needed at
# `docker run` time. See vite.config.js: it builds straight into
# app/static/dist/, which is where hub/app/main.py expects to find it.

FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY --from=frontend-build /build/app/static/dist ./app/static/dist

# grid.db defaults to living next to the code (see app/db.py), which is
# fine on bare metal but wrong in a container -- that path is inside the
# image's writable layer and vanishes on `docker rm`. Point it at a
# separate volume instead so data survives a container restart/recreate.
ENV GRIDKEEPER_DB=/data/grid.db
VOLUME ["/data"]

# GRIDKEEPER_ADMIN_PASSWORD and GRIDKEEPER_SECRET_KEY are deliberately
# not set here -- pass them at `docker run` time (-e), never bake real
# secrets into an image that might get pushed to a public registry.

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
