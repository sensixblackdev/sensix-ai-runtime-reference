# Arquitetura de runtime

## Objetivo

Entregar `/v1/models`, `/v1/chat/completions` e SSE no contrato OpenAI, sem expor o processo vLLM diretamente à internet. O gateway é o único ponto público e controla autenticação, limites, trace, roteamento e política de ferramentas.

## Memória e cache

| Camada | Onde fica | Por que existe | Regra |
|---|---|---|---|
| Pesos | volume `hf-cache` | evita novo download em cada container | persistir no Pod/volume de rede |
| Compile cache | volume `vllm-cache` | evita recompilação de kernels | persistir junto do runtime |
| KV cache | VRAM do worker | reduz recomputação no contexto ativo | dimensionar por `max-model-len` e concorrência |
| Prefix cache | KV cache do vLLM | reusa prefixes idênticos, como system prompt e tools | ativar `--enable-prefix-caching` |
| Sessão | banco externo/Redis | memória conversacional, nunca o prompt inteiro em logs | TTL e tenant ID |

Para GPT-OSS-120B em uma H100 80 GB, comece com `max-model-len=32768`, `gpu-memory-utilization=0.92` e baixa concorrência. Aumente contexto somente após medir OOM, TTFT e tokens/s.

## Roteamento e load balancing

1. Normalizar o `model` externo para um ID do catálogo.
2. Filtrar workers pelo modelo carregado e versão de runtime compatível.
3. Aplicar health check curto (`/health`) e escolher o menor `in_flight`.
4. Em falha anterior ao primeiro token, tentar uma única réplica saudável.
5. Depois do primeiro token SSE, nunca trocar de worker; encerrar com erro estruturado e `traceId`.

Para múltiplos gateways, guardar `in_flight`, circuit breaker e limites de cliente no Redis/Valkey, não na memória de cada processo.

## Ferramentas

O modelo apenas devolve `tool_calls` compatíveis com OpenAI. Um executor separado aplica:

- allowlist de nomes e JSON Schema;
- diretório raiz por projeto; sem caminhos absolutos fora dele;
- timeout, limite de saída e auditoria;
- redator de tokens em entrada, saída e log;
- aprovação explícita para rede, shell ou alterações fora do workspace.

Nunca entregue um shell root, Docker socket ou arquivo `.env` diretamente ao container de inferência.

## Saída estruturada e JSON auto-repair

Prefira `response_format: {"type": "json_schema"}` e temperatura zero. Se a validação Pydantic falhar, o gateway realiza **uma única** regeneração com o erro resumido e o conteúdo truncado. Persistir/reenviar sem limite causa loops e custo imprevisível.

Streaming não é retroativamente reparável: validar no cliente, ou solicitar resposta estruturada não-streaming quando o JSON for obrigatório.
