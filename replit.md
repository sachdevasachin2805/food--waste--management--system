# Food Wastage Management System

A Streamlit-based web application for managing food waste by connecting food providers with receivers.

## Overview

- **Framework**: Streamlit (Python)
- **Database**: PostgreSQL (Replit built-in, accessed via DATABASE_URL)
- **Port**: 5000

## Architecture

Single-file app (`app.py`) with:
- Dashboard with real-time metrics and charts
- Food item management (add, browse, claim)
- Provider and receiver management
- Claims tracking
- Analytics and data quality views

## Database Schema

Four tables:
- `providers` — food donors/providers
- `food_items` — available food listings
- `receivers` — food recipients/beneficiaries
- `claims` — food claim/pickup records

## Running the App

The workflow "Start application" runs:
```
streamlit run app.py --server.port 5000 --server.address 0.0.0.0 --server.headless true
```

## Environment Variables

- `DATABASE_URL` — PostgreSQL connection string (set automatically by Replit)
