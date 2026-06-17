# Copa Predictor 2026

Aplicação para sugerir resultados da Copa do Mundo 2026 com **dois modelos paralelos**:

- **Modelo A — Histórico**: usa todos os dados disponíveis de cada seleção (Elo, forma últimos N jogos, H2H, descanso)
- **Modelo B — Tournament-only**: usa apenas resultados durante a própria Copa 2026, com Bayesian shrinkage para um prior derivado do Elo pré-torneio

Ambos os modelos retornam:
- Placar esperado (gols esperados de cada time)
- Distribuição de placares (probabilidade de cada combinação 0-6 × 0-6)
- Probabilidades W/D/L
- Resultado mais provável

## Stack de dados

| Fonte | Uso | Custo |
|---|---|---|
| API-Football (api-sports.io) | Fixtures, eventos, stats, escalações, H2H | Free 100 req/dia |
| openfootball/worldcup.json | Schedule estático + fallback | Grátis (GitHub) |
| Elo Ratings (eloratings.net via Kaggle) | Feature preditiva mais forte | Grátis (CC BY-SA 4.0) |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # adicionar API_FOOTBALL_KEY
sqlite3 copa.db < schema.sql
```

## Obtendo a chave da API

1. Acesse [dashboard.api-football.com](https://dashboard.api-football.com)
2. Crie uma conta gratuita (100 req/dia)
3. Copie a chave e cole no `.env`

## Obtendo o CSV de Elo

1. Acesse o dataset no Kaggle: [2026 FIFA World Cup Historical Elo Ratings](https://www.kaggle.com/datasets/afonsofernandescruz/2026-fifa-world-cup-historical-elo-ratings)
2. Baixe o CSV e salve como `elo_ratings_wc2026.csv`

## Uso

```bash
# 1. Cria o banco de dados
sqlite3 copa.db < schema.sql

# 2. Ingere os times e fixtures da Copa 2026
python -m src.ingest world-cup

# 3. Ingere histórico dos últimos 5 anos de cada seleção
python -m src.ingest history --years 5

# 4. Ingere Elo ratings
python -m src.ingest elo --csv elo_ratings_wc2026.csv

# 5. Treina o Modelo A (Histórico)
python -m src.models train-historical

# 6. Inspeciona estado do torneio (Modelo B)
python -m src.models inspect-tournament

# 7. Prediz um jogo com ambos os modelos
python -m src.predict --home Brasil --away Argentina
```

### Exemplo de output

```
───────────── Brasil × Argentina  (2026-06-26) ─────────────

         Modelo A — Histórico
  ┌────────────────────────────┬──────────────────┐
  │ Gols esperados (casa)      │ 1.84             │
  │ Gols esperados (visit.)    │ 1.12             │
  │ Placar mais provável       │ 2 × 1  (8.4%)   │
  │ P(vitória casa)            │ 52.1%            │
  │ P(empate)                  │ 24.3%            │
  │ P(vitória visit.)          │ 23.6%            │
  └────────────────────────────┴──────────────────┘

         Modelo B — Apenas Copa 2026
  ┌────────────────────────────┬──────────────────────────────────┐
  │ Gols esperados (casa)      │ 1.66                             │
  │ Gols esperados (visit.)    │ 1.31                             │
  │ Placar mais provável       │ 1 × 1  (9.1%)                   │
  │ P(vitória casa)            │ 44.8%                            │
  │ P(empate)                  │ 26.1%                            │
  │ P(vitória visit.)          │ 29.1%                            │
  │ Notas                      │ baseado em 3 jogos do BRA e 3... │
  └────────────────────────────┴──────────────────────────────────┘
```

## Estrutura

```
src/
├── api_football.py   # Cliente da API com cache em SQLite
├── elo_loader.py     # Carrega CSV de Elo ratings
├── ingest.py         # ETL: API → SQLite
├── features.py       # Feature engineering (Modelo A e B)
├── models.py         # Poisson GLM + Bayesian Gamma-Poisson
└── predict.py        # CLI de predição
schema.sql            # Schema do banco SQLite
requirements.txt      # Dependências Python
```

## Como os modelos funcionam

**Modelo A** treina em jogos internacionais 2020-2025 (~3000 partidas). Usa Poisson regression bivariada:
```
log(λ_home) = β₀ + β₁·elo_diff + β₂·form_home + β₃·form_away + β₄·h2h + β₅·rest
log(λ_away) = β₀' + ...
```
Depois aplica produto cartesiano de Poisson para gerar matriz de placares 8×8.

**Modelo B** mantém para cada time uma estimativa Bayesiana de força ofensiva/defensiva:
```
prior:  α ~ Gamma(k₀, θ₀)  derivado do Elo pré-Copa
likelihood: goals | α ~ Poisson(α)
posterior: Gamma(k₀ + Σgoals, θ₀ + n)
```
No início da Copa o posterior fica próximo do prior. Conforme a Copa avança, os dados do torneio dominam.

## Próximos passos

- [ ] Correção Dixon-Coles τ(x,y) para calibração em placares baixos
- [ ] Decay exponencial por recência no Modelo A
- [ ] Feature de xG sintético (shots × conversion rate)
- [ ] Endpoint REST com FastAPI
- [ ] Backtesting em Catar 2022 e Rússia 2018
