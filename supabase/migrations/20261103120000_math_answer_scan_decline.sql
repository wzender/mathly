-- A photo request can be declined: the phone refuses it, or the computer withdraws it while waiting.
-- Additive: one more scan state and one more action; existing rows and actions are unchanged.
begin;
alter table public.math_answer_scans drop constraint math_answer_scans_state_check;
alter table public.math_answer_scans add constraint math_answer_scans_state_check
  check (state in ('waiting','confirmed','uploading','received','failed','expired','superseded','declined'));
create or replace function public.math_answer_action(p_user uuid, p_action text, p_data jsonb default '{}')
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  a public.math_question_attempts;
  s public.math_answer_scans;
  att public.math_answer_attachments;
  t timestamptz := clock_timestamp();
  sid uuid;
  aid uuid;
  listing jsonb;
begin
  if p_action='cleanup_candidates' then
    return coalesce((select jsonb_agg(o.name) from storage.objects o
      where o.bucket_id='mathly-answers' and o.created_at < t-interval '24 hours'
      and not exists(select 1 from public.math_answer_attachments x where x.object_key=o.name)), '[]'::jsonb);
  end if;
  if p_user is null then raise exception 'not_found' using errcode='P0002'; end if;
  if p_action='pending' then
    -- Expiry and stale lease recovery are also persisted on discovery.
    update public.math_answer_scans set state='expired',error='expired'
      where user_id=p_user and expires_at<=t and state in ('waiting','confirmed','uploading','failed');
    update public.math_answer_scans set state='failed',error='upload_interrupted'
      where user_id=p_user and state='uploading' and lease_until<=t;
    select jsonb_agg(jsonb_build_object('scan',to_jsonb(x),'attempt',to_jsonb(q)) order by x.created_at desc)
      into listing from public.math_answer_scans x join public.math_question_attempts q on q.id=x.attempt_id
      where x.user_id=p_user and x.state in ('waiting','confirmed','uploading','failed','expired')
      and not exists(select 1 from public.math_answer_scans newer where newer.attempt_id=x.attempt_id and newer.generation>x.generation);
    return coalesce(listing,'[]'::jsonb);
  end if;
  if p_action='resume' then
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_user::text||(p_data->>'question_id')||(p_data->>'question_version'),0));
    if not coalesce((p_data->>'new')::boolean,false) then
      select * into a from public.math_question_attempts where user_id=p_user
        and question_id=p_data->>'question_id' and question_version=p_data->>'question_version'
        order by created_at desc,id desc limit 1 for update;
    end if;
    if a.id is null then
      insert into public.math_question_attempts(user_id,question_id,question_version,snapshot)
        values(p_user,p_data->>'question_id',p_data->>'question_version',p_data->'snapshot') returning * into a;
    end if;
  else
    if p_data ? 'scan_id' then
      select attempt_id into aid from public.math_answer_scans where id=(p_data->>'scan_id')::uuid and user_id=p_user;
    else aid := (p_data->>'attempt_id')::uuid;
    end if;
    select * into a from public.math_question_attempts where id=aid and user_id=p_user for update;
    if a.id is null then raise exception 'not_found' using errcode='P0002'; end if;
    if p_data ? 'question_id' and a.question_id<>p_data->>'question_id' then
      raise exception 'not_found' using errcode='P0002';
    end if;
  end if;
  select * into s from public.math_answer_scans where attempt_id=a.id order by generation desc limit 1 for update;
  select * into att from public.math_answer_attachments where attempt_id=a.id;
  t := clock_timestamp();
  if p_data ? 'scan_id' and s.id is distinct from (p_data->>'scan_id')::uuid then
    raise exception 'superseded' using errcode='P0001';
  end if;
  if s.id is not null then
    if s.state in ('waiting','confirmed','uploading','failed') and s.expires_at<=t then
      update public.math_answer_scans set state='expired',error='expired' where id=s.id returning * into s;
    elsif s.state='uploading' and s.lease_until<=t then
      update public.math_answer_scans set state='failed',error='upload_interrupted' where id=s.id returning * into s;
    end if;
  end if;
  if p_action='create_scan' then
    if att.id is not null then null;
    elsif s.id is null or coalesce((p_data->>'renew')::boolean,false) then
      if s.state='uploading' then raise exception 'upload_in_progress' using errcode='P0001'; end if;
      if s.id is not null then update public.math_answer_scans set state='superseded' where id=s.id; end if;
      insert into public.math_answer_scans(user_id,attempt_id,generation,expires_at,created_at)
        values(p_user,a.id,coalesce(s.generation,0)+1,t+interval '15 minutes',t) returning * into s;
    end if;
  elsif p_action='confirm' then
    if s.state='waiting' then
      update public.math_answer_scans set state='confirmed' where id=s.id returning * into s;
    end if;
  elsif p_action='begin' then
    if s.state in ('confirmed','failed') then
      update public.math_answer_scans set state='uploading',lease_id=gen_random_uuid(),
        lease_until=least(t+interval '3 minutes',expires_at),idempotency_key=(p_data->>'key')::uuid,error=''
        where id=s.id returning * into s;
    elsif s.state='uploading' and s.idempotency_key is distinct from (p_data->>'key')::uuid then
      raise exception 'upload_in_progress' using errcode='P0001';
    elsif s.state='waiting' then raise exception 'confirmation_required' using errcode='P0001';
    end if;
  elsif p_action='finalize' then
    if att.id is null then
      if s.state<>'uploading' or s.lease_id is distinct from (p_data->>'lease_id')::uuid then
        raise exception 'invalid_upload' using errcode='P0001';
      end if;
      if (p_data->>'object_key') not like p_user::text||'/'||s.id::text||'/'||s.lease_id::text||'/%' then
        raise exception 'invalid_upload' using errcode='P0001';
      end if;
      insert into public.math_answer_attachments(user_id,attempt_id,scan_id,object_key,media_type,byte_size)
        values(p_user,a.id,s.id,p_data->>'object_key','image/jpeg',(p_data->>'byte_size')::integer) returning * into att;
      update public.math_answer_scans set state='received',error='' where id=s.id returning * into s;
      update public.math_question_attempts set status='received' where id=a.id returning * into a;
    end if;
  elsif p_action='decline' then
    -- the phone refused the request, or the computer withdrew it; a received answer stays received
    if att.id is null and s.state in ('waiting','confirmed','failed') then
      update public.math_answer_scans set state='declined',error='declined' where id=s.id returning * into s;
    end if;
  elsif p_action='fail' then
    if s.state='uploading' and s.lease_id=(p_data->>'lease_id')::uuid then
      update public.math_answer_scans set state='failed',error='upload_failed' where id=s.id returning * into s;
    end if;
  elsif p_action not in ('resume','get') then
    raise exception 'invalid_action';
  end if;
  return jsonb_build_object('attempt',to_jsonb(a),'scan',case when s.id is null then null else to_jsonb(s) end,
    'attachment',case when att.id is null then null else to_jsonb(att) end);
end $$;
revoke all on function public.math_answer_action(uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.math_answer_action(uuid,text,jsonb) to service_role;
commit;
