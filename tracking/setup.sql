create table if not exists video_pipeline (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    source text,
    link text,
    script text,
    video_url text,
    status text not null default 'sourced',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
