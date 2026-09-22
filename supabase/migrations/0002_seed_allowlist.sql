insert into allowed_actors (email, label)
values ('olaniyigeorge77@gmail.com', 'project owner')
on conflict do nothing;
