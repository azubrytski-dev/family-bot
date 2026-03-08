INSERT INTO news_sources (name, country, category, url, enabled) VALUES
  ('agenda.ge', 'Georgia', 'Georgia', 'https://agenda.ge', TRUE),
  ('civil.ge',  'Georgia', 'Georgia', 'https://civil.ge', TRUE),
  ('onliner.by','Belarus', 'Belarus', 'https://www.onliner.by', TRUE),
  ('Myfin', 'Belarus', 'Belarus', 'https://myfin.by', TRUE),
  ('Banki24', 'Belarus', 'Belarus', 'https://banki24.by', TRUE),
  ('Smartpress', 'Belarus', 'Belarus', 'https://smartpress.by', TRUE),
  ('Telegraf', 'Belarus', 'Belarus', 'https://telegraf.news', TRUE),
  ('Office Life', 'Belarus', 'Belarus', 'https://officelife.media', TRUE),
  ('BelTA', 'Belarus', 'Belarus', 'https://www.belta.by', TRUE),
  ('SB Belarus', 'Belarus', 'Belarus', 'https://www.sb.by', TRUE),
  ('BBC', 'UK',      'World',   'https://www.bbc.com', TRUE),
  ('Reuters',   'Global',  'World',   'https://www.reuters.com', TRUE)
ON CONFLICT DO NOTHING;

