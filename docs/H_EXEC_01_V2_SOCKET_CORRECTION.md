# H-EXEC v2: bounded Unix-socket name and failure-report preservation

Run34227400959 at d6fdcba1db33e608a5976ad99127cc164755db7b failed in the repaired
technical arm before its routing intervention: Python AF_UNIX rejected the
absolute GitHub workspace socket pathname as too long. The admin socket was
created inside the container at the short mounted path; the host connect() call
used the long resolved workspace path. The job102064948320 traceback identifies
h_exec_live_v1.py:70 and OSError: AF_UNIX path too long. Subsequent compact
generation lacked proxy-routes.log because acquisition stopped before extraction.
This is an interface failure, not a negative or positive H-EXEC result.

All v1 source/config/protocol files remain unchanged. V2 supplies the socket name
relative to the unchanged process cwd, validates containment in the workspace
and its encoded length below108 bytes, and does not chdir across active threads.
No proxy, traffic, readiness, state intervention or analysis rule changes.
Bounded controls exercise absolute-to-relative conversion, containment, encoded
length and unchanged cwd. Additional compact handling retains identity, partial
acquisition/intervention/boundary metadata and an explicit failure record even
when route/native extraction is incomplete.

The [v1 scientific protocol](H_EXEC_01_PROTOCOL_V1.md), four arms, seeds,8-block
independent series, co-primary tests, effect and diagnostic thresholds are carried
forward exactly. Only adapter/module/config/workflow names, technical namespace
and repository hashes change. This correction is not a mechanism refinement.
All four technical arms are repeated with v2; v1 observations remain technical
development and add zero independent study blocks. The successful prerequisite
must have the exact v2 protocol-config digest; v1 partial qualification is not
accepted for a study dispatch. After two unproductive technical attempts, change
approach rather than repeating the same failure.

No study outcome has been collected or opened. Main campaigns remain0. Preserve
all v1 compact reports, failure log excerpt, source artifact API metadata and full
raw archives remotely, followed by all v2 attempted results. A technical pass
still does not establish the H claim or select a main model.
