-- ─── Central Intelligence Seed Data ──────────────────────────────────────────
-- Run AFTER all migrations. Populates tables with realistic data so the UI
-- has content to display immediately.
-- ─────────────────────────────────────────────────────────────────────────────

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. USERS & TEAMS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO users (id, email, name, role) VALUES
  ('00000000-0000-4000-8000-000000000001', 'jade@centralintelligence.ai',    'Jade Doe',       'admin'),
  ('00000000-0000-4000-8000-000000000002', 'marcus@centralintelligence.ai',  'Marcus Chen',    'coach'),
  ('00000000-0000-4000-8000-000000000003', 'elena@centralintelligence.ai',   'Elena Vasquez',  'coach'),
  ('00000000-0000-4000-8000-000000000004', 'sam@centralintelligence.ai',     'Sam Okafor',     'agent');

INSERT INTO teams (name, description) VALUES
  ('Sales',       'Outbound sales and lead qualification'),
  ('Fulfillment', 'Client coaching and retention'),
  ('Marketing',   'Content creation and campaign management');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 2. BUSINESS PROFILE & OFFERS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO business_profile (business_name, mission, target_audience, brand_voice, core_values, key_differentiators, primary_market, notes) VALUES
  ('Central Intelligence',
   'Help online business owners scale past $50k/month with AI-powered marketing intelligence.',
   'Online coaches, consultants, and course creators doing $10k-$100k/month who want to scale without burning out.',
   'Direct, empathetic, data-driven. Speak to the entrepreneur behind the business — not just the business.',
   'Transparency, Speed, Client Obsession, Data Over Opinions',
   'AI-extracted Voice of Customer data from real sales calls, not surveys or guesswork.',
   'Online coaching and education',
   'System reads every transcript and turns raw conversations into marketing copy that sounds like the customer.');

