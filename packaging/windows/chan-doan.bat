@echo off
:: Vo mong goi chan-doan.ps1 de nguoi dung bam dup duoc.
:: Phan viec that nam trong file .ps1 - batch xu ly chuoi co ky tu > rat te.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chan-doan.ps1"
