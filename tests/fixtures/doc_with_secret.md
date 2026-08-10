# Documentation With Sensitive Content (Test Fixture)

This file intentionally contains a fake token pattern for secret-scanning tests.
Do NOT use this file outside of the test fixtures directory.

## Warning

The following value is a synthetic token that matches the GitHub PAT regex pattern.
It is not a real credential and has never been valid.

## Test Data

Fake token: ghp_abcdefghijklmnopqrstuvwxyz1234567890

The scanner should detect the pattern above and flag this file.
