# Security Prompt Experiment

## Overview
This experiment compares two prompt styles for fixing vulnerable Java code:

1. Baseline prompt
2. Security-aware prompt with CWE context

## Goal
The goal is to test whether adding security information, such as CWE ID and description, improves the quality of AI-generated vulnerability fixes.

## Current Prototype
The current prototype includes 3 Java vulnerability examples:

- Incorrect string comparison
- Improper input validation
- Hardcoded password

For each example, the program generates:
- a baseline repair prompt
- a security-aware repair prompt
