# Docker Layout

The service-specific backend image is defined in `docker/Dockerfile`. The
frontend keeps its Next.js image definition in `frontend/Dockerfile`.

Run the full stack from the repository root with:

```powershell
docker compose up -d --build
```

The equivalent layout-aware entrypoint is:

```powershell
docker compose -f docker/docker-compose.yml up -d --build
```

Infrastructure-specific configuration is stored under `infra/`.