INSERT INTO offers (offer_id, name, offer_type, description, price, status, url) VALUES
  ('OFFER_MENTORSHIP_10K',  '10K Mentorship',        'Coaching',  '12-week 1-on-1 scaling program with weekly calls',              9997.00,  'Active',       'https://example.com/mentorship'),
  ('OFFER_GROUP_5K',        'Group Accelerator',      'Course',    '8-week group coaching program for $10k-$30k/month businesses',  4997.00,  'Active',       'https://example.com/accelerator'),
  ('OFFER_VIP_DAY',         'VIP Strategy Day',       'Service',   'Full-day intensive: audit + 90-day plan',                       2497.00,  'Active',       'https://example.com/vip'),
  ('OFFER_WEBINAR_FREE',    'Scaling Workshop',       'Webinar',   'Free 90-minute workshop: "3 Levers to Scale Past $50k/mo"',        0.00,  'Active',       'https://example.com/workshop'),
  ('OFFER_MINI_COURSE',     'Lead Magnet Mini-Course', 'Course',   '5-day email mini-course on cash flow for coaches',                 0.00,  'Coming Soon',  NULL);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 3. MONTHLY PREFERENCES
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO monthly_preferences (month, year, sending_days, emails_per_week, email_types, primary_goal, secondary_goal, active_offers, notes) VALUES
  (3, 2026,
   ARRAY['Monday','Wednesday','Friday'],
   3,
   ARRAY['Newsletter','Promotional','Story-based'],
   'Book Calls',
   'Nurture',
   ARRAY['OFFER_MENTORSHIP_10K','OFFER_GROUP_5K','OFFER_WEBINAR_FREE'],
   'March push: webinar funnel is hot. Lean into pain-based hooks from recent discovery calls.'),
  (4, 2026,
   ARRAY['Tuesday','Thursday'],
   2,
   ARRAY['Newsletter','Story-based'],
   'Nurture',
   'Drive Sales',
   ARRAY['OFFER_GROUP_5K','OFFER_VIP_DAY'],
   'April cool-down. Focus on storytelling and case studies from Q1 wins.');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 4. TAG DICTIONARY
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO tag_dictionary (tag, tag_type, synonyms, notes) VALUES
  ('Time Freedom',      'Theme',     'time management, work-life balance, schedule freedom',        'Core desire across most audiences'),
  ('Income Scaling',    'Goal',      'revenue growth, scaling income, hitting 50k',                 'Primary goal for target market'),
  ('Burnout',           'Pain',      'exhaustion, overwhelmed, running on fumes',                   'Top pain point — strong emotional hook'),
  ('Team Hiring',       'Pain',      'delegation, finding talent, building a team',                 'Surfaces in $30k+ earners'),
  ('Imposter Syndrome', 'Identity',  'not good enough, fraud, fake it till you make it',            'Deep identity signal — handle with care'),
  ('Offer Clarity',     'Objection', 'confused about offer, too many options, which program',       'Common pre-sale objection'),
  ('Pricing Fear',      'Objection', 'too expensive, budget, cant afford it, price anxiety',        'Handle with value framing, not discounting'),
  ('Mindset Block',     'Theme',     'limiting beliefs, self-sabotage, fear of success',            'Recurring in coaching calls'),
  ('Systems & Ops',     'Goal',      'operations, automation, SOPs, processes',                     'Aspirational for scaling businesses'),
  ('Client Results',    'Theme',     'testimonials, wins, case studies, transformations',            'Great for social proof content');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 5. LEADS (matches frontend mock data patterns)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO leads (id, name, email, phone, status, source, created_at, created_by) VALUES
  ('a1b2c3d4-0001-4000-8000-000000000001', 'Sarah Mitchell',  'sarah@example.com',     '+1 (555) 234-5678', 'appointment-set', 'webinar',  '2026-03-07T14:22:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0002-4000-8000-000000000002', 'James Torres',    'jtorres@example.com',   '+1 (555) 876-5432', 'new',             'vsl',      '2026-03-06T09:15:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0003-4000-8000-000000000003', 'Priya Nair',      'priya@example.com',     '+1 (555) 345-6789', 'qualified',       'opt-in',   '2026-03-05T16:30:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0004-4000-8000-000000000004', 'Derek Owens',     'derek@example.com',     '+1 (555) 456-7890', 'sale',            'webinar',  '2026-03-04T11:45:00Z', '00000000-0000-4000-8000-000000000002'),
  ('a1b2c3d4-0005-4000-8000-000000000005', 'Amara Johnson',   'amara@example.com',     '+1 (555) 567-8901', 'lost',            'vsl',      '2026-03-03T08:00:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0006-4000-8000-000000000006', 'Carlos Reyes',    'creyes@example.com',    '+1 (555) 678-9012', 'contacted',       'opt-in',   '2026-03-03T13:20:00Z', '00000000-0000-4000-8000-000000000002'),
  ('a1b2c3d4-0007-4000-8000-000000000007', 'Rachel Adams',    'rachel.a@example.com',  '+1 (555) 789-0123', 'new',             'opt-in',   '2026-03-28T20:10:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0008-4000-8000-000000000008', 'Tyler Brooks',    'tyler.b@example.com',   '+1 (555) 890-1234', 'contacted',       'webinar',  '2026-03-27T18:55:00Z', '00000000-0000-4000-8000-000000000003'),
  ('a1b2c3d4-0009-4000-8000-000000000009', 'Monica Reyes',    'monica.r@example.com',  '+1 (555) 901-2345', 'qualified',       'vsl',      '2026-03-26T10:05:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0010-4000-8000-000000000010', 'Chris Donovan',   'chris.d@example.com',   '+1 (555) 012-3456', 'contacted',       'ads',      '2026-03-15T07:30:00Z', '00000000-0000-4000-8000-000000000004'),
  ('a1b2c3d4-0011-4000-8000-000000000011', 'Natalie Kim',     'natalie.k@example.com', '+1 (555) 123-4567', 'new',             'referral', '2026-03-29T06:45:00Z', '00000000-0000-4000-8000-000000000001'),
  ('a1b2c3d4-0012-4000-8000-000000000012', 'Omar Hassan',     'omar.h@example.com',    '+1 (555) 234-5670', 'appointment-set', 'webinar',  '2026-03-25T15:15:00Z', '00000000-0000-4000-8000-000000000002');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 6. MEMBERS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO members (id, name, email, enrollment_date, coach_id, status) VALUES
  ('b1b2c3d4-0001-4000-8000-000000000001', 'Derek Owens',   'derek@example.com',   '2026-01-15', '00000000-0000-4000-8000-000000000002', 'active'),
  ('b1b2c3d4-0002-4000-8000-000000000002', 'Lisa Park',     'lisa.p@example.com',  '2026-02-01', '00000000-0000-4000-8000-000000000003', 'active'),
  ('b1b2c3d4-0003-4000-8000-000000000003', 'Andre Williams','andre.w@example.com', '2025-11-10', '00000000-0000-4000-8000-000000000002', 'active'),
  ('b1b2c3d4-0004-4000-8000-000000000004', 'Megan Foster',  'megan.f@example.com', '2025-12-01', '00000000-0000-4000-8000-000000000003', 'paused'),
  ('b1b2c3d4-0005-4000-8000-000000000005', 'Ryan Cho',      'ryan.c@example.com',  '2025-09-15', '00000000-0000-4000-8000-000000000002', 'graduated');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 7. CALLS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO calls (id, date, call_type, call_result, call_owner, member_id, lead_id, transcript_source, transcript_uid, transcript_quality, call_duration_minutes, processed_date, notes) VALUES
  ('CALL_SARAH_MITCHELL_20260307',  '2026-03-07', 'Discovery',      'Qualified',    'Marcus Chen',  NULL,
    'a1b2c3d4-0001-4000-8000-000000000001', 'Cockatoo', 'SARAH_MITCHELL_20260307', 'Clean', 42, '2026-03-07',
    'Sarah asked about 1-on-1 coaching. Revenue $45k/mo, wants to hit $100k. Strong fit for mentorship.'),

  ('CALL_PRIYA_NAIR_20260305',      '2026-03-05', 'Sales',          'Closed',       'Marcus Chen',  NULL,
    'a1b2c3d4-0003-4000-8000-000000000003', 'Cockatoo', 'PRIYA_NAIR_20260305', 'Clean', 55, '2026-03-05',
    'Priya committed to Group Accelerator. Revenue $250k/yr, needs team and ops help.'),

  ('CALL_DEREK_OWENS_20260301',     '2026-03-01', 'Coaching',       'N/A',          'Elena Vasquez',
    'b1b2c3d4-0001-4000-8000-000000000001', NULL, 'Cockatoo', 'DEREK_OWENS_20260301', 'Clean', 48, '2026-03-01',
    'Weekly coaching call. Derek hit $52k revenue this month — new personal best. Discussed team hiring timeline.'),

  ('CALL_LISA_PARK_20260310',       '2026-03-10', 'Coaching',       'N/A',          'Elena Vasquez',
    'b1b2c3d4-0002-4000-8000-000000000002', NULL, 'Cockatoo', 'LISA_PARK_20260310', 'Moderate', 35, '2026-03-10',
    'Lisa struggling with content creation burnout. Discussed batching strategy and AI tools.'),

  ('CALL_ANDRE_WILLIAMS_20260312',  '2026-03-12', 'Accountability', 'N/A',          'Marcus Chen',
    'b1b2c3d4-0003-4000-8000-000000000003', NULL, 'Cockatoo', 'ANDRE_WILLIAMS_20260312', 'Clean', 30, '2026-03-12',
    'Andre on track for $80k month. Main blocker: pricing fear on his premium offer. Worked through objection handling.'),

  ('CALL_AMARA_JOHNSON_20260303',   '2026-03-03', 'Sales',          'Lost',         'Sam Okafor',   NULL,
    'a1b2c3d4-0005-4000-8000-000000000005', 'Cockatoo', 'AMARA_JOHNSON_20260303', 'Messy', 28, '2026-03-03',
    'Amara liked the program but budget too tight. Revisit Q3. She mentioned fear of investing at current revenue level.'),

  ('CALL_JAMES_TORRES_20260320',    '2026-03-20', 'Discovery',      'No Decision',  'Marcus Chen',  NULL,
    'a1b2c3d4-0002-4000-8000-000000000002', 'Cockatoo', 'JAMES_TORRES_20260320', 'Clean', 38, '2026-03-20',
    'James watched the full VSL. Interested in group program but wants to think about it. Follow up in 5 days.');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 8. INSIGHTS (extracted from calls)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO insights (id, call_id, speaker_name, insight_type, signal_family, signal, signal_strength, pain_layer, raw_quote, what_they_say, the_real_problem, emotional_driver, marketing_translation, hook_angle_example, best_use_case, quote_confidence, frequency_score) VALUES

  -- Sarah Mitchell — Discovery call
  ('INS_CALL_SARAH_MITCHELL_20260307_01', 'CALL_SARAH_MITCHELL_20260307', 'Sarah Mitchell',
   'Pain', 'Income & Leverage', 'Income tied to effort', 'Strong', 'Emotional',
   'I''m making good money but I literally cannot take a day off without revenue dropping.',
   'She feels trapped by her own business model.',
   'No leverage — all revenue is tied to her personal time and effort.',
   'Exhaustion and fear of the ceiling she''s hitting.',
   'Are you the bottleneck in your own business? Here''s how to break free.',
   'You''re making $40k/month but can''t take a sick day. Sound familiar?',
   'Email', 'High', 4),

  ('INS_CALL_SARAH_MITCHELL_20260307_02', 'CALL_SARAH_MITCHELL_20260307', 'Sarah Mitchell',
   'Goal', 'Income & Leverage', 'Scale to $100k/month', 'Strong', NULL,
   'I want to hit $100k a month but without working more hours than I already am.',
   'She wants income growth without time growth.',
   'Needs systems, team, or offer restructuring to decouple time from revenue.',
   'Ambition mixed with fear that scaling means more burnout.',
   'What if you could 2x your revenue without adding a single hour to your week?',
   'She went from $45k to $100k/month — and actually works LESS now.',
   'Webinar', 'High', 6),

  -- Priya Nair — Sales call (closed)
  ('INS_CALL_PRIYA_NAIR_20260305_01', 'CALL_PRIYA_NAIR_20260305', 'Priya Nair',
   'Pain', 'Operations & Systems', 'Team hiring paralysis', 'Strong', 'Surface',
   'I know I need to hire but I don''t even know where to start. What role do I hire first?',
   'She''s overwhelmed by the hiring process.',
   'No hiring framework or org chart vision — just knows she''s drowning.',
   'Overwhelm and decision paralysis.',
   'The first hire that changed everything for this $250k business owner.',
   'Stop trying to do it all. Here''s the ONE hire that buys back 20 hours a week.',
   'Email', 'High', 3),

  ('INS_CALL_PRIYA_NAIR_20260305_02', 'CALL_PRIYA_NAIR_20260305', 'Priya Nair',
   'Win', 'Income & Leverage', 'Revenue milestone', 'Strong', NULL,
   'We just crossed $250k for the year and honestly I still can''t believe it.',
   'She''s proud but doesn''t fully own the achievement.',
   'Identity hasn''t caught up to the results — still sees herself as small.',
   'Pride mixed with imposter syndrome.',
   'She hit $250k and still felt like a fraud. Here''s what changed.',
   'The moment she realized she wasn''t "lucky" — she was actually really good at this.',
   'Social', 'High', 2),

  -- Derek Owens — Coaching call
  ('INS_CALL_DEREK_OWENS_20260301_01', 'CALL_DEREK_OWENS_20260301', 'Derek Owens',
   'Win', 'Income & Leverage', 'Revenue personal best', 'Strong', NULL,
   'I just did $52k this month. That''s the most I''ve ever made in a single month.',
   'He hit a new revenue milestone.',
   'The system is working — he needs to trust it and not self-sabotage.',
   'Excitement and validation.',
   'From stuck at $30k to $52k in one month. Here''s the shift that made it click.',
   'He changed ONE thing in his offer and added $22k in revenue.',
   'Email', 'High', 1),

  -- Lisa Park — Coaching call
  ('INS_CALL_LISA_PARK_20260310_01', 'CALL_LISA_PARK_20260310', 'Lisa Park',
   'Pain', 'Time & Energy', 'Content creation burnout', 'Strong', 'Emotional',
   'I dread content days. I used to love creating but now it just feels like a grind.',
   'Content creation has become a chore instead of a creative outlet.',
   'No content system — she''s creating from scratch every time without templates or batching.',
   'Loss of passion and creative exhaustion.',
   'If content creation feels like a grind, you''re doing it wrong. Here''s the fix.',
   'She went from dreading content days to batching a month of posts in 3 hours.',
   'Reel', 'High', 5),

  -- Andre Williams — Accountability call
  ('INS_CALL_ANDRE_WILLIAMS_20260312_01', 'CALL_ANDRE_WILLIAMS_20260312', 'Andre Williams',
   'Objection', 'Pricing & Value', 'Fear of raising prices', 'Strong', 'Emotional',
   'I know my premium offer should be $10k but every time I go to pitch it I freeze up and drop back to $5k.',
   'He can''t hold his price in the sales conversation.',
   'Pricing fear rooted in not fully believing his offer is worth $10k.',
   'Fear of rejection and not being "worth it".',
   'You built a $10k offer but you''re selling it for $5k. Here''s why.',
   'The pricing script that helped him finally hold his $10k price (and close more).',
   'Email', 'High', 4),

  -- Amara Johnson — Lost sale
  ('INS_CALL_AMARA_JOHNSON_20260303_01', 'CALL_AMARA_JOHNSON_20260303', 'Amara Johnson',
   'Objection', 'Pricing & Value', 'Budget constraint', 'Moderate', 'Surface',
   'I just don''t think I can swing $10k right now. Maybe later in the year when things pick up.',
   'She says it''s about money.',
   'Likely a value perception issue more than a true budget constraint.',
   'Financial anxiety and risk aversion.',
   'Think you can''t afford coaching? Here''s what it''s actually costing you NOT to invest.',
   'She said she couldn''t afford it. 6 months later, she realized she couldn''t afford NOT to.',
   'Email', 'Medium', 7);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 9. INSIGHT TAGS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO insight_tags (insight_id, tag) VALUES
  ('INS_CALL_SARAH_MITCHELL_20260307_01', 'Burnout'),
  ('INS_CALL_SARAH_MITCHELL_20260307_01', 'Income Scaling'),
  ('INS_CALL_SARAH_MITCHELL_20260307_02', 'Income Scaling'),
  ('INS_CALL_SARAH_MITCHELL_20260307_02', 'Time Freedom'),
  ('INS_CALL_PRIYA_NAIR_20260305_01',     'Team Hiring'),
  ('INS_CALL_PRIYA_NAIR_20260305_01',     'Systems & Ops'),
  ('INS_CALL_PRIYA_NAIR_20260305_02',     'Imposter Syndrome'),
  ('INS_CALL_PRIYA_NAIR_20260305_02',     'Client Results'),
  ('INS_CALL_DEREK_OWENS_20260301_01',    'Income Scaling'),
  ('INS_CALL_DEREK_OWENS_20260301_01',    'Client Results'),
  ('INS_CALL_LISA_PARK_20260310_01',       'Burnout'),
  ('INS_CALL_LISA_PARK_20260310_01',       'Time Freedom'),
  ('INS_CALL_ANDRE_WILLIAMS_20260312_01', 'Pricing Fear'),
  ('INS_CALL_ANDRE_WILLIAMS_20260312_01', 'Mindset Block'),
  ('INS_CALL_AMARA_JOHNSON_20260303_01',  'Pricing Fear'),
  ('INS_CALL_AMARA_JOHNSON_20260303_01',  'Offer Clarity');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 10. CONTENT IDEAS (generated from insights)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO content_ideas (id, insight_id, call_id, source, market_audience, content_format, content_angle, trigger_insight, raw_quote, content_premise, hook_opening_line, teaching_point, cta_idea, priority_level, best_platform, idea_score, status) VALUES

  ('CONT_CALL_SARAH_MITCHELL_20260307_01',
   'INS_CALL_SARAH_MITCHELL_20260307_01', 'CALL_SARAH_MITCHELL_20260307',
   'AI Extraction', 'Online coaches doing $30-60k/month',
   'Email', 'Pain-based — income ceiling trap',
   'Income tied to effort', 'I literally cannot take a day off without revenue dropping.',
   'Most coaches hit a ceiling because their business model requires them to trade time for money. This email breaks down the 3 leverage points that let you decouple.',
   'You hit $40k/month. Congrats. But can you take a vacation?',
   'The 3 types of leverage: offers, team, systems. Most coaches only use one.',
   'Book a strategy call to map your leverage plan.',
   'High', 'Email', 9, 'Scheduled'),

  ('CONT_CALL_SARAH_MITCHELL_20260307_02',
   'INS_CALL_SARAH_MITCHELL_20260307_02', 'CALL_SARAH_MITCHELL_20260307',
   'AI Extraction', 'Ambitious coaches ready to scale',
   'Webinar', 'Goal-based — path to $100k/month',
   'Scale to $100k/month', 'I want to hit $100k a month but without working more hours.',
   'Webinar segment showing the math behind $100k months: offer stack, conversion rates, and the team structure that makes it possible.',
   'The $100k/month math that nobody shows you.',
   'You don''t need more clients — you need better offers and one key hire.',
   'Register for the scaling workshop.',
   'High', 'Webinar', 8, 'Idea'),

  ('CONT_CALL_LISA_PARK_20260310_01',
   'INS_CALL_LISA_PARK_20260310_01', 'CALL_LISA_PARK_20260310',
   'AI Extraction', 'Coaches and creators drowning in content',
   'Reel', 'Pain-based — content burnout',
   'Content creation burnout', 'I dread content days.',
   'Quick reel showing the before/after of batch content creation. "You used to love this. Here''s how to love it again."',
   'When did you stop loving content creation?',
   'Batch creation + templates = 1 day per month instead of daily grind.',
   'DM "BATCH" for the free content batching template.',
   'Medium', 'Instagram', 7, 'Idea'),

  ('CONT_CALL_ANDRE_WILLIAMS_20260312_01',
   'INS_CALL_ANDRE_WILLIAMS_20260312_01', 'CALL_ANDRE_WILLIAMS_20260312',
   'AI Extraction', 'Coaches undercharging for premium offers',
   'Email', 'Objection-handling — pricing fear',
   'Fear of raising prices', 'Every time I go to pitch it I freeze up and drop back to $5k.',
   'Story-based email: "My client built a $10k offer but kept selling it for $5k. Here''s the exact moment that changed."',
   'You built a $10k offer. So why are you selling it for $5k?',
   'Pricing confidence comes from proof, not affirmations. Stack testimonials + guarantees.',
   'Reply with your current price and I''ll tell you if you''re undercharging.',
   'High', 'Email', 8, 'Scheduled'),

  ('CONT_CALL_PRIYA_NAIR_20260305_01',
   'INS_CALL_PRIYA_NAIR_20260305_02', 'CALL_PRIYA_NAIR_20260305',
   'AI Extraction', 'Coaches who hit milestones but still feel small',
   'Post', 'Win-story — imposter syndrome at scale',
   'Revenue milestone', 'We just crossed $250k for the year and honestly I still can''t believe it.',
   'LinkedIn post celebrating a client win while addressing the imposter syndrome that comes with scaling.',
   'She hit $250k and still felt like a fraud.',
   'Success doesn''t cure imposter syndrome. Community and proof do.',
   'Tag someone who needs to hear this.',
   'Medium', 'LinkedIn', 6, 'Idea');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 11. MARKET SIGNALS (aggregated from insights)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO market_signals (signal_family, signal, insight_type, total_mentions, last_30_days, last_7_days, example_quote, example_call_id, best_marketing_angle, notes) VALUES
  ('Income & Leverage', 'Income tied to effort',      'Pain',      14, 4, 1, 'I literally cannot take a day off without revenue dropping.',        'CALL_SARAH_MITCHELL_20260307', 'Freedom-based: "What if your income didn''t depend on your calendar?"',  'Strongest pain signal across all calls. Use in email subject lines.'),
  ('Income & Leverage', 'Scale to $100k/month',       'Goal',      11, 3, 1, 'I want to hit $100k a month but without working more hours.',         'CALL_SARAH_MITCHELL_20260307', 'Aspirational: Show the math and proof it''s possible.',                  'Pair with case study of someone who did it.'),
  ('Pricing & Value',   'Fear of raising prices',     'Objection',  9, 4, 1, 'Every time I go to pitch it I freeze up.',                           'CALL_ANDRE_WILLIAMS_20260312', 'Confidence-based: "Your price isn''t the problem. Your belief is."',     'High emotional resonance. Story-based emails work best.'),
  ('Pricing & Value',   'Budget constraint',          'Objection',  7, 2, 1, 'I just don''t think I can swing $10k right now.',                     'CALL_AMARA_JOHNSON_20260303', 'ROI framing: "What''s it costing you NOT to invest?"',                   'Often a value perception issue, not a real budget issue.'),
  ('Time & Energy',     'Content creation burnout',   'Pain',       8, 5, 2, 'I dread content days.',                                              'CALL_LISA_PARK_20260310',      'Efficiency-based: "1 day/month instead of daily grind."',               'Growing signal — content fatigue is real across the market.'),
  ('Operations & Systems', 'Team hiring paralysis',   'Pain',       6, 3, 1, 'I know I need to hire but I don''t even know where to start.',        'CALL_PRIYA_NAIR_20260305',     'Clarity-based: "The first hire that buys back 20 hours."',              'Surfaces in $30k+ earners consistently.');

