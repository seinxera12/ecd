# Comprehensive Codebase Analysis & Documentation Generation

You are acting as a **Senior Software Architect**, **Technical Writer**, and **Lead Engineer** performing a complete project handover.

## Objective

You have been given an existing project that contains **little or no documentation**. Your task is to thoroughly understand the project before documenting it.

Do **NOT** simply describe files individually.

Instead, reverse engineer the entire system, understand how everything works together, then produce documentation that would allow a new developer to confidently continue development without assistance.

---

# Phase 1 — Understand the Entire Codebase

Before writing anything, analyze the entire repository.

Build a complete mental model of:

* project architecture
* execution flow
* application lifecycle
* business logic
* module interactions
* dependencies
* configuration
* data flow
* build process
* deployment assumptions
* runtime behavior

Traverse every directory and inspect:

* source code
* configuration files
* package manifests
* dependency files
* Docker files
* CI/CD files
* environment variable usage
* scripts
* build tooling
* assets
* database schema/migrations
* APIs
* tests
* infrastructure files

Do NOT skip directories simply because they appear unimportant.

Infer undocumented behavior from the implementation.

If there are generated files, identify what generates them.

If there are multiple applications (frontend/backend/workers/services), understand how they communicate.

---

# Phase 2 — Build an Internal Architecture Model

Construct an internal understanding of:

## High-Level Architecture

Identify:

* application type
* architectural style
* major layers
* bounded contexts
* services
* packages
* modules

Determine whether it follows patterns such as:

* MVC
* MVVM
* Clean Architecture
* Hexagonal Architecture
* Onion Architecture
* Layered Architecture
* Feature-based Architecture
* Microservices
* Modular Monolith
* Event-driven Architecture
* CQRS
* Repository Pattern
* Domain Driven Design
* or a custom architecture.

Explain the actual architecture implemented—not what it resembles superficially.

---

## Application Startup Flow

Determine:

Where execution begins.

Examples:

* main()
* index.js
* server.ts
* App.tsx
* main.py
* entrypoint
* CLI launcher

Trace execution until the application is fully initialized.

Explain:

* initialization order
* dependency initialization
* configuration loading
* service registration
* middleware setup
* routing initialization
* database initialization
* cache initialization
* authentication setup
* background jobs
* websocket setup
* scheduler initialization

---

## Runtime Flow

Understand:

What happens after startup.

Trace:

User request

↓

Router

↓

Controller

↓

Business logic

↓

Services

↓

Repositories

↓

Database

↓

Response

or equivalent architecture.

Explain every major runtime flow.

---

## Data Flow

Understand how data moves.

Document:

* inputs
* validation
* transformation
* storage
* retrieval
* caching
* serialization
* API responses

Follow data from entry to persistence and back.

---

## State Management

If frontend exists:

Determine:

* React Context
* Redux
* Zustand
* MobX
* Vuex
* Signals
* local state
* server state
* query libraries

Explain how state changes over time.

---

## Backend Logic

Identify:

* controllers
* services
* repositories
* middleware
* authentication
* authorization
* validation
* ORM usage
* transactions
* background processing
* queues
* caching

---

## Frontend Logic

Determine:

* routing
* layouts
* pages
* reusable components
* API layer
* hooks
* contexts
* stores
* forms
* navigation
* UI architecture

Explain how pages are rendered and updated.

---

## Database

Determine:

* database type
* schema
* relationships
* migrations
* indexing
* models
* ORM
* query builder
* repositories

Explain how persistence works.

---

## APIs

Document:

every endpoint.

Include:

* URL
* method
* purpose
* request format
* response format
* authentication
* validation
* business logic involved

---

## External Services

Identify integrations with:

* cloud providers
* storage
* authentication providers
* email
* payment gateways
* AI services
* messaging
* analytics
* monitoring
* third-party APIs

Explain:

why they exist

how they are used

what data is exchanged

---

## Configuration

Find every configuration source.

Examples:

.env

config/

settings

constants

build configs

vite

webpack

docker

compose

nginx

CI

GitHub Actions

package scripts

Explain what each configuration controls.

---

## Dependencies

Analyze dependencies.

Explain:

Why each major dependency exists.

Group them by purpose.

Example:

Frontend

Backend

Database

Authentication

Networking

Visualization

Testing

Build

Linting

Formatting

Development

---

## Design Patterns

Identify patterns actually implemented.

