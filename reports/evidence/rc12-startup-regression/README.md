# Startup transport regression — source68d0ad8

Initial checking, independent backend health, delayed/failed SDK status, auth-unknown gating, known auth-required, unchanged live-region identity and old health response ordering are covered. Root reran all16Node suites with the repository static-directory argument and the full Python suite:1038passed/4skipped/0failed.

[Real browser workflow checks](../../rc12/startup-fixed-browser/results.json) and [18-combination theme matrix](../../rc12/startup-fixed-browser/themes/results.json) use an isolated real FastAPI/SQLite fixture with live SDK inference forbidden. Eight browser checks and108layout checks passed; these are not additional unique Python tests. Original component/browser/Windows source IDs are recorded separately. Physical Windows/DPI/liveSDK are not proven by these Linux results.
