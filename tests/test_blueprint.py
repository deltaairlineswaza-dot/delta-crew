from training_blueprint import (
    ACTUAL_ROLE_NAMES,
    CATEGORY_SPECS,
    LEADERSHIP_ROLE_NAMES,
    ROLE_SPECS,
    all_channel_specs,
)


def test_role_names_are_unique_and_coloured() -> None:
    names = [role.name for role in ROLE_SPECS]
    assert len(names) == len(set(names))
    assert all(role.colour > 0 for role in ROLE_SPECS)
    assert set(LEADERSHIP_ROLE_NAMES).issubset(ACTUAL_ROLE_NAMES)


def test_category_and_local_channel_names_are_unique() -> None:
    category_names = [category.name for category in CATEGORY_SPECS]
    assert len(category_names) == len(set(category_names))
    for category in CATEGORY_SPECS:
        names = [channel.name for channel in category.channels]
        assert len(names) == len(set(names)), category.name


def test_requested_discussion_channels_are_forums() -> None:
    forum_categories = {
        category.key
        for category, channel in all_channel_specs()
        if channel.kind == "forum"
    }
    assert forum_categories == {
        "flight_deck",
        "cabin_crew",
        "ground_crew",
        "customer_service",
    }
    forums = [channel for _, channel in all_channel_specs() if channel.kind == "forum"]
    assert len(forums) == 14
    assert all(channel.name.startswith("section-") for channel in forums)


def test_department_information_channels_are_read_only() -> None:
    department_categories = CATEGORY_SPECS[1:7]
    for category in department_categories:
        information = category.channels[0]
        assert information.policy == "department_information"
        assert information.name.endswith("-information")


def test_expected_blueprint_size() -> None:
    assert len(ROLE_SPECS) == 64
    assert len(CATEGORY_SPECS) == 9
    assert len(all_channel_specs()) == 49

