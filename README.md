# BIORADAR — Agente de Inteligência Biotech

Agente autónomo que monitoriza o setor biotech dos EUA a partir de **dados exclusivamente públicos e gratuitos**, deteta eventos materiais, e gera memos de analista. Pipeline de IA vertical ponta-a-ponta com infraestrutura de custo zero.

## O que faz

Mantém, para um universo de ~50 biotechs cotadas, um retrato de inteligência sempre atualizado:

- **Calendário de catalisadores** — readouts de ensaios agendados (ClinicalTrials.gov) + decisões da FDA (datas PDUFA extraídas de 8-K)
- **Deteção de eventos materiais** — classifica 8-K (readouts, decisões regulatórias, designações) com sentimento
- **Cash runway** — meses de caixa restantes por empresa (10-Q via SEC EDGAR)
- **Alertas de diluição** — cruza ofertas de ações (424B) com runway curto
- **Atividade de insiders** — compras em mercado aberto (Form 4)
- **Memos de analista** — síntese em linguagem natural por LLM, a partir dos factos extraídos
- **Dashboard** — site estático que apresenta tudo

## Fontes (todas públicas e gratuitas)

| Fonte | Dados |
|---|---|
| SEC EDGAR | 8-K, Form 4, 10-Q, 424B |
| ClinicalTrials.gov v2 | ensaios, estados, datas de conclusão |
| yfinance | preço, market cap |
| Groq (LLM gratuito) | geração dos memos |

## Arquitetura

```text
agent/
├── config.py         # universo + identificação
├── db/
│   └── database.py   # schema SQLite (estado do agente)
├── ingest/           # 6 ingestores incrementais (um por fonte)
│   ├── ingest_8k.py
│   ├── ingest_trials.py
│   ├── ingest_prices.py
│   ├── ingest_fundamentals.py
│   ├── ingest_insiders.py
│   └── ingest_dilution.py
├── detect/
│   └── detect_8k.py  # deteção de eventos a partir de texto
└── report/           # calendário, one-pagers, memos, site
    ├── calendar.py
    ├── onepager.py
    ├── memo.py
    └── site.py
run.py                # ponto de entrada: python run.py <comando>
```

O agente é **stateful e incremental**: cada corrida só processa o que é novo desde a última (guardado em SQLite). Desenhado para correr em contínuo via GitHub Actions.

## Uso

```bash
python run.py init         # inicializa BD + resolve universo
python run.py update       # atualiza todas as fontes (incremental)
python run.py calendar     # mostra o calendário de catalisadores
python run.py profile MDGL # perfil de uma empresa
python run.py memos groq   # gera memos com LLM
python run.py site         # gera o dashboard
```

A chave da API do LLM vive num ficheiro `.env` local (nunca versionado).

## Nota metodológica

Este projeto começou como uma investigação sobre se seria possível extrair *alpha* (retorno acima do mercado) de dados públicos gratuitos de biotech. Após testes extensivos e com disciplina anti-sobreajuste (divisão treino/holdout, testes de permutação, diferença-em-diferenças), a conclusão honesta foi que **não existe sinal direcional explorável em dados públicos** — um resultado consistente com a hipótese de eficiência de mercado para informação amplamente acessível.

O valor do agente não está em prever o mercado, mas em **reduzir a incerteza de um analista**: agregar, sintetizar e alertar sobre o que é material, mais depressa e com mais cobertura do que um humano conseguiria manualmente. É uma ferramenta de investigação com revisão humana, não um sistema de recomendação de investimento.

---
*Classificação automática a partir de dados públicos. Não constitui aconselhamento financeiro.*
