-- Filtered season/team query.
SELECT game_id, gameday, home_team, away_team FROM games
WHERE season = 2024 AND (home_team = 'KC' OR away_team = 'KC') ORDER BY gameday;
-- Aggregate historical home win rate, with ties counted separately.
SELECT season, COUNT(*) AS games,
 AVG(((payload->>'home_score')::integer > (payload->>'away_score')::integer)::integer) AS home_win_rate,
 SUM(((payload->>'home_score')::integer = (payload->>'away_score')::integer)::integer) AS ties
FROM games GROUP BY season ORDER BY season;
-- Feature construction: strict earlier-day boundary.
SELECT payload FROM games WHERE gameday < DATE '2025-09-01' ORDER BY gameday, game_id;
EXPLAIN (ANALYZE, BUFFERS) SELECT game_id FROM games WHERE season = 2024 ORDER BY gameday;
