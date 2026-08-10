import unittest
from unittest.mock import MagicMock

from training_blueprint import CATEGORY_SPECS, LEADERSHIP_ROLE_NAMES
from training_setup import TrainingSetupService


class DiscussionPermissionTests(unittest.TestCase):
    def test_trainees_can_reply_but_cannot_create_forum_posts(self) -> None:
        category = next(
            category
            for category in CATEGORY_SPECS
            if any(channel.policy == "discussion" for channel in category.channels)
        )
        discussion = next(
            channel for channel in category.channels if channel.policy == "discussion"
        )
        roles = {
            name: MagicMock(name=name)
            for name in {
                *category.audience_role_names,
                *category.staff_role_names,
                *LEADERSHIP_ROLE_NAMES,
            }
        }
        guild = MagicMock()
        guild.me = None

        overwrites = TrainingSetupService()._channel_overwrites(
            guild, category, discussion, None, roles, []
        )

        trainee_role_names = set(category.audience_role_names).difference(
            category.staff_role_names
        )
        for role_name in trainee_role_names:
            with self.subTest(role=role_name):
                permissions = overwrites[roles[role_name]]
                self.assertFalse(permissions.send_messages)
                self.assertTrue(permissions.send_messages_in_threads)
                self.assertFalse(permissions.create_public_threads)
                self.assertFalse(permissions.create_private_threads)

        for role_name in category.staff_role_names:
            with self.subTest(role=role_name):
                permissions = overwrites[roles[role_name]]
                self.assertTrue(permissions.send_messages)
                self.assertTrue(permissions.send_messages_in_threads)
                self.assertTrue(permissions.create_public_threads)
                self.assertTrue(permissions.manage_threads)


if __name__ == "__main__":
    unittest.main()
