select * from "football"."marts"."fct_match"
where close_overround is not null and (close_overround < 0.98 or close_overround > 1.25)