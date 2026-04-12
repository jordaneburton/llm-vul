# Security Prompt Experiment

## Overview

This experiment compares two types of prompts for fixing vulnerable Java code:

1. Baseline prompt
2. Security-aware prompt (with CWE information)

## Goal

To test whether adding security context improves the quality of AI-generated fixes.

## Example

The current example demonstrates a Java code snippet with a potential bug and generates:

- A basic repair prompt
- A security-aware prompt with CWE-480

## Next Steps

- Add more vulnerability examples
- Test with an AI model
- Compare results