-- ═══════════════════════════════════════════════════════════════════════════════
-- 12. GOALS, PAIN POINTS, WINS, OBJECTIONS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO goals (member_id, lead_id, goal_text, target_date, status) VALUES
  ('b1b2c3d4-0001-4000-8000-000000000001', NULL, 'Hit $75k/month consistently',        '2026-06-30', 'active'),
  ('b1b2c3d4-0001-4000-8000-000000000001', NULL, 'Hire first full-time team member',    '2026-04-30', 'active'),
  ('b1b2c3d4-0002-4000-8000-000000000002', NULL, 'Launch group coaching program',       '2026-05-15', 'active'),
  ('b1b2c3d4-0003-4000-8000-000000000003', NULL, 'Scale to $100k/month',                '2026-09-01', 'active'),
  (NULL, 'a1b2c3d4-0001-4000-8000-000000000001', 'Decide on mentorship program',        '2026-03-15', 'active'),
  (NULL, 'a1b2c3d4-0003-4000-8000-000000000003', 'Build hiring plan before enrolling',  '2026-03-20', 'active');

INSERT INTO pain_points (member_id, lead_id, text, category, frequency_count) VALUES
  ('b1b2c3d4-0002-4000-8000-000000000002', NULL, 'Content creation takes too long — no system or templates',  'Time & Energy',        3),
  ('b1b2c3d4-0003-4000-8000-000000000003', NULL, 'Afraid to price premium offer above $5k',                   'Pricing & Value',      2),
  ('b1b2c3d4-0004-4000-8000-000000000004', NULL, 'Overwhelmed managing clients + marketing + admin alone',     'Operations & Systems', 4),
  (NULL, 'a1b2c3d4-0005-4000-8000-000000000005', 'Budget too tight for investment this quarter',               'Pricing & Value',      1),
  (NULL, 'a1b2c3d4-0001-4000-8000-000000000001', 'Cannot take time off without revenue dropping',              'Income & Leverage',    2);

