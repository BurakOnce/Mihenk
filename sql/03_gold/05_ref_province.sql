-- üretilmiş dosya, elle düzenleme - bkz. tools/generate_ctl_seed.py
-- 2026-09-13 21:37:24 tarihinde src/data_generator/reference.py'den üretildi (81 il)

CREATE TABLE gold.ref_province
(
    province_code   VARCHAR(2)      NOT NULL,
    province_name   VARCHAR(40)     NOT NULL,
    region          VARCHAR(30)     NOT NULL,
    population_m    DECIMAL(9,2)    NULL
);
GO

INSERT INTO gold.ref_province (province_code, province_name, region, population_m)
SELECT * FROM (VALUES
    ('01', 'Adana', 'Akdeniz', 2.27),
    ('02', 'Adıyaman', 'Güneydoğu Anadolu', 0.64),
    ('03', 'Afyonkarahisar', 'Ege', 0.75),
    ('04', 'Ağrı', 'Doğu Anadolu', 0.51),
    ('05', 'Amasya', 'Karadeniz', 0.34),
    ('06', 'Ankara', 'İç Anadolu', 5.8),
    ('07', 'Antalya', 'Akdeniz', 2.69),
    ('08', 'Artvin', 'Karadeniz', 0.17),
    ('09', 'Aydın', 'Ege', 1.15),
    ('10', 'Balıkesir', 'Marmara', 1.26),
    ('11', 'Bilecik', 'Marmara', 0.23),
    ('12', 'Bingöl', 'Doğu Anadolu', 0.28),
    ('13', 'Bitlis', 'Doğu Anadolu', 0.35),
    ('14', 'Bolu', 'Karadeniz', 0.32),
    ('15', 'Burdur', 'Akdeniz', 0.27),
    ('16', 'Bursa', 'Marmara', 3.24),
    ('17', 'Çanakkale', 'Marmara', 0.56),
    ('18', 'Çankırı', 'İç Anadolu', 0.2),
    ('19', 'Çorum', 'Karadeniz', 0.53),
    ('20', 'Denizli', 'Ege', 1.06),
    ('21', 'Diyarbakır', 'Güneydoğu Anadolu', 1.8),
    ('22', 'Edirne', 'Marmara', 0.41),
    ('23', 'Elazığ', 'Doğu Anadolu', 0.6),
    ('24', 'Erzincan', 'Doğu Anadolu', 0.24),
    ('25', 'Erzurum', 'Doğu Anadolu', 0.75),
    ('26', 'Eskişehir', 'İç Anadolu', 0.92),
    ('27', 'Gaziantep', 'Güneydoğu Anadolu', 2.16),
    ('28', 'Giresun', 'Karadeniz', 0.45),
    ('29', 'Gümüşhane', 'Karadeniz', 0.15),
    ('30', 'Hakkari', 'Doğu Anadolu', 0.28),
    ('31', 'Hatay', 'Akdeniz', 1.69),
    ('32', 'Isparta', 'Akdeniz', 0.45),
    ('33', 'Mersin', 'Akdeniz', 1.94),
    ('34', 'İstanbul', 'Marmara', 15.65),
    ('35', 'İzmir', 'Ege', 4.46),
    ('36', 'Kars', 'Doğu Anadolu', 0.28),
    ('37', 'Kastamonu', 'Karadeniz', 0.39),
    ('38', 'Kayseri', 'İç Anadolu', 1.45),
    ('39', 'Kırklareli', 'Marmara', 0.37),
    ('40', 'Kırşehir', 'İç Anadolu', 0.24),
    ('41', 'Kocaeli', 'Marmara', 2.08),
    ('42', 'Konya', 'İç Anadolu', 2.31),
    ('43', 'Kütahya', 'Ege', 0.58),
    ('44', 'Malatya', 'Doğu Anadolu', 0.81),
    ('45', 'Manisa', 'Ege', 1.47),
    ('46', 'Kahramanmaraş', 'Akdeniz', 1.18),
    ('47', 'Mardin', 'Güneydoğu Anadolu', 0.87),
    ('48', 'Muğla', 'Ege', 1.05),
    ('49', 'Muş', 'Doğu Anadolu', 0.4),
    ('50', 'Nevşehir', 'İç Anadolu', 0.31),
    ('51', 'Niğde', 'İç Anadolu', 0.37),
    ('52', 'Ordu', 'Karadeniz', 0.76),
    ('53', 'Rize', 'Karadeniz', 0.35),
    ('54', 'Sakarya', 'Marmara', 1.09),
    ('55', 'Samsun', 'Karadeniz', 1.37),
    ('56', 'Siirt', 'Güneydoğu Anadolu', 0.33),
    ('57', 'Sinop', 'Karadeniz', 0.22),
    ('58', 'Sivas', 'İç Anadolu', 0.64),
    ('59', 'Tekirdağ', 'Marmara', 1.14),
    ('60', 'Tokat', 'Karadeniz', 0.6),
    ('61', 'Trabzon', 'Karadeniz', 0.82),
    ('62', 'Tunceli', 'Doğu Anadolu', 0.09),
    ('63', 'Şanlıurfa', 'Güneydoğu Anadolu', 2.21),
    ('64', 'Uşak', 'Ege', 0.38),
    ('65', 'Van', 'Doğu Anadolu', 1.13),
    ('66', 'Yozgat', 'İç Anadolu', 0.42),
    ('67', 'Zonguldak', 'Karadeniz', 0.58),
    ('68', 'Aksaray', 'İç Anadolu', 0.44),
    ('69', 'Bayburt', 'Karadeniz', 0.08),
    ('70', 'Karaman', 'İç Anadolu', 0.26),
    ('71', 'Kırıkkale', 'İç Anadolu', 0.28),
    ('72', 'Batman', 'Güneydoğu Anadolu', 0.63),
    ('73', 'Şırnak', 'Güneydoğu Anadolu', 0.57),
    ('74', 'Bartın', 'Karadeniz', 0.2),
    ('75', 'Ardahan', 'Doğu Anadolu', 0.08),
    ('76', 'Iğdır', 'Doğu Anadolu', 0.2),
    ('77', 'Yalova', 'Marmara', 0.3),
    ('78', 'Karabük', 'Karadeniz', 0.25),
    ('79', 'Kilis', 'Güneydoğu Anadolu', 0.15),
    ('80', 'Osmaniye', 'Akdeniz', 0.56),
    ('81', 'Düzce', 'Karadeniz', 0.4)
) AS v (province_code, province_name, region, population_m);
GO

-- bilinmiyor üyesi: il kodu çözülemeyen bir müşteri her bölgesel görselden
-- düşmek yerine yine de bir bölgeye bağlansın diye.
INSERT INTO gold.ref_province (province_code, province_name, region, population_m)
VALUES ('-1', 'Bilinmiyor', 'Bilinmiyor', NULL);
GO
