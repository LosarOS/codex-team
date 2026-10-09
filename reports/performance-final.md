# Performance measurements

Actual FastAPI routes and SQLite, synthetic 1000-run dataset, five samples: History page median14.09ms/max14.34ms. A1000-line page from20000-line Diff median5.61ms/max5.91ms. These are local route timings, not installed UI/render benchmarks.

History summarizes/filter/paginates in SQLite. Diff and meaningful events load lazily. Project inspection caches5seconds; account status caches30seconds; SDK RPC and shutdown waits are bounded. Startup/backend/UI-ready timing and Windows125/150% scaling remain NOT TESTED for the final package.
