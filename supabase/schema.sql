-- Run this once in the Supabase SQL editor (Project -> SQL Editor -> New query)
-- for a fresh project. Safe to re-run: everything is idempotent.

create extension if not exists vector;
create extension if not exists pgcrypto; -- gen_random_uuid()

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  source_name text not null,
  chunk_count integer not null default 0,
  created_at timestamptz not null default now()
);

-- gemini-embedding-001 outputs 3072-dimensional vectors. If you switch
-- EMBEDDING_MODEL to a model with a different dimension, you must
-- `alter table chunks alter column embedding type vector(<new_dim>)`
-- (and re-embed existing documents) to match.
create table if not exists chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  embedding vector(3072) not null,
  created_at timestamptz not null default now()
);

create index if not exists chunks_document_id_idx on chunks (document_id);

-- No ANN index (ivfflat/hnsw) on `embedding`: pgvector caps those index types
-- at 2000 dimensions, below gemini-embedding-001's 3072. Brute-force cosine
-- search via `<=>` is fine up to tens of thousands of chunks; if you outgrow
-- that, switch to a lower-dimension embedding model and add an hnsw index.
create or replace function match_chunks(query_embedding vector(3072), match_count int)
returns table (
  id uuid,
  document_id uuid,
  chunk_index integer,
  content text,
  source_name text,
  similarity float
)
language sql stable
as $$
  select
    c.id,
    c.document_id,
    c.chunk_index,
    c.content,
    d.source_name,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  join documents d on d.id = c.document_id
  order by c.embedding <=> query_embedding
  limit match_count;
$$;
