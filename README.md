# Copa Predictor 2026

Aplicação full-stack para prever resultados da Copa do Mundo de 2026 com **dois
modelos paralelos**, uma **API FastAPI** e uma **interface web em Next.js**.

- **Modelo A — Histórico** 📚: usa a "ficha" de cada seleção — ranking de força
  (Elo), forma recente (gols feitos/sofridos nos últimos jogos), histórico de
  confrontos diretos (H2H) e descanso. Funciona desde o 1º jogo. *(= reputação)*
- **Modelo B — Só esta Copa** 🔥: ignora o passado e usa **apenas** os resultados
  da própria Copa 2026, com atualização Bayesiana sobre um *prior* derivado do Elo
  pré-torneio. Começa quase só com o ranking e fica mais preciso a cada rodada.
  *(= fase atual no torneio)*

Ambos devolvem: gols esperados de cada lado, distribuição de placares (matriz
0–7 × 0–7), probabilidades de vitória/empate/derrota e o placar mais provável.

> A Copa é em **campo neutro**: os modelos não aplicam vantagem de mando. O Modelo A
> é simetrizado (inverter a ordem dos times espelha o resultado exatamente).

---

## Arquitetura

```
┌──────────────────┐     HTTP/JSON      ┌─────────────────────┐
│  web/ (Next.js)  │ ─────────────────▶ │  src/api.py (FastAPI)│
│  React + Tailwind│                    │  + agendador horário │
└──────────────────┘                    └──────────┬──────────┘
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              ▼                     ▼                     ▼
                        copa.db (SQLite)     modelos (A/B)        football-data.org
                                                                  + API-Football
```

```
src/
├── api.py            # API FastAPI (endpoints + auto-refresh + monitoramento)
├── api_football.py   # Cliente API-Football (histórico)
├── football_data.py  # Cliente football-data.org (fixtures/resultados da Copa)
├── elo_loader.py     # Carrega o CSV de Elo
├── ingest.py         # ETL: APIs → SQLite (+ refresh dos resultados)
├── features.py       # Feature engineering (Modelo A e estado do Modelo B)
├── models.py         # Poisson GLM (A) + Bayesian Gamma-Poisson (B)
├── monitor.py        # Backtest, log diário de métricas, gatilho de recalibração
├── teams.py          # Resolução de nomes/códigos de seleção
└── predict.py        # CLI de predição
web/                  # Front-end Next.js (App Router, shadcn/ui, recharts)
schema.sql            # Schema do SQLite
backtest.py           # Backtest jogo a jogo (sem vazamento) na linha de comando
```

---

## Setup

