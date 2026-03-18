use master;

/*
Create the database if it doesn't exist
*/

if not exists (
    select name from sys.databases
    where name = N'mvHofki'
)
create database mvHofki;

use mvHofki;

/*
Dropping existing tables if they exist
*/
drop table if exists dbo.instrument_pictures;
drop table if exists dbo.instrument_invoices;
drop table if exists dbo.instrument_files;
drop table if exists dbo.loan_register;
drop table if exists dbo.instruments;
drop table if exists dbo.musicians;
drop table if exists dbo.instrument_types;
drop table if exists dbo.currencies;
drop table if exists dbo.files;


create table dbo.files
(
    id int identity(1,1) not null,
    [file_Name] nvarchar(100),
    sub_directory nvarchar(MAX),
    created_at datetimeoffset not null default getutcdate(),
    primary key (id)
)

create table dbo.currencies
(
    id int identity(1,1) not null,
    label nvarchar(100),
    abbreviation nvarchar(100),
    primary key (id)
)

create table dbo.instrument_types
(
    id int identity(1,1) not null,
    created_at datetimeoffset not null default getutcdate(),
    label nvarchar(255),
    label_short nvarchar(100),
    primary key (id)
)

create table dbo.instruments
(
    id int identity(1,1) not null,
    label_addition nvarchar(100),
    construction_year date,
    acquisition_cost float,
    instrument_type_id int not null foreign key references dbo.instrument_types(id),
    notes nvarchar(100),
    creator_id uniqueidentifier not null default newid(),
    created_at datetimeoffset not null default getutcdate(),
    acquisition_date date,
    inventory_nr int not null,
    distributor nvarchar(100),
    currency_id int not null,
    container nvarchar(100),
    particularities nvarchar(100),
    [owner] nvarchar(100) not null,
    manufacturer nvarchar(100),
    serial_nr nvarchar(100),
    primary key (id)
)

create table dbo.musicians
(
    id int identity(1,1) not null,
    first_name nvarchar(100),
    last_name nvarchar(100),
    phone nvarchar(100),
    street_address nvarchar(100),
    creator_id uniqueidentifier not null default newid(),
    created_at datetimeoffset not null default getutcdate(),
    city nvarchar(100),
    postal_code int,
    email nvarchar(100),
    is_extern bit not null,
    notes nvarchar(Max),
    constraint musicians_first_name_check check (len(first_name) > 0),
    constraint musicians_last_name_check check (len(last_name) > 0),
    primary key (id)
)


create table dbo.loan_register
(
    id int identity(1,1) not null,
    created_at datetimeoffset not null default getutcdate(),
    [start_date] date not null,
    end_date date,
    instrument_id int not null foreign key references dbo.instruments(id),
    musician_id int not null foreign key references dbo.musicians(id),
    primary key (id)
)

create table dbo.instrument_invoices
(
    id int identity(1,1) not null,
    created_at datetimeoffset not null default getutcdate(),
    instrument_id int not null foreign key references dbo.instruments(id),
    file_id int not null foreign key references dbo.files(id),
    amount bigint,
    currency_id int not null foreign key references dbo.currencies(id),
    date_issued date,
    [description] nvarchar(100),
    invoice_issuer nvarchar(100),
    invoice_nr nvarchar(100),
    issuer_address nvarchar(100),
    primary key (id)
)

CREATE TABLE dbo.instrument_pictures
(
    id int identity(1,1) not null,
    created_at datetimeoffset not null default getutcdate(),
    instrument_id int not null foreign key references dbo.instruments(id),
    file_id int not null foreign key references dbo.files(id),

)

/*
Initializing Data
*/

SET IDENTITY_INSERT dbo.instrument_types ON;
insert into dbo.instrument_types (id, label, label_short)
VALUES
    (1,  'Querflöte', 'FL'),
    (2, 'Klarinette in Es', 'KL'),
    (3,  'Klarinette in B', 'KL'),
    (4,  'Bassklarinette', 'KL'),
    (5,  'Fagott', 'FA'),
    (6,  'Oboe', 'OB'),
    (7,  'Englischhorn (Alt-Oboe)', 'OB'),
    (8,  'Flügelhorn', 'FH'),
    (11, 'Altsaxophon', 'SA'),
    (12, 'Tenorsaxophon', 'SA'),
    (13, 'Baritonsaxophon', 'SA'),
    (9,  'Saxophon', 'SA'),
    (14, 'Trompete', 'TR'),
    (15, 'Tenorhorn', 'TE'),
    (16, 'Bariton', 'TE'),
    (17, 'Euphonium', 'TE'),
    (19, 'Posaune', 'PO'),
    (20, 'Tuba', 'TU'),
    (21, 'Schlagwerk', 'SW'),
    (18, 'Horn', 'WH');
SET IDENTITY_INSERT dbo.instrument_types OFF;

SET IDENTITY_INSERT dbo.currencies ON;
INSERT INTO dbo.currencies (id, label, abbreviation)
VALUES
    (1, 'Euro', '€'),
    (2, 'Schilling', 'ATS'),
    (3, 'Dollar', '$'),
    (4, 'Pfund', '£');
SET IDENTITY_INSERT dbo.currencies OFF;