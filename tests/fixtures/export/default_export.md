# Session Context: auth-service

**Source:** claude-code | **Date:** 2026-03-24 | **Duration:** 45min
**Turns:** 10 → 10 key turns | **~148 tokens**

## Goal

Implement the auth module with JWT support

## Current State

Next we need to add integration tests for all auth flows

## Key Decisions

1. Switch to argon2 instead, it's more secure

## What Was Done

- Add rate limiting to the login endpoint
- Use bcrypt for password hashing

## Files Changed

`src/auth.py`, `src/tokens.py`, `tests/test_auth.py`

## Resume

Next we need to add integration tests for all auth flows
