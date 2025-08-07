# End-to-End Test Coverage for LRU Eviction

This document details the comprehensive end-to-end test coverage for the LRU eviction mechanism, ensuring complete validation from client requests to actual sandbox management.

## Test Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │───▶│   MCP Server    │───▶│ MicrosandboxWrapper │───▶│ Microsandbox    │
│   (