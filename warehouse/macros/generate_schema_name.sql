{# Use the layer name as-is (staging, marts, ...) instead of <target>_<layer>. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
