@echo off
cd /d "%~dp0"
python data_ingest.py >> ingest_log.txt 2>&1