# hermes_deploy — EU_DE_NEGOCIOS v2

Deploy do [hermes-agent](https://github.com/NousResearch/hermes-agent) configurado
como agente autônomo de negócios digitais para Railway.

## Estrutura

```
hermes_deploy/
├── Dockerfile          ← Instala hermes-agent + nossa config
├── railway.toml        ← Config do Railway (aponte para este dir)
├── start.sh            ← Setup de ~/.hermes/ + inicia daemon
├── daemon.py           ← Loop autônomo (roda o CronScheduler)
├── config.yaml         ← Config do hermes (modelo, ferramentas, memória)
├── SOUL.md             ← Identidade e constituição do agente
├── skills/
│   ├── estatuto-constitucional.md   ← Regras invioláveis
│   ├── afiliados-brasil.md          ← Conhecimento de afiliados BR
│   └── ciclo-de-negocios.md         ← Procedimento padrão de ciclo
└── cron/
    └── ciclo-negocios.yaml          ← Job de 4h (o coração do agente)
```

## Variáveis de ambiente necessárias no Railway

| Variável | Obrigatória | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | Chave da OpenAI |
| `SUPABASE_URL` | Recomendada | Para persistência |
| `SUPABASE_SERVICE_ROLE_KEY` | Recomendada | Para persistência |
| `PERPLEXITY_API_KEY` | Opcional | Busca melhorada |
| `TELEGRAM_BOT_TOKEN` | Opcional | Notificações |
| `TELEGRAM_CHAT_ID` | Opcional | Seu chat ID no Telegram |
| `HERMES_HOME` | Auto | `/data/hermes` (Railway volume) |

## Deploy no Railway

1. Crie um novo serviço no Railway
2. Conecte ao repo `mdguerra00/eu_digital`
3. Em **Settings → Build**, defina:
   - **Root directory**: `hermes_deploy`
   - **Dockerfile path**: `Dockerfile`
4. Adicione as variáveis de ambiente
5. (Opcional) Monte um volume em `/data/hermes` para persistência entre deploys
6. Deploy!

## Como funciona

- O `daemon.py` importa o `CronScheduler` do hermes-agent
- O scheduler roda um `tick()` a cada 60 segundos
- A cada 4 horas, o job `ciclo-negocios.yaml` dispara
- O agente executa o ciclo com as skills pré-carregadas
- Resultados salvos em `$HERMES_HOME/cron/outputs/`
- O agente **cria novas skills automaticamente** quando aprende algo

## Próximos passos após validação

- [ ] Configurar Telegram para notificações em tempo real
- [ ] Montar volume Railway para persistir skills entre deploys
- [ ] Adicionar skill de rastreamento financeiro (Supabase)
- [ ] Ativar `market_analyzer` como skill do hermes
