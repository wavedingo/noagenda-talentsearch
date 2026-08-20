from django.test import TestCase

from accounts.models import User
from candidates.models import Candidate, Demo


class CandidateModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="candidate@example.com")

    def test_create_candidate_defaults_to_pending(self):
        candidate = Candidate.objects.create(user=self.user, stage_name="The Contender")
        self.assertEqual(candidate.status, Candidate.Status.PENDING)
        self.assertFalse(candidate.is_featured)

    def test_one_candidate_per_user(self):
        from django.db import IntegrityError

        Candidate.objects.create(user=self.user, stage_name="First")
        with self.assertRaises(IntegrityError):
            Candidate.objects.create(user=self.user, stage_name="Second")

    def test_create_demo_defaults_to_pending(self):
        candidate = Candidate.objects.create(user=self.user, stage_name="The Contender")
        demo = Demo.objects.create(candidate=candidate, original_path="s3://bucket/demo1.mp3")
        self.assertEqual(demo.status, Demo.Status.PENDING)

    def test_candidate_can_have_multiple_demos(self):
        candidate = Candidate.objects.create(user=self.user, stage_name="The Contender")
        Demo.objects.create(candidate=candidate, original_path="s3://bucket/demo1.mp3", status=Demo.Status.ARCHIVED)
        Demo.objects.create(candidate=candidate, original_path="s3://bucket/demo2.mp3")
        self.assertEqual(candidate.demos.count(), 2)
