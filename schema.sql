-- Reze bot bazasi (Supabase). Kod asosida tuzilgan.
-- Yangi bazada hammasini ishga tushiring. Mavjud bazada ham xavfsiz:
-- "if not exists" tufayli bor narsaga tegmaydi.

create table if not exists messages (
  id bigint generated always as identity primary key,
  chat_id bigint not null,
  role text not null,
  content text not null,
  created_at timestamptz default now()
);
create table if not exists facts (
  id bigint generated always as identity primary key,
  chat_id bigint not null,
  fact text not null,
  created_at timestamptz default now()
);
create table if not exists reminders (
  id bigint generated always as identity primary key,
  chat_id bigint not null,
  task text not null,
  remind_at timestamptz not null,
  done boolean default false
);
create table if not exists settings (
  chat_id bigint primary key,
  proactive boolean default true,
  last_slot text
);

-- keyinroq qo'shilgan ustunlar
alter table facts     add column if not exists expires_at timestamptz;
alter table reminders add column if not exists repeat text;
alter table settings  add column if not exists summary text;
alter table settings  add column if not exists style text;
alter table settings  add column if not exists voice text;
alter table settings  add column if not exists rate text;
alter table settings  add column if not exists vmode text;
alter table settings  add column if not exists engine text;
alter table settings  add column if not exists gvoice text;
alter table settings  add column if not exists sticker_set text;
alter table settings  add column if not exists stickers boolean;

alter table messages  enable row level security;
alter table facts     enable row level security;
alter table reminders enable row level security;
alter table settings  enable row level security;

-- Yozish sozlamalari (buyruqlar orqali boshqariladi)
alter table settings add column if not exists pro_min int;
alter table settings add column if not exists pro_max int;
alter table settings add column if not exists pro_gap int;
alter table settings add column if not exists pro_from int;
alter table settings add column if not exists pro_to int;
alter table settings add column if not exists jimlik_h int;

-- Yangi Supabase loyihalarda service_role ga ruxsat kerak bo'ladi
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
