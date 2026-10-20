# Talent Academy LMS

A full learning-management platform for **Talent Academy** supporting high-school students preparing for EST, SAT, ACT and related courses.

## Overview

The platform includes student, admin and academic-management workflows in one system, with course delivery, attendance, exams, reports, points, announcements and subscription management.

## Core Features

### Students

- Student ID based access
- Academy and External student types
- Subscription states: Active, Pending, Expired and Suspended
- Course enrollment and progress tracking
- Recorded lessons
- Live-session access and attendance
- Online exams with image-based questions and answer choices
- Autosaving exam answers
- Server-authoritative exam timer
- Exam attempt recovery and admin unlock flow
- Points and leaderboard system
- Calendar and notifications
- Student performance views

### Admin

- Student management and search
- Course and lesson management
- Custom groups and course assignments
- Live-session management
- Attendance sheets and finalization
- Exam builder with questions, passages and answer keys
- Exam-attempt management
- Reports with Excel and PDF export
- Admin dashboard with platform statistics
- Announcements and notifications
- Admin account management
- Audit log

## Technical Stack

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- TanStack Query

### Backend

- FastAPI
- Python
- SQLAlchemy
- Alembic
- Pydantic

### Data & Infrastructure

- PostgreSQL
- Docker
- S3-compatible object storage / MinIO for local development
- Production-ready reverse-proxy and deployment configuration

## Project Status

The platform has progressed through the main student and admin feature phases, including courses, attendance, exams, reports, dashboards and deployment preparation.

Production deployment configuration has been prepared and tested locally; this repository itself should not be treated as proof that the latest build is currently deployed to a public production server.

## Local Development

```bash
docker compose -f docker-compose.dev.yml up
```

This starts the PostgreSQL database, local object storage, backend and frontend development services.

Frontend: `http://localhost:3000`  
Backend API docs: `http://localhost:8000/docs`

## Documentation

Detailed technical documentation is available in:

- `docs/ARCHITECTURE.md`
- `docs/DESIGN.md`
- `docs/DEPLOYMENT.md`

## Security

The platform includes role-based access control, server-side authorization checks, rate limiting, CSRF protections, controlled exam-attempt access and production configuration validation.
