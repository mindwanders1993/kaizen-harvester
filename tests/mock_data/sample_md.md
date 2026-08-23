# Consecutive Numbers

## Problem Description
Find all numbers that appear at least three times consecutively in the `Logs` table.

### Schema
```sql
CREATE TABLE Logs (
    id INT PRIMARY KEY,
    num INT
);

INSERT INTO Logs (id, num) VALUES
(1, 1),
(2, 1),
(3, 1),
(4, 2),
(5, 1),
(6, 2),
(7, 2);
```

### Solution
```sql
SELECT DISTINCT num AS ConsecutiveNums
FROM (
    SELECT num,
           LEAD(num, 1) OVER (ORDER BY id) AS next_num,
           LEAD(num, 2) OVER (ORDER BY id) AS next_next_num
    FROM Logs
) sub
WHERE num = next_num AND num = next_next_num;
```
