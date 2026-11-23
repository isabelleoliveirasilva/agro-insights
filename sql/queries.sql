-- =============================================================================
-- Agro Insights: consultas analíticas
--
-- Como executar (a partir da raiz do projeto, depois de rodar o ETL):
--   sqlite3 -header -column data/processed/agro.db < sql/queries.sql
--
-- Observação: produtos e vendas são fictícios. Produção (IBGE) e clima
-- (Open-Meteo) são dados públicos reais.
-- =============================================================================


-- =============================================================================
-- Consulta 1: Top 10 produtos por receita
-- Pergunta: quais produtos mais faturam e quanto cada um pesa no total?
-- Técnicas: JOIN, GROUP BY e função de janela sobre agregado (SUM(SUM(...)) OVER ())
-- Como ler: participacao_pct é a fatia do produto na receita de TODOS os produtos,
--           mesmo que o resultado mostre só os 10 primeiros.
-- =============================================================================
SELECT
    p.nome,
    p.categoria,
    p.cultura_alvo,
    SUM(v.quantidade)                                                  AS unidades,
    ROUND(SUM(v.valor_total), 2)                                       AS receita,
    ROUND(100.0 * SUM(v.valor_total) / SUM(SUM(v.valor_total)) OVER (), 2) AS participacao_pct
FROM vendas v
JOIN produtos p ON p.id = v.produto_id
GROUP BY p.id, p.nome, p.categoria, p.cultura_alvo
ORDER BY receita DESC, p.nome
LIMIT 10;


-- =============================================================================
-- Consulta 2: Vendas por região e mês
-- Pergunta: como a receita se distribui entre as regiões ao longo do tempo?
-- Técnicas: JOIN com a tabela de estados, GROUP BY, strftime e RANK() sobre agregado
-- Como ler: posicao_no_mes = 1 indica a região que mais vendeu naquele mês.
-- =============================================================================
SELECT
    strftime('%Y-%m', v.data_venda)                                    AS mes,
    e.regiao,
    COUNT(*)                                                           AS vendas,
    SUM(v.quantidade)                                                  AS unidades,
    ROUND(SUM(v.valor_total), 2)                                       AS receita,
    RANK() OVER (
        PARTITION BY strftime('%Y-%m', v.data_venda)
        ORDER BY SUM(v.valor_total) DESC
    )                                                                  AS posicao_no_mes
FROM vendas v
JOIN estados e ON e.uf = v.uf
GROUP BY mes, e.regiao
ORDER BY mes, receita DESC;


-- =============================================================================
-- Consulta 3: Maiores produtores por cultura no último ano
-- Pergunta: quais são os 3 estados que mais produzem cada cultura?
-- Técnicas: CTE, JOIN, RANK() com PARTITION BY, NULLIF para evitar divisão por zero
-- Como ler: produtividade_t_ha = toneladas por hectare colhido. Estados sem dado
--           (nulo) ou sem produção (zero) ficam de fora do ranking.
-- =============================================================================
WITH ultimo AS (
    SELECT MAX(ano) AS ano FROM producao
),
ranking AS (
    SELECT
        u.ano,
        p.cultura,
        p.uf,
        e.regiao,
        p.quantidade_t,
        p.area_colhida_ha,
        ROUND(p.quantidade_t / NULLIF(p.area_colhida_ha, 0), 2)        AS produtividade_t_ha,
        RANK() OVER (PARTITION BY p.cultura ORDER BY p.quantidade_t DESC) AS posicao
    FROM producao p
    JOIN ultimo u ON p.ano = u.ano
    JOIN estados e ON e.uf = p.uf
    WHERE p.quantidade_t IS NOT NULL
      AND p.quantidade_t > 0
)
SELECT *
FROM ranking
WHERE posicao <= 3
ORDER BY cultura, posicao;


-- =============================================================================
-- Consulta 4: Crescimento anual da produção nacional por cultura
-- Pergunta: a produção de cada cultura está crescendo ou caindo ano a ano?
-- Técnicas: CTE, GROUP BY, LAG() com janela nomeada (WINDOW)
-- Como ler: variacao_pct compara com o ano anterior (o primeiro ano fica nulo).
--           Cuidado: se ufs_com_dado mudar de um ano para outro, a variação pode
--           refletir dados faltando e não uma mudança real na produção.
-- =============================================================================
WITH nacional AS (
    SELECT
        cultura,
        ano,
        SUM(quantidade_t)    AS quantidade_t,
        COUNT(quantidade_t)  AS ufs_com_dado
    FROM producao
    GROUP BY cultura, ano
)
SELECT
    cultura,
    ano,
    quantidade_t,
    ufs_com_dado,
    LAG(quantidade_t) OVER w                                           AS ano_anterior,
    ROUND(
        100.0 * (quantidade_t - LAG(quantidade_t) OVER w)
        / NULLIF(LAG(quantidade_t) OVER w, 0),
        2
    )                                                                  AS variacao_pct
FROM nacional
WINDOW w AS (PARTITION BY cultura ORDER BY ano)
ORDER BY cultura, ano;


-- =============================================================================
-- Consulta 5: Vendas em meses chuvosos x meses secos, por estado
-- Pergunta: a receita muda quando chove mais do que o normal no estado?
-- Técnicas: duas CTEs agregadas por mês, JOIN entre vendas e clima, AVG() OVER,
--           CASE para classificar cada mês
-- Como ler: mês chuvoso = chuva acima da média mensal daquele estado, considerando
--           só os meses em que há vendas e clima. O clima cobre apenas os estados
--           com cidade de referência. Como as vendas são fictícias, o objetivo
--           aqui é demonstrar a técnica e não tirar conclusões agronômicas.
-- =============================================================================
WITH chuva_mensal AS (
    SELECT
        uf,
        strftime('%Y-%m', data_leitura) AS mes,
        SUM(precipitacao_mm)            AS chuva_mm
    FROM clima
    GROUP BY uf, mes
),
receita_mensal AS (
    SELECT
        uf,
        strftime('%Y-%m', data_venda)   AS mes,
        SUM(valor_total)                AS receita
    FROM vendas
    GROUP BY uf, mes
),
base AS (
    SELECT
        c.uf,
        c.mes,
        c.chuva_mm,
        r.receita,
        AVG(c.chuva_mm) OVER (PARTITION BY c.uf) AS chuva_media_uf
    FROM chuva_mensal c
    JOIN receita_mensal r ON r.uf = c.uf AND r.mes = c.mes
    WHERE c.chuva_mm IS NOT NULL
)
SELECT
    uf,
    CASE WHEN chuva_mm > chuva_media_uf THEN 'chuvoso' ELSE 'seco' END AS tipo_mes,
    COUNT(*)                                                           AS meses,
    ROUND(AVG(chuva_mm), 1)                                            AS chuva_media_mm,
    ROUND(AVG(receita), 2)                                             AS receita_media
FROM base
GROUP BY uf, tipo_mes
ORDER BY uf, tipo_mes;
