-- Problem: Second Highest Salary
-- Write a SQL query to get the second highest salary from the Employee table.
--
-- Setup DDL:
CREATE TABLE IF NOT EXISTS Employee (
    id INT PRIMARY KEY,
    salary INT
);

INSERT INTO Employee (id, salary) VALUES
(1, 100),
(2, 200),
(3, 300);

-- Solution Query:
SELECT MAX(salary) AS SecondHighestSalary
FROM Employee
WHERE salary < (SELECT MAX(salary) FROM Employee);
