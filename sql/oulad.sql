-- table: b_population
SELECT code_module,code_presentation,scope,COUNT(*) AS enrolments,COUNT(DISTINCT id_student) AS unique_learners,
 SUM(CASE WHEN event_rows=0 THEN 1 ELSE 0 END) AS no_activity_enrolments,
 SUM(CASE WHEN total_clicks IS NULL THEN 1 ELSE 0 END) AS clicks_undefined_enrolments,
 SUM(total_clicks) AS clicks
FROM oulad_profile WHERE scope='full' GROUP BY scope,CUBE(code_module,code_presentation)

-- table: b_results
SELECT code_module,code_presentation,scope,final_result,COUNT(*) AS enrolments,
 SUM(total_clicks) AS clicks,AVG(total_clicks) AS mean_clicks,AVG(active_days) AS mean_active_days,
 SUM(pre_start_clicks) AS pre_start_clicks,AVG(resources_used) AS mean_resources,
 SUM(CASE WHEN event_rows=0 THEN 1 ELSE 0 END) AS no_activity_enrolments
FROM oulad_profile WHERE scope='full' GROUP BY scope,final_result,CUBE(code_module,code_presentation)

-- table: b_weekly
SELECT w.code_module,w.code_presentation,w.scope,w.week,p.final_result,
 COUNT(*) AS active_enrolments,SUM(w.clicks) AS clicks,SUM(w.active_days) AS enrolment_active_days,
 AVG(w.resources) AS mean_resources,MAX(w.last_activity_day) AS last_activity_day
FROM oulad_weekly w JOIN oulad_full p ON w.id_student=p.id_student AND w.code_module=p.code_module AND w.code_presentation=p.code_presentation
WHERE w.scope='full'
GROUP BY w.scope,w.week,p.final_result,CUBE(w.code_module,w.code_presentation)
