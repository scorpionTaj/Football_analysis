-- Grain and tests: _serving.yml.
select * from {{ ref('stg_app__match_contexts') }}
