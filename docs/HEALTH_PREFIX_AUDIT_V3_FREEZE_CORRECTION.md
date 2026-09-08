# Prefix census v3: Git-byte freezing gate

Adapter v2 run `34217439370`, head `40bad03db620ee83eac2a92602d74afacb5585f6`, stopped at the source-lock check before any archive download. On Windows, the new Python-generated adapter/workflow had CRLF bytes; Git normalized these two files to LF. The v2 config had mistakenly frozen working-tree hashes without repeating the Git index check used for v1.

The failed v2 config and source are preserved unchanged. V3 keeps the qualified-boundary schema correction and the same decoder/census logic. It writes new source/workflow bytes with LF and changes the freezing procedure: stage source files first, compute hashes from the Git index, and require `scripts/verify_staged_research_lock.py` to pass before commit/dispatch. Source and workflow locks for v3 refer to exact Git bytes; every archive lock, census identity, correction rule and diagnostic scope is unchanged.

After two unsuccessful technical attempts, this adds an explicit local pre-dispatch gate instead of repeating the same freeze procedure. It does not relax the remote content checks. The original v1 and v2 failures remain evidence; they are not independent campaigns and produced no complete observation census. Full 168-case / 328-file coverage is still required. No fitting, outcome loading or new main campaigns is authorized by a green census.

The predeclared statistical and resource scope remains [v1](HEALTH_PREFIX_AUDIT_PROTOCOL.md), with the explicit [qualification schema correction](HEALTH_PREFIX_AUDIT_V2_CORRECTION.md). The old source files are historical records, not dependencies executed by v3. Bounded AST checks verify that corrected_signal/census/restore/qualification functions have not changed.
