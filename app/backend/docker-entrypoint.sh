#!/bin/sh
set -e

# Run migrations + vector seed before starting the service.
# The seeder short-circuits when the collection is already populated, so
# warm restarts don't pay for OpenAI embeddings.
#
# Set TALKBOX_SKIP_BOOTSTRAP=1 to bypass entirely (tests, local debugging).
if [ "${TALKBOX_SKIP_BOOTSTRAP}" != "1" ]; then
  python main.py seed
fi

exec "$@"
