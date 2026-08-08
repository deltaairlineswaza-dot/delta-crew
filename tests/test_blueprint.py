import unittest

from training_blueprint import (
    ACTUAL_ROLE_NAMES,
    CATEGORY_SPECS,
    LEADERSHIP_ROLE_NAMES,
    ROLE_SPECS,
    all_channel_specs,
)


class BlueprintTests(unittest.TestCase):
    def test_role_names_are_unique_and_coloured(self) -> None:
        names = [role.name for role in ROLE_SPECS]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(role.colour > 0 for role in ROLE_SPECS))
        self.assertTrue(set(LEADERSHIP_ROLE_NAMES).issubset(ACTUAL_ROLE_NAMES))

    def test_category_and_local_channel_names_are_unique(self) -> None:
        category_names = [category.name for category in CATEGORY_SPECS]
        self.assertEqual(len(category_names), len(set(category_names)))
        for category in CATEGORY_SPECS:
            with self.subTest(category=category.name):
                names = [channel.name for channel in category.channels]
                self.assertEqual(len(names), len(set(names)))

    def test_requested_discussion_channels_are_forums(self) -> None:
        forum_categories = {
            category.key
            for category, channel in all_channel_specs()
            if channel.kind == "forum"
        }
        self.assertEqual(
            forum_categories,
            {
                "flight_deck",
                "cabin_crew",
                "ground_crew",
                "customer_service",
            },
        )
        forums = [
            channel for _, channel in all_channel_specs() if channel.kind == "forum"
        ]
        self.assertEqual(len(forums), 14)
        self.assertTrue(
            all(channel.name.startswith("section-") for channel in forums)
        )

    def test_department_information_channels_are_read_only(self) -> None:
        department_categories = CATEGORY_SPECS[1:7]
        for category in department_categories:
            with self.subTest(category=category.name):
                information = category.channels[0]
                self.assertEqual(information.policy, "department_information")
                self.assertTrue(information.name.endswith("-information"))

    def test_expected_blueprint_size(self) -> None:
        self.assertEqual(len(ROLE_SPECS), 64)
        self.assertEqual(len(CATEGORY_SPECS), 9)
        self.assertEqual(len(all_channel_specs()), 49)


if __name__ == "__main__":
    unittest.main()

