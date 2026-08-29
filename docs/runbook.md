# Runbook de operação

## Antes de iniciar

1. Confirmar quota e custo do Pod; Pod cobra enquanto está ligado.
2. Criar volume persistente para `hf-cache` e `vllm-cache` quando haverá reinícios.
3. Configurar firewall: somente `8080` do gateway via reverse proxy TLS; nunca publicar `8000` do vLLM.
4. Gerar chave exclusiva do gateway e guardar no cofre do operador.

## Início e smoke test

```bash
docker compose --env-file .env -f docker/compose.pod-h100.yml up -d
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/v1/models -H "Authorization: Bearer $SENSIX_GATEWAY_API_KEY"
```

## Sinais para parar ou reduzir

- `CUDA out of memory`: reduzir `max-model-len` ou concorrência; não aumentar tentativas.
- TTFT alto em primeiro request: pesos/compile cache ainda não foram aquecidos.
- `5xx` acima de 2%: retirar worker do pool, preservar trace IDs e investigar logs sanitizados.
- Sem demanda: parar o Pod. Volumes persistentes têm cobrança própria.

## Métricas mínimas

`request_count`, `error_rate`, `ttft_ms`, `tokens_per_second`, `queue_ms`, `active_requests`, `gpu_memory_utilization`, `cache_hit_rate` e `tool_execution_ms`.
