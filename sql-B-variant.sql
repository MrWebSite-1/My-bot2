-- B variant uchun: ikkala Supabase loyihasida (Reze va Miro) ishga tushiring.
-- Mavjud ma'lumotga tegmaydi, takror ishga tushirish xavfsiz.
alter table settings add column if not exists grp_mode text;
alter table settings add column if not exists bot_talk boolean;
alter table settings add column if not exists bot_auto boolean;
alter table settings add column if not exists bot_turns int;
alter table settings add column if not exists bot_delay int;
alter table settings add column if not exists bot_daily int;
alter table settings add column if not exists bot_every int;
