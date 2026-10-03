{# Small stand-in for dbt_utils.generate_surrogate_key without a package dependency. #}
{% macro dbt_utils_surrogate(columns) -%}
  md5(concat_ws('|', {% for c in columns %}coalesce(cast({{ c }} as varchar), '∅'){% if not loop.last %}, {% endif %}{% endfor %}))
{%- endmacro %}
