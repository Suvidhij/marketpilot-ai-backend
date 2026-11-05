# API — Phase 1

Base URL: `http://localhost:8000`. Interactive specification: `/docs`. OpenAPI JSON: `/openapi.json`.

## GET /api/v1/health

Public liveness endpoint. Returns HTTP 200:

```json
{"status":"ok","service":"MarketPilot AI API","version":"0.1.0"}
```

No request body or credentials. Unsupported methods return 405 and missing routes return 404. The configured CORS middleware only permits trusted UI origins and GET requests. Database readiness is outside this check's scope.

Authentication and business endpoints are not implemented. They will be documented with their request, response, error, and ownership contracts when added.
