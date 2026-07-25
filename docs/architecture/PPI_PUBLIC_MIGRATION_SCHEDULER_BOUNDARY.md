# PPI Scheduler Authority Boundary

The scheduler may read public repository metadata, validate the current gate, and publish a report artifact.

It may not:

- use provider credentials;
- collect or retry provider data;
- write to `ppi-data-acquisition`;
- read or dispatch `ai-signal-engine`;
- merge pull requests;
- mutate the registry;
- publish production data;
- authorize broker, order, trading, MMM/raw-data, or R12 actions.

Any future increase in authority requires a reviewed contract revision and pull request.