### 1. Backend (Python 3.10+)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # preencha as chaves (veja abaixo)
sqlite3 copa.db < schema.sql  # cria o banco
```

**Chaves (`.env`):**
- `API_FOOTBALL_KEY` — conta grátis em [dashboard.api-football.com](https://dashboard.api-football.com) (100 req/dia), para o histórico.
- `FOOTBALL_DATA_TOKEN` — conta grátis em [football-data.org](https://www.football-data.org), para fixtures/resultados da Copa.

**CSV de Elo:** baixe o dataset [2026 FIFA World Cup Historical Elo Ratings](https://www.kaggle.com/datasets/afonsofernandescruz/2026-fifa-world-cup-historical-elo-ratings) e salve como `elo_ratings_wc2026.csv`.

**Popular o banco:**
```bash
python -m src.ingest world-cup-football-data   # times + fixtures + resultados da Copa
python -m src.ingest history --years 5          # histórico de cada seleção
python -m src.ingest elo --csv elo_ratings_wc2026.csv
python -m src.models train-historical           # treina o Modelo A
```

**Subir a API:**
```bash
uvicorn src.api:app --port 8010
```
Ao subir, a API faz um refresh dos resultados e grava um snapshot de métricas; depois repete de hora em hora (configurável em `REFRESH_INTERVAL_SECONDS`).

### 2. Frontend (Node 20+)

```bash
cd web
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8010" > .env.local
npm run dev        # http://localhost:3000
```
> Se a porta 3000 estiver ocupada, use `npm run dev -- -p 3100` e ajuste a URL no navegador.
> O `NEXT_PUBLIC_API_URL` aponta o front para a API.

---

## A interface (e os botões)

| Página | O que mostra |
|---|---|
| **Início** (`/`) | Próximos jogos, resultados recentes e prévia da classificação |
| **Previsão** (`/predict`) | Escolha duas seleções e clique em **Prever** — mostra os **dois modelos lado a lado** com gols esperados, barra de probabilidades W/D/L, matriz de placares e os **dados usados** na conta |
| **Jogos** (`/fixtures`) | Todos os jogos, filtráveis por status/grupo; cada um abre a previsão |
| **Grupos** (`/groups`) | Classificação dos grupos calculada dos jogos encerrados |
| **Time** (`/teams/[id]`) | Elo, forma, desempenho no torneio e jogos da seleção |
| **Monitor** (`/monitor`) | Desempenho dos modelos nos jogos já disputados + gatilho de recalibração |

### Botões
- **Atualizar** (barra superior, em todas as páginas) — chama `POST /api/refresh`,
  re-puxa os resultados do football-data.org e atualiza a página. Útil logo
  após um jogo terminar (o auto-refresh horário já faz isso sozinho; o botão força na hora).
- **Rodar agora** (página Monitor) — chama `POST /api/monitor/run`, roda o backtest
  sobre os jogos encerrados e grava um snapshot de métricas do dia.
- **Tema** (ícone sol/lua) — alterna claro/escuro.

---

## Como os modelos funcionam

### Modelo A — Histórico (Poisson GLM)
Treina em jogos internacionais desde 2020 (~800 partidas). Duas regressões de
Poisson (gols do mandante e do visitante) sobre as features:
`elo_diff`, forma ofensiva/defensiva (últimos 10), `h2h`, descanso.
A matriz de placares é o produto das duas distribuições de Poisson.
Como a Copa é neutra, a previsão é **simetrizada** (média das duas ordens).

### Modelo B — Só Copa 2026 (Bayesian Gamma-Poisson)
Cada seleção tem ataque/defesa estimados:
```
prior:      derivado do Elo pré-Copa, em torno de 1,35 gol/time
posterior:  (prior + gols na Copa) / (3 + nº de jogos na Copa)
```
No início o posterior ≈ prior (quase só Elo). Após ~3 jogos, os dados do torneio
dominam. Os gols esperados combinam ataque de um × defesa do outro.

### Sobre empates e calibração (decisões honestas)
- A matriz tem infraestrutura de correção **Dixon-Coles** (`rho`) e de **inflação de
  empate** (`draw_boost`), ambas **desligadas** (`rho=0`, `draw_boost=1.0`).
- Motivo: calibração out-of-sample em ~800 jogos reais mostrou que o **Poisson
  independente já acerta a taxa de empate** (~21% previsto vs ~21% real) e qualquer
  inflação **piora** as métricas. Os ~40% de empate nos primeiros jogos da Copa
  são ruído de amostra pequena — calibrar nisso seria overfitting.
- O `argmax` (escolher o resultado mais provável) raramente aponta "empate", mesmo
  com a probabilidade calibrada, porque empate é uma diagonal fina disputando
  contra dois triângulos inteiros de placares de vitória. Por isso as **métricas de
  probabilidade (RPS, Brier, log-loss)** avaliam melhor que o acerto do `argmax`.

---

## Monitoramento e gatilho de recalibração

A página **Monitor** roda um **backtest sem vazamento** (Modelo A retreinado
*excluindo* os jogos da Copa) sobre todas as partidas encerradas e registra um
**snapshot por dia** em `metrics_log.csv`: acerto 1X2, placar exato, Brier, RPS,
log-loss, taxa de empate (real e prevista), nº de jogos.

O **gatilho de recalibração** (banner verde/amarelo/vermelho) só sugere mexer na
matemática quando **dois critérios** valem juntos — e a decisão é **humana**:
1. **amostra suficiente** (`≥ 72` jogos, ~fim da fase de grupos);
2. **desvio de empate significativo e persistente** (`|z| ≥ 2` por ≥ 5 snapshots).

Isso evita o erro de re-calibrar a cada ruído de poucos jogos.

```bash
python backtest.py        # backtest jogo a jogo no terminal
python -m src.monitor     # grava o snapshot do dia e imprime o status do gatilho
```

---

## API (principais endpoints)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/teams` | Seleções da Copa 2026 |
| `GET` | `/api/fixtures` | Jogos (filtros: `status`, `group`, `matchday`) |
| `GET` | `/api/standings` | Classificação dos grupos |
| `GET` | `/api/teams/{id}` | Detalhe de uma seleção |
| `GET` | `/api/predict` | Previsão (`home`/`away` ou `fixture_id`; `historical=true` inclui o Modelo A) |
| `GET` / `POST` | `/api/refresh` | Status / dispara o refresh dos resultados |
| `GET` / `POST` | `/api/monitor/history` · `/api/monitor/run` | Histórico de métricas / roda o backtest |

---

## CLI de predição

```bash
python -m src.predict --home Brasil --away Argentina
```

## Stack

| Camada | Tecnologias |
|---|---|
| Modelos/ETL | Python, statsmodels, SQLite |
| API | FastAPI, Uvicorn |
| Front-end | Next.js (App Router), React, Tailwind, shadcn/ui, recharts |
| Dados | football-data.org, API-Football, Elo (Kaggle) |

## Próximos passos
- [ ] Backtest sobre Catar 2022 e Rússia 2018 (exige fonte de dados que libere temporadas antigas)
- [ ] Feature de xG sintético no Modelo A
- [ ] Reavaliar Dixon-Coles/empate quando houver amostra grande e persistente (o gatilho avisa)
