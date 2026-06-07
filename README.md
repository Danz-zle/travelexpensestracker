# Travel Expense Tracker

## Project Overview

Travel Expense Tracker is a dual-platform chatbot running on:

* Telegram
* LINE

It helps users:

### Module A – Smart Shopping

Compare overseas prices against Taiwan reference prices.

Features:

* Currency conversion
* Taiwan price database
* BUY / NORMAL / DON'T BUY recommendations
* Multi-currency support

### Module B – Expense Tracking

Track travel and daily expenses.

Features:

* Daily mode
* Trip mode
* Budget management
* Expense summaries
* Recent expense review
* Expense deletion
* Trip deletion

---

# Architecture

## Frontend

Telegram Bot

LINE Bot

## Backend

Render

Python Flask

## Database

Google Sheets

## API Layer

Google Apps Script Web App

---

# Project Structure

```text
app.py

config.py
state.py

command_aliases.py

currency_utils.py
sheets_api.py
formatters.py

commands/
├── __init__.py
├── utility.py
├── shopping.py
├── expenses.py
├── trips.py

services/
(data reserved)

data/
(reserved)

exchange.py
evaluator.py

requirements.txt
```

# Google Sheets Tabs

## TaiwanPrices

Stores Taiwan reference prices.

Columns:

* Item
* Taiwan Price
* Updated Time

---

## Expenses

Stores expense records.

Columns:

* Timestamp
* User Key
* Trip Name
* Platform
* Item
* Currency
* Original Price
* Converted TWD

---

## Budgets

Stores budget by trip.

Columns:

* User Key
* Trip Name
* Budget TWD

---

## Trips

Stores trip information.

Columns:

* User Key
* Trip Name
* Active Flag

---

# Commands

## General

START

HELP

STATUS

RATE USD

RATE JPY

RATE CNY

---

# Module A – Smart Shopping

## Compare Price

Example:

AirPods Pro USD 199

Result:

* Converted TWD
* Taiwan Price
* BUY / NORMAL / DON'T BUY

---

## Add Taiwan Price

ADDPRICE AirPods Pro 7490

Bulk:

ADDPRICE

AirPods Pro 7490

Sony XM6 10990

---

## Update Taiwan Price

UPDATEPRICE AirPods Pro 6990

---

## Delete Taiwan Price

DELETEPRICE AirPods Pro

---

## List Database

LISTPRICE

---

## Quick Taiwan Price Save

TWPRICE 7490

---

# Module B – Expense Tracking

## Daily Mode

USEDEFAULT

All expenses are stored in:

Default

---

## Create Trip

NEWTRIP Japan Okinawa Jun 2026

---

## View Buckets

MYTRIPS

---

## Record Expense

SPENT Lunch MYR 59.9

SPENT Flight TWD 17000

---

## Bulk Expense

SPENT

Lunch MYR 59.9

Taxi MYR 20

Coffee TWD 80

---

## Set Budget

BUDGET 30000

---

## View Expense Summary

EXPENSE

Alias:

EXP

SUMMARY

---

## Recent Expenses

RECENT

RECENT 20

Aliases:

LAST

LATEST

---

## Delete Expense

DELETEEXPENSE 2

Confirm:

YESDELETE

Cancel:

CANCEL

Aliases:

DELEXPENSE

DELEXP

DELETE EXPENSE

---

## Delete Trip

DELETETRIP Japan Okinawa Jun 2026

Confirm:

CONFIRMDELETE

Cancel:

CANCEL

---

# Supported Currencies

TWD

JPY

USD

EUR

KRW

HKD

SGD

MYR

THB

VND

PHP

KHR

CNY

Supported aliases:

RMB

YUAN

人民幣

---

# Current Version

Version 2.1

Modules:

✅ Smart Shopping

✅ Expense Tracking

Upcoming:

🔜 Wishlist

🔜 OCR Receipt Capture

🔜 Daily Reports

🔜 Monthly Reports

🔜 Analytics Dashboard
