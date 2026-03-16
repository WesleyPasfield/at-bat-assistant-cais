## Examples

### Example 1: Entity Resolution Function

```sql
CREATE OR REPLACE FUNCTION catalog.schema.lookup_entity_by_name(
  name_first STRING COMMENT 'The first name of the entity to look up (e.g., "John")',
  name_last STRING COMMENT 'The last name of the entity to look up (e.g., "Smith")'
)
RETURNS TABLE
LANGUAGE SQL
COMMENT 'Look up entity ID by name. Call this first to resolve names to IDs before using other functions.'
RETURN (
  SELECT *
  FROM catalog.schema.dim_entities
  WHERE LOWER(name_first) = LOWER(name_first)
    AND LOWER(name_last) = LOWER(name_last)
  LIMIT 1
)
```

### Example 2: Direct Query with Typed Filters

```sql
CREATE OR REPLACE FUNCTION catalog.schema.get_tendency_by_category(
  entity_id INT COMMENT 'The entity ID. Use lookup_entity_by_name first to resolve names to IDs',
  category STRING COMMENT 'The category filter: "A" for type A, "B" for type B, "C" for type C',
  count_a INT COMMENT 'The first count value. If the count is 0, you must provide 0 rather than nothing',
  count_b INT COMMENT 'The second count value. If the count is 0, you must provide 0 rather than nothing',
  period INT COMMENT 'The time period to look up (e.g., 2024, 2025)'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Get entity tendency by category: type, location, and frequency. Returns JSON sorted by type then frequency.'
RETURN (
  WITH aggregated AS (
    SELECT type, location, COUNT(*) as cnt
    FROM catalog.schema.events
    WHERE entity_id = entity_id
      AND category = category
      AND count_a = count_a
      AND count_b = count_b
      AND period = period
    GROUP BY type, location
  ),
  with_frequency AS (
    SELECT
      struct(type, location, cnt,
             ROUND(100.0 * cnt / SUM(cnt) OVER (), 1) as frequency_pct
      ) AS result_struct
    FROM aggregated
    ORDER BY type, frequency_pct DESC
  )
  SELECT to_json(collect_list(result_struct))
  FROM with_frequency
)
```

### Example 3: Contextual Query (Direct + Situational Filters)

```sql
CREATE OR REPLACE FUNCTION catalog.schema.get_tendency_with_context(
  entity_id INT COMMENT 'The entity ID. Use lookup_entity_by_name first to resolve names to IDs',
  category STRING COMMENT 'The category filter: "A" for type A, "B" for type B',
  count_a INT COMMENT 'First count value. If 0, you must provide 0 rather than nothing',
  count_b INT COMMENT 'Second count value. If 0, you must provide 0 rather than nothing',
  context_flag_1 BOOLEAN COMMENT 'Whether context condition 1 is present',
  context_flag_2 BOOLEAN COMMENT 'Whether context condition 2 is present',
  period INT COMMENT 'The time period to look up'
)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Get entity tendency by category AND situational context. Returns JSON with type, location, and frequency.'
RETURN (
  -- Same structure as direct query but with additional WHERE clauses
  -- for context flags using: AND (flag IS NULL OR (column IS NOT NULL) = flag)
)
```

### Example 4: Embedding Lookup → Vector Search (Two-Step Chain)

**Step 1: Look up the embedding for a known entity**

```sql
CREATE OR REPLACE FUNCTION catalog.schema.entity_embedding_lookup(
  entity_id BIGINT COMMENT 'The entity ID to look up',
  period BIGINT COMMENT 'The time period to look up',
  entity_type STRING COMMENT 'The type to look up (e.g., FF, SL, CH)'
)
RETURNS TABLE
LANGUAGE SQL
COMMENT 'Look up embedding vector for an entity by ID, period, and type. Returns the embedding vector used for similarity search. Run type_lookup first to get valid types for this entity.'
RETURN (
  SELECT entity_id, entity_type, embedding_vector
  FROM catalog.schema.entity_vectors_mean
  WHERE entity_id = entity_id
    AND period = period
    AND entity_type = entity_type
  LIMIT 1
)
```

**Step 2: Pass the vector to similarity search**

```sql
CREATE OR REPLACE FUNCTION catalog.schema.entity_embedding_query(
  e_vector ARRAY<FLOAT> COMMENT 'The embedding vector (list of floats) to search for similar entities'
)
RETURNS TABLE
LANGUAGE SQL
COMMENT 'Query Vector Search index for similar entities. Takes an embedding vector from entity_embedding_lookup and returns the most similar entities.'
RETURN (
  SELECT * FROM vector_search(
    index => "catalog.schema.entity_vectors_index",
    query_vector => e_vector,
    num_results => 6,
    query_type => 'ANN'
  )
)
```

**Key:** The COMMENT on the query function explicitly says it takes output from the lookup function. This teaches the LLM the two-step chain.

### Example 5: Aggregation Function with Joins

```sql
CREATE OR REPLACE FUNCTION catalog.schema.recommend_matchups_by_group(
  target_id BIGINT COMMENT 'Target entity ID',
  group_abbr STRING COMMENT 'Group abbreviation (e.g., team code)',
  period INT COMMENT 'Time period for the query'
)
RETURNS TABLE
LANGUAGE SQL
COMMENT 'Weighted expected outcome per group member against a target entity. Use this for requests that want to understand which members will perform well in a specific scenario.'
RETURN (
  WITH members AS (
    SELECT member_id, member_name, group_id
    FROM catalog.schema.dim_group_members
    WHERE period = period AND group_id = group_abbr
  ),
  scored AS (
    SELECT
      m.member_id, m.member_name, m.group_id,
      SUM(perf.score * usage.weight) AS expected_outcome
    FROM members m
    JOIN catalog.schema.member_performance perf ON perf.member_id = m.member_id
    JOIN catalog.schema.target_usage usage ON usage.target_id = target_id
    GROUP BY m.member_id, m.member_name, m.group_id
  )
  SELECT * FROM scored ORDER BY expected_outcome DESC LIMIT 30
)
```

### Example 6: Function Name Good vs Bad

```
Good function names (verb-first, specific):
  lookup_player_by_name
  get_tendency_by_count
  get_tendency_with_runners
  recommend_matchups_by_team
  pitcher_arsenal_lookup
  batter_embedding_query

Bad function names (vague, ambiguous):
  query_data
  get_info
  search
  analyze
  run_query
  fetch_results
```

### Example 7: COMMENT Good vs Bad

```sql
-- Bad: restates the type, no guidance
entity_id INT COMMENT 'The entity ID'

-- Good: tells the LLM where to get the value
entity_id INT COMMENT 'The entity ID. Use lookup_entity_by_name first to resolve names to IDs'

-- Bad: no boundary information
COMMENT 'Returns entity data'

-- Good: specifies when, what, prerequisites, and exclusions
COMMENT 'Get entity tendency by category and count. Returns JSON with type, location, frequency.
         Requires entity ID from lookup_entity_by_name. Does NOT include contextual data —
         use get_tendency_with_context for situational analysis.'
```
