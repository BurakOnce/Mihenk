
-- a plain, persisted number sequence. two things NOT to reach for here on
-- fabric warehouse, both tried and both rejected with "references an object
-- that is not supported in distributed processing mode": sys.columns cross
-- joined with itself (a system catalog view can't be joined in the
-- distributed engine), and ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - an
-- order-nothing window function, even over a plain VALUES table. GENERATE_SERIES
-- is the one that actually works.
CREATE TABLE ctl.util_numbers (n INT NOT NULL);
GO

INSERT INTO ctl.util_numbers (n)
SELECT value FROM GENERATE_SERIES(0, 99999);
GO

ALTER TABLE ctl.util_numbers
    ADD CONSTRAINT pk_util_numbers PRIMARY KEY NONCLUSTERED (n) NOT ENFORCED;
GO
