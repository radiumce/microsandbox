# Python SDK Image

This directory contains the Dockerfile for the Python SDK image used with microsandbox.

## Features

- Latest Python version
- Common Python development packages pre-installed
- microsandbox-portal service with Python REPL support
- Non-root user for improved security

## Building the Image（Final successful build command use Dockerfile not Dockerfile.local）

docker build --platform linux/arm64 -t microsandbox/python:latest -f Dockerfile .