Examples:

Repository

Factory

Strategy

Singleton

Dependency Injection

Observer

Adapter

Facade

Command

Decorator

State

Builder

Explain where and why each pattern is used.

---

## Algorithms

Identify any important algorithms.

Examples:

search

routing

navigation

graph algorithms

sorting

filtering

recommendation

optimization

Explain their implementation.

---

## Security

Identify:

authentication

authorization

JWT

OAuth

sessions

CSRF

CORS

rate limiting

validation

sanitization

permissions

roles

encryption

secret management

---

## Error Handling

Explain:

logging

exception handling

retry mechanisms

fallbacks

timeouts

user-facing errors

---

## Performance

Identify:

lazy loading

memoization

virtualization

caching

debouncing

throttling

batching

pagination

query optimization

background processing

parallelization

---

# Phase 3 — Produce Documentation

Generate **exactly two Markdown files**.

---

# File 1

implementation.md

This is a developer-oriented implementation document.

It should include:

# Project Overview

Purpose

Goals

Problem solved

High-level architecture

Technology stack

Repository structure

---

# System Architecture

Detailed architecture diagrams (Mermaid where appropriate)

Module dependency diagrams

Application flow diagrams

Sequence diagrams

Data flow diagrams

Request lifecycle diagrams

Initialization flow

Folder relationships

---

# Repository Structure

Explain every significant folder.

Explain why it exists.

Explain interactions between folders.

---

# Component Documentation

Document every important module.

For each:

Purpose

Responsibilities

Key classes/functions

Dependencies

Used by

Uses

Important implementation details

Extension points

---

# Runtime Lifecycle

Startup

Initialization

Runtime

Shutdown

---

# Business Logic

Explain every significant feature.

Not just what it does—

Explain HOW it works internally.

---

# Data Model

Entities

Relationships

Persistence

Validation

Transformations

---

# API Documentation

Endpoints

Payloads

Authentication

Flow

Internal execution

---

# Configuration

Every config file

Every environment variable

Purpose

Default behavior

Effects

---

# Framework Usage

Explain how each framework/library is used in THIS project.

Not generic documentation.

---

# Design Decisions

Infer architectural decisions.

Explain tradeoffs where evident.

---

# Development Workflow

How new features should be added.

How existing ones are modified.

Coding conventions observed.

Architectural conventions.

Common pitfalls.

---

# Known Technical Debt

Infer:

tight coupling

duplication

complexity

fragile areas

missing abstractions

improvement opportunities

Clearly separate facts from inferred observations.

---

# File 2

setup.md

A complete developer onboarding guide.

It should allow a new developer to clone the project and run it successfully.

Include:

# Prerequisites

Operating systems

Languages

SDK versions

Package managers

Databases

Runtime requirements

Tools

Editors

Extensions

---

# Installation

Clone

Dependencies

Package installation

Environment variables

Configuration

Secrets

Database setup

Migrations

Seed data

Assets

---

# Running the Project

Development mode

Production mode

Debug mode

Hot reload

Watch mode

---

# Build Process

Explain:

what happens

where outputs go

important scripts

---

# Environment Variables

Create a table:

Variable

Purpose

Required?

Default

Example

Inferred usage

---

# Database Setup

Installation

Initialization

Migration

Reset

Seed

Backup

Restore

---

# Troubleshooting

Common errors

Likely causes

Solutions

Dependency issues

Port conflicts

Database issues

Environment issues

Build failures

---

# Useful Commands

List every useful command.

Explain what it does.

---

# Testing

How tests are run.

Frameworks used.

Coverage.

Test structure.

---

# Debugging

Recommended IDE settings.

Breakpoints.

Logging.

Useful scripts.

---

# Development Workflow

Recommended workflow.

Branching assumptions.

Build order.

Development cycle.

---

# Final Requirements

* Base every statement on actual code whenever possible.
* Clearly distinguish confirmed facts from reasonable inferences.
* Do not invent undocumented behavior.
* Include Mermaid diagrams wherever they improve understanding.
* Cross-reference related sections to avoid duplication.
* Use clear Markdown headings, tables, code blocks, and callouts for readability.
* Treat the output as professional engineering documentation suitable for long-term maintenance and onboarding.
* The documentation should be comprehensive enough that a developer unfamiliar with the project can understand the implementation, confidently set up a local development environment, and begin making changes safely.
