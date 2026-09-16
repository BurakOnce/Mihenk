
-- düz, kalıcı bir sayı dizisi. fabric warehouse'ta burada uzak durulacak iki şey
-- var, ikisi de denendi ve ikisi de "references an object that is not supported
-- in distributed processing mode" ile reddedildi: sys.columns'un kendisiyle cross
-- join'i (sistem katalog görünümü dağıtık motorda join edilemiyor) ve
-- ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - sıralamasız bir window fonksiyonu,
-- düz bir VALUES tablosu üzerinde bile. gerçekten çalışan GENERATE_SERIES.
CREATE TABLE ctl.util_numbers (n INT NOT NULL);
GO

INSERT INTO ctl.util_numbers (n)
SELECT value FROM GENERATE_SERIES(0, 99999);
GO

ALTER TABLE ctl.util_numbers
    ADD CONSTRAINT pk_util_numbers PRIMARY KEY NONCLUSTERED (n) NOT ENFORCED;
GO
