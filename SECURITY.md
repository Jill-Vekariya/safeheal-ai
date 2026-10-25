# Security reporting

Report suspected vulnerabilities privately using this repository's Security tab. Include the affected revision, reproduction steps, and potential impact. Do not publish credentials or exploit details in a public issue.

SafeHeal AI is an isolated research prototype. Its model cannot execute commands, access cluster credentials, approve actions, or expand the recovery catalog. Operator enrollment, OS administration, and fixture harnesses are trusted components. See docs/SAFE_RECOVERY.md for the exact boundaries and limitations.

Before publishing changes, run the checksum-pinned Gitleaks history scan. Exact historical findings in .gitleaksignore were reviewed as SHA-256 artifact digests; broad secret-rule or path exclusions are not used. Keep provider credentials, kubeconfigs, and executor tokens in ignored local directories. A clean scan does not prove that every possible secret or vulnerability is absent.
