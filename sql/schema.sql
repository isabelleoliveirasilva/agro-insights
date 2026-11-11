-- Schema do Agro Insights (SQLite)
-- Datas em formato ISO-8601 (YYYY-MM-DD).
-- Lembrete: ative `PRAGMA foreign_keys = ON;` em cada conexão (ver load.py).

create table if not exists estados (
    uf     text primary key check (length(uf) = 2),
    nome   text not null,
    regiao text not null
);

create table if not exists produtos (
    id           integer primary key,
    nome         text not null,
    categoria    text not null,
    cultura_alvo text not null,
    preco        real not null check (preco >= 0)
);

create table if not exists vendas (
    id          integer primary key,
    data_venda  date    not null,
    produto_id  integer not null references produtos(id),
    uf          text    not null references estados(uf),
    quantidade  integer not null check (quantidade > 0),
    valor_total real    not null check (valor_total >= 0)
);

-- Medidas podem ser nulas: o IBGE usa "-", "..." e "X" para dado ausente.
create table if not exists producao (
    ano             integer not null,
    uf              text    not null references estados(uf),
    cultura         text    not null,
    area_colhida_ha real,
    quantidade_t    real,
    valor_mil_reais real,
    primary key (ano, uf, cultura)
);

create table if not exists clima (
    data_leitura      date not null,
    uf                text not null references estados(uf),
    temperatura_media real,
    precipitacao_mm   real,
    primary key (data_leitura, uf)
);

-- Índices para as consultas analíticas
create index if not exists idx_vendas_produto on vendas(produto_id);
create index if not exists idx_vendas_uf      on vendas(uf);
create index if not exists idx_vendas_data    on vendas(data_venda);
create index if not exists idx_producao_uf    on producao(uf);

-- Dados de referência: 27 unidades da federação
insert or ignore into estados (uf, nome, regiao) values
    ('AC', 'Acre', 'Norte'),
    ('AP', 'Amapá', 'Norte'),
    ('AM', 'Amazonas', 'Norte'),
    ('PA', 'Pará', 'Norte'),
    ('RO', 'Rondônia', 'Norte'),
    ('RR', 'Roraima', 'Norte'),
    ('TO', 'Tocantins', 'Norte'),
    ('AL', 'Alagoas', 'Nordeste'),
    ('BA', 'Bahia', 'Nordeste'),
    ('CE', 'Ceará', 'Nordeste'),
    ('MA', 'Maranhão', 'Nordeste'),
    ('PB', 'Paraíba', 'Nordeste'),
    ('PE', 'Pernambuco', 'Nordeste'),
    ('PI', 'Piauí', 'Nordeste'),
    ('RN', 'Rio Grande do Norte', 'Nordeste'),
    ('SE', 'Sergipe', 'Nordeste'),
    ('DF', 'Distrito Federal', 'Centro-Oeste'),
    ('GO', 'Goiás', 'Centro-Oeste'),
    ('MT', 'Mato Grosso', 'Centro-Oeste'),
    ('MS', 'Mato Grosso do Sul', 'Centro-Oeste'),
    ('ES', 'Espírito Santo', 'Sudeste'),
    ('MG', 'Minas Gerais', 'Sudeste'),
    ('RJ', 'Rio de Janeiro', 'Sudeste'),
    ('SP', 'São Paulo', 'Sudeste'),
    ('PR', 'Paraná', 'Sul'),
    ('RS', 'Rio Grande do Sul', 'Sul'),
    ('SC', 'Santa Catarina', 'Sul');
