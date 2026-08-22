from django.core.management.base import BaseCommand

from ratings.services import recompute_scores


class Command(BaseCommand):
    help = "Recompute denormalized rating averages and Bayesian scores (spec 3.6)."

    def handle(self, *args, **options):
        recompute_scores()
        self.stdout.write(self.style.SUCCESS("Scores recomputed."))
