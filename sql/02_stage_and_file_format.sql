-- 02_stage_and_file_format.sql
USE DATABASE RESILIENCE_REWIRED;
USE SCHEMA RAW;

-- Create standard CSV file format
CREATE OR REPLACE FILE FORMAT CSV_BANKING_FORMAT
    TYPE = 'CSV'
    COMPRESSION = 'AUTO'
    FIELD_DELIMITER = ','
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    TRIM_SPACE = TRUE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
    NULL_IF = ('', 'NULL', 'null', 'NaN', 'nan');

-- Create named internal stage for CSV ingestion
CREATE OR REPLACE STAGE BANKING_DATA_STAGE
    FILE_FORMAT = CSV_BANKING_FORMAT
    COMMENT = 'Internal stage for Tangerine datathon CSV files';