INSERT INTO wins (member_id, win_text, win_date, impact_area) VALUES
  ('b1b2c3d4-0001-4000-8000-000000000001', 'Hit $52k in a single month — new personal best',                '2026-03-01', 'Revenue'),
  ('b1b2c3d4-0001-4000-8000-000000000001', 'First $10k sale on premium offer',                                '2026-02-14', 'Sales'),
  ('b1b2c3d4-0002-4000-8000-000000000002', 'Signed 3 new clients from a single Instagram reel',              '2026-03-08', 'Marketing'),
  ('b1b2c3d4-0003-4000-8000-000000000003', 'On track for $80k month',                                         '2026-03-12', 'Revenue'),
  ('b1b2c3d4-0005-4000-8000-000000000005', 'Graduated program with $500k annual revenue achieved',            '2026-03-20', 'Revenue');

INSERT INTO objections (lead_id, objection_text, context, resolution_offered) VALUES
  ('a1b2c3d4-0005-4000-8000-000000000005', 'Can''t afford $10k right now',                   'Sales call — end of pitch',             'Offered payment plan. Still declined. Follow up Q3.'),
  ('a1b2c3d4-0002-4000-8000-000000000002', 'Need to think about it',                          'Discovery call — post-demo',            'Sent case study + booked follow-up call in 5 days.'),
  ('a1b2c3d4-0006-4000-8000-000000000006', 'Not sure if this is the right time',              'Follow-up email reply',                 'Shared ROI calculator and timeline comparison.'),
  ('a1b2c3d4-0009-4000-8000-000000000009', 'I have a small team already — will this still help?', 'VSL follow-up call',               'Explained the program covers scaling teams, not just first hires.');

-- ═══════════════════════════════════════════════════════════════════════════════
-- Done! All tables populated with realistic, interconnected seed data.
-- ═══════════════════════════════════════════════════════════════════════════════
