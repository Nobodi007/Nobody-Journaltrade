-- ตารางโน้ตประกอบไม้ สำหรับหน้า Journal
-- รันใน Supabase → SQL Editor ครั้งเดียว

create table if not exists public.trade_notes (
  trade_id       text not null,          -- = MT5 position_id
  account_id     text not null,          -- = MT5 login
  setup          text default '',
  timeframe      text default '',
  confidence     integer default 3,
  emotion_in     text default '',
  emotion_out    text default '',
  followed_plan  integer default 1,
  mistakes       text default '[]',
  thesis         text default '',
  lesson         text default '',
  tags           text default '',
  screenshot_url text default '',
  updated_at     timestamptz default now(),
  primary key (trade_id, account_id)
);

alter table public.trade_notes enable row level security;

-- แอปอ่าน/เขียนด้วย publishable (anon) key
-- หมายเหตุ: ใครมี key นี้ก็แก้โน้ตได้ ใช้กับสมุดบันทึกส่วนตัวเท่านั้น
create policy "notes read"   on public.trade_notes for select to anon using (true);
create policy "notes insert" on public.trade_notes for insert to anon with check (true);
create policy "notes update" on public.trade_notes for update to anon using (true) with check (true);
