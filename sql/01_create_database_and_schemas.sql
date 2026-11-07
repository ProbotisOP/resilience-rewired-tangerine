-- 01_create_database_and_schemas.sql
-- Sheridan Datathon 2026 - Tangerine Track: Resilience Rewired
-- Creates the RESILIENCE_REWIRED database and layered architectural schemas.

CREATE DATABASE IF NOT EXISTS RESILIENCE_REWIRED
    COMMENT = 'Tangerine Financial Resilience Intelligence Platform Database';

USE DATABASE RESILIENCE_REWIRED;

-- 1. RAW Schema: Direct landing for supplied CSV tables
CREATE SCHEMA IF NOT EXISTS RAW
    COMMENT = 'Raw landing zone for anonymized retail banking CSVs';

-- 2. CORE Schema: Normalized, dimensional star/snowflake model
CREATE SCHEMA IF NOT EXISTS CORE
    COMMENT = 'Core dimensional model (Conformed Dims, Facts, and Bridge tables)';

-- 3. MART Schema: Curated analytical aggregates and feature stores
CREATE SCHEMA IF NOT EXISTS MART
    COMMENT = 'Curated business marts, baselines, and shock exposure stores';

-- 4. SEMANTIC Schema: Cortex Semantic Views and governed metrics
CREATE SCHEMA IF NOT EXISTS SEMANTIC
    COMMENT = 'Governed semantic layer for Cortex Analyst and executive Q&A';
