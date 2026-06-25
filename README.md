# BIORADAR - Agente de Inteligencia Biotech

Agente autonomo que monitoriza o setor biotech dos EUA a partir de **dados exclusivamente publicos e gratuitos**, deteta eventos materiais, e gera memos de analista. Pipeline de IA vertical ponta-a-ponta com infraestrutura de custo zero.

## O que faz

Mantem, para um universo de ~50 biotechs cotadas, um retrato de inteligencia sempre atualizado:

- **Calendario de catalisadores** - readouts de ensaios agendados (ClinicalTrials.gov) + decisoes da FDA (datas PDUFA extraidas de 8-K)
- **Detecao de eventos materiais** - classifica 8-K (readouts, decisoes regulatorias, designacoes) com sentimento
- **Cash runway** - meses de caixa restantes por empresa (10-Q via SEC EDGAR)
- **Alertas de diluicao** - cruza ofertas de acoes (424B) com runway curto
- **Atividade de insiders** - compras em mercado aberto (Form 4)
- **Memos de analista** - sintese em linguagem natural por LLM, a partir dos factos extraidos
- **Dashboard** - site estatico que apresenta tudo

## Fontes (todas publicas e gratuitas)

| Fonte | Dados |
|---|---|
| SEC EDGAR | 8-K, Form 4, 10-Q, 424B |
| ClinicalTrials.gov v2 | ensaios, estados, datas de conclusao |
| yfinance | preco, market cap |
| Groq (LLM gratuito) | geracao dos memos |

## Arquitetura

```text
agent/
|-- config.py         # universo + identificacao
|-- db/
|   `-- database.py   # schema SQLite (estado do agente)
|-- ingest/           # 6 ingestores incrementais (um por fonte)
|   |-- ingest_8k.py
|   |-- ingest_trials.py
|   |-- ingest_prices.py
|   |-- ingest_fundamentals.py
|   |-- ingest_insiders.py
|   `-- ingest_dilution.py
|-- detect/
|   `-- detect_8k.py  # detecao de eventos a partir de texto
`-- report/           # calendario, one-pagers, memos, site
    |-- calendar.py
    |-- onepager.py
    |-- memo.py
    `-- site.py
run.py                # ponto de entrada: python run.py <comando>
```

O agente e **stateful e incremental**: cada corrida so processa o que e novo desde a ultima (guardado em SQLite). Desenhado para correr em continuo via GitHub Actions.

## Uso

```bash
python run.py init         # inicializa BD + resolve universo
python run.py update       # atualiza todas as fontes (incremental)
python run.py calendar     # mostra o calendario de catalisadores
python run.py profile MDGL # perfil de uma empresa
python run.py memos groq   # gera memos com LLM
python run.py site         # gera o dashboard
```

A chave da API do LLM vive num ficheiro `.env` local (nunca versionado).

## Automacao

O agente corre **autonomamente nos servidores do GitHub** (GitHub Actions), nao na maquina do autor. O computador local pode estar desligado - a atualizacao acontece na nuvem.

Um workflow agendado via cron corre diariamente. A cada execucao, o GitHub liga uma maquina temporaria que: (1) descarrega o codigo e a base de dados do repositorio; (2) corre a ingestao incremental, indo as fontes buscar apenas o que e novo; (3) regenera o dashboard; (4) faz commit da base de dados atualizada; (5) republica o site no GitHub Pages.

```text
GitHub Actions (cron diario)
  -> checkout codigo + BD
     -> run.py update fast   (ingestao incremental das fontes)
        -> run.py site        (regenera o dashboard)
           -> commit da BD + publica no GitHub Pages
```

A base de dados e **versionada** no repositorio (~1.6 MB) para que cada execucao parta do estado anterior e so processe o delta - o que torna as corridas diarias rapidas (minutos) em vez de horas.

**Decisoes de design e limitacoes:**

- **Estado versionado.** Versiona-se `data/agent.db` em vez de a reconstruir do zero a cada corrida. Trade-off: o historico do Git acumula versoes da BD, mas as execucoes ficam rapidas e robustas.
- **Cron best-effort.** O agendador do GitHub pode atrasar uma corrida ou, raramente, falha-la em periodos de carga. Irrelevante para dados de frequencia diaria.
- **Pausa por inatividade.** O GitHub suspende workflows agendados em repositorios sem commits ha ~60 dias; reativa-se com qualquer commit ou execucao manual.
- **Segredos.** A chave da API do LLM nunca esta no codigo - vive como secret encriptado do repositorio (GROQ_API_KEY), injetado no ambiente apenas durante a execucao.
- **Limite do LLM.** O tier gratuito do Groq tem limite diario de pedidos; a geracao de memos respeita-o (gera por lotes, com fallback deterministico por template).

O workflow tambem pode ser disparado a mao (aba Actions -> Run workflow), util para forcar uma atualizacao imediata.

## Nota metodologica

Este projeto comecou como uma investigacao sobre se seria possivel extrair *alpha* (retorno acima do mercado) de dados publicos gratuitos de biotech. Apos testes extensivos e com disciplina anti-sobreajuste (divisao treino/holdout, testes de permutacao, diferenca-em-diferencas), a conclusao honesta foi que **nao existe sinal direcional exploravel em dados publicos** - um resultado consistente com a hipotese de eficiencia de mercado para informacao amplamente acessivel.

O valor do agente nao esta em prever o mercado, mas em **reduzir a incerteza de um analista**: agregar, sintetizar e alertar sobre o que e material, mais depressa e com mais cobertura do que um humano conseguiria manualmente. E uma ferramenta de investigacao com revisao humana, nao um sistema de recomendacao de investimento.

---
*Classificacao automatica a partir de dados publicos. Nao constitui aconselhamento financeiro.*
