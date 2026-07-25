# PPI Public Migration Scheduler Runbook

1. Review the latest readiness artifact.
2. Fix only the active task.
3. Open a focused pull request.
4. Do not activate the next task until the current task passes.
5. Advance the queue only by reviewed configuration change.
6. Keep private schedules and private dispatch disabled.

For `T01`, the next manual action is to run the current `main` version of `Bootstrap PPI public acquisition repository`, then review target pull request 1.
