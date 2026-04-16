from __future__ import annotations

import time

from django.conf import settings
from django.core.management.base import BaseCommand

from portal.assessment_services import (
    claim_next_zero_trust_run,
    mark_stale_zero_trust_runs,
    process_zero_trust_run,
    worker_identity,
)


class Command(BaseCommand):
    help = "Runs the PostgreSQL-backed Zero Trust assessment worker loop."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one queued assessment run and then exit.",
        )
        parser.add_argument(
            "--poll-interval",
            type=int,
            default=settings.ASSESSMENT_WORKER_POLL_INTERVAL_SECONDS,
            help="Seconds to wait between queue polls.",
        )

    def handle(self, *args, **options) -> None:
        worker_id = worker_identity()
        poll_interval = max(1, int(options["poll_interval"]))
        run_once = bool(options["once"])

        self.stdout.write(self.style.NOTICE(f"Starting assessment worker {worker_id}"))

        while True:
            stale_count = mark_stale_zero_trust_runs()
            if stale_count:
                self.stdout.write(self.style.WARNING(f"Marked {stale_count} stale assessment run(s)."))

            run = claim_next_zero_trust_run(worker_id=worker_id)
            if run is None:
                if run_once:
                    self.stdout.write("No queued assessment runs found.")
                    return
                time.sleep(poll_interval)
                continue

            self.stdout.write(f"Processing assessment run {run.external_id}")
            process_zero_trust_run(run.external_id, worker_id=worker_id)

            if run_once:
                return
