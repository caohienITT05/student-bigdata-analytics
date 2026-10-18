-- table: a_summary
SELECT source, source_file, is_synthetic, has_target, COUNT(*) AS records,
       SUM(CASE WHEN Target IS NOT NULL THEN 1 ELSE 0 END) AS labelled_records,
       SUM(CASE WHEN Target = 'Dropout' THEN 1 ELSE 0 END) AS dropout_records,
       ROUND(100.0 * SUM(CASE WHEN Target = 'Dropout' THEN 1 ELSE 0 END) / NULLIF(COUNT(Target),0),2) AS dropout_percent,
       AVG(age_at_enrollment) AS mean_age, AVG(sem1_grade) AS mean_sem1, AVG(sem2_grade) AS mean_sem2,
       SUM(CASE WHEN size(_issues)>0 THEN 1 ELSE 0 END) AS flagged_records
FROM academic GROUP BY source, source_file, is_synthetic, has_target

-- table: a_target
SELECT source, source_file, is_synthetic, has_target, Target AS target, COUNT(*) AS records
FROM academic GROUP BY source, source_file, is_synthetic, has_target, Target

-- table: a_histograms
SELECT source, source_file, is_synthetic, has_target, metric,
 CASE WHEN value IS NULL THEN 'Không xác định'
 WHEN metric='age' THEN CASE WHEN value<20 THEN '<20' WHEN value<25 THEN '20–24' WHEN value<35 THEN '25–34' WHEN value<45 THEN '35–44' ELSE '45+' END
 WHEN value=0 THEN '0' WHEN value<0 OR value>20 THEN 'Ngoài 0–20' WHEN value<5 THEN '(0,5)' WHEN value<10 THEN '[5,10)' WHEN value<15 THEN '[10,15)' ELSE '[15,20]' END AS bin,
 CASE WHEN value IS NULL THEN 99 WHEN metric='age' THEN CASE WHEN value<20 THEN 0 WHEN value<25 THEN 1 WHEN value<35 THEN 2 WHEN value<45 THEN 3 ELSE 4 END
 WHEN value=0 THEN 0 WHEN value<0 OR value>20 THEN 98 WHEN value<5 THEN 1 WHEN value<10 THEN 2 WHEN value<15 THEN 3 ELSE 4 END AS bin_order,
 COUNT(*) AS records
FROM academic LATERAL VIEW STACK(3,'age',CAST(age_at_enrollment AS DOUBLE),'sem1_grade',sem1_grade,'sem2_grade',sem2_grade) h AS metric,value
GROUP BY source,source_file,is_synthetic,has_target,metric,bin,bin_order
