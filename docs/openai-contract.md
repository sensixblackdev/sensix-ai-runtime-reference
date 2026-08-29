# Contrato OpenAI e exemplos

## Chat completions com tool calling

```json
{
  "model": "gpt-oss-120b",
  "messages": [{"role": "user", "content": "Liste os testes do projeto"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "list_project_tests",
      "description": "Lista testes dentro do projeto permitido.",
      "parameters": {"type": "object", "properties": {}, "additionalProperties": false}
    }
  }],
  "tool_choice": "auto"
}
```

O gateway devolve `choices[0].message.tool_calls`; o executor roda somente a função autorizada e envia o resultado de volta como mensagem de papel `tool`.

## JSON estruturado

```json
{
  "model": "gpt-oss-120b",
  "messages": [{"role": "user", "content": "Resuma os riscos"}],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "risk_summary",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {"risks": {"type": "array", "items": {"type": "string"}}},
        "required": ["risks"],
        "additionalProperties": false
      }
    }
  },
  "temperature": 0
}
```

## Erro seguro

Erros devem seguir o envelope OpenAI e incluir `X-Trace-ID`, sem stack trace, prompt ou segredo:

```json
{"error":{"message":"No healthy model worker","type":"server_error","traceId":"..."}}
```
