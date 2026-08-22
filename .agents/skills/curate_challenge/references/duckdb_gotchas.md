# DuckDB vs. PostgreSQL/Spark SQL — Dialect Gotcha Reference

> **Purpose**: Every ground truth SQL query extracted by Kaizen Harvester MUST be verified against this list before persisting to the DuckDB vault.

---

## ⚠️ Integer Division

| Context | PostgreSQL / Spark | DuckDB |
|:---|:---|:---|
| `5 / 2` | `2` (integer) | `2.5` (float) |
| Force integer division | `5 / 2` | `5 // 2` |

**Fix**: If the question requires integer division, use `//` or cast explicitly: `CAST(5 AS INTEGER) / CAST(2 AS INTEGER)`.

---

## 📅 Date & Time Functions

| Operation | PostgreSQL | Spark SQL | DuckDB |
|:---|:---|:---|:---|
| Current date | `CURRENT_DATE` | `CURRENT_DATE` | `CURRENT_DATE` ✅ |
| Date arithmetic | `date + INTERVAL '1 day'` | `date_add(date, 1)` | `date + INTERVAL 1 DAY` |
| Truncate to month | `DATE_TRUNC('month', col)` | `DATE_TRUNC('MONTH', col)` | `DATE_TRUNC('month', col)` ✅ |
| Day of week (1=Mon) | `EXTRACT(ISODOW FROM col)` | `DAYOFWEEK(col)` | `ISODOW(col)` or `EXTRACT(ISODOW FROM col)` |
| String → Date | `TO_DATE(col, 'YYYY-MM-DD')` | `TO_DATE(col, 'yyyy-MM-dd')` | `STRPTIME(col, '%Y-%m-%d')::DATE` |
| Make a date | `MAKE_DATE(y, m, d)` | `MAKE_DATE(y, m, d)` | `MAKE_DATE(y, m, d)` ✅ |
| Diff in days | `col1 - col2` | `DATEDIFF(col1, col2)` | `DATEDIFF('day', col2, col1)` |

---

## 🔤 String Functions

| Operation | PostgreSQL | Spark SQL | DuckDB |
|:---|:---|:---|:---|
| Split string | `STRING_TO_ARRAY(col, ',')` | `SPLIT(col, ',')` | `STRING_SPLIT(col, ',')` |
| String aggregate | `STRING_AGG(col, ',')` | `COLLECT_LIST(col)` | `STRING_AGG(col, ',')` ✅ |
| Regex match | `col ~ 'pattern'` | `col RLIKE 'pattern'` | `REGEXP_MATCHES(col, 'pattern')` |
| Regex extract | `REGEXP_MATCH(col, '...')` | `REGEXP_EXTRACT(col, '...')` | `REGEXP_EXTRACT(col, '...')` |
| Position | `POSITION('x' IN col)` | `INSTR(col, 'x')` | `POSITION('x' IN col)` ✅ |

---

## 🪟 Window Functions & QUALIFY

| Operation | PostgreSQL | Spark SQL | DuckDB |
|:---|:---|:---|:---|
| Filter on window result | Subquery required | `QUALIFY` supported | `QUALIFY` supported ✅ |
| ROWS vs RANGE | Supported | Supported | Supported ✅ |
| `LEAD`/`LAG` | Supported | Supported | Supported ✅ |
| `PERCENT_RANK` | Supported | Supported | Supported ✅ |

**DuckDB Advantage**: Use `QUALIFY` to filter on window function results without a subquery:
```sql
SELECT *, RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk
FROM employees
QUALIFY rnk <= 3;
```
