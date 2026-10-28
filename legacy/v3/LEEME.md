# Archivo V3 (no usar en producción V4)

- `Dockerfile.server`, `compose.server.yaml`: servidor FastAPI/SQLite V3 (`server/`), solo referencia y tests heredados.
- `Dockerfile.agent`, `compose.agent.yaml`: agente V3 en Docker. **V4 no necesita Docker**; el agente V4 corre nativo con `01..03` (Windows) o `macos/` (Mac).
- `TikTokStudioV3.tsx`: componente para el Site V11 de ChatGPT; no verificado contra ese Site.
