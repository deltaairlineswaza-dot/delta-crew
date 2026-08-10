"""Declarative PROPEL training-server blueprint.

Increment ``BLUEPRINT_VERSION`` whenever a managed role, category, channel, or
permission policy changes.  The setup command uses the version to decide when
its previously-created resources need to be replaced.
"""

from __future__ import annotations

from dataclasses import dataclass

BLUEPRINT_VERSION = "2026.08.10.1"


@dataclass(frozen=True, slots=True)
class RoleSpec:
    name: str
    colour: int
    group: str
    decorative: bool = False


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    name: str
    kind: str  # text, forum, or voice
    policy: str


@dataclass(frozen=True, slots=True)
class CategorySpec:
    key: str
    name: str
    audience_role_names: tuple[str, ...]
    staff_role_names: tuple[str, ...]
    channels: tuple[ChannelSpec, ...]


COLOURS = {
    "leadership": 0xF1C40F,
    "trainers": 0x2ECC71,
    "evaluators": 0x9B59B6,
    "flight_deck": 0x3498DB,
    "cabin_crew": 0xE84393,
    "ground_crew": 0xE67E22,
    "customer_service": 0x1ABC9C,
    "tsa": 0x34495E,
    "atc": 0x5865F2,
    "status": 0x95A5A6,
    "alumni": 0xF39C12,
}


def _role_group(
    heading: str,
    group: str,
    names: tuple[str, ...],
    *,
    colour: int | None = None,
) -> tuple[RoleSpec, ...]:
    group_colour = colour if colour is not None else COLOURS[group]
    return (
        RoleSpec(heading, group_colour, group, decorative=True),
        *(RoleSpec(name, group_colour, group) for name in names),
    )


ROLE_SPECS: tuple[RoleSpec, ...] = (
    *_role_group(
        "🎓 ┃ PROPEL LEADERSHIP",
        "leadership",
        (
            "PROPEL | Director",
            "PROPEL | Deputy Director",
            "PROPEL | Training Management",
        ),
    ),
    *_role_group(
        "👨‍🏫 ┃ CERTIFIED TRAINERS",
        "trainers",
        (
            "Flight Deck | Certified Trainer",
            "Cabin Crew | Certified Trainer",
            "Ground Crew | Certified Trainer",
            "Customer Service | Certified Trainer",
            "TSA | Certified Trainer",
            "ATC | Certified Trainer",
        ),
    ),
    *_role_group(
        "📋 ┃ CERTIFIED EVALUATORS",
        "evaluators",
        (
            "Flight Deck | Check Pilot",
            "Cabin Crew | Evaluator",
            "Ground Crew | Evaluator",
            "Customer Service | Evaluator",
            "TSA | Evaluator",
            "ATC | Check Controller",
        ),
    ),
    *_role_group(
        "✈️ ┃ FLIGHT DECK TRAINEES",
        "flight_deck",
        (
            "Flight Deck Trainee | Section 1",
            "Flight Deck Trainee | Section 2",
            "Flight Deck Trainee | Section 3",
            "Flight Deck Trainee | Section 4",
            "Flight Deck | Line Check",
            "Flight Deck | Certified",
        ),
    ),
    *_role_group(
        "🛎️ ┃ CABIN CREW TRAINEES",
        "cabin_crew",
        (
            "Cabin Crew Trainee | Section 1",
            "Cabin Crew Trainee | Section 2",
            "Cabin Crew Trainee | Section 3",
            "Cabin Crew Trainee | Section 4",
            "Cabin Crew | Cabin Check",
            "Cabin Crew | Certified",
        ),
    ),
    *_role_group(
        "🦺 ┃ GROUND CREW TRAINEES",
        "ground_crew",
        (
            "Ground Crew Trainee | Section 1",
            "Ground Crew Trainee | Section 2",
            "Ground Crew Trainee | Section 3",
            "Ground Crew Trainee | Section 4",
            "Ground Crew | Ground Check",
            "Ground Crew | Certified",
        ),
    ),
    *_role_group(
        "🎧 ┃ CUSTOMER SERVICE TRAINEES",
        "customer_service",
        (
            "Customer Service Trainee | Section 1",
            "Customer Service Trainee | Section 2",
            "Customer Service | Service Check",
            "Customer Service | Certified",
        ),
    ),
    *_role_group(
        "🛡️ ┃ TSA TRAINEES",
        "tsa",
        (
            "TSA Trainee | Section 1",
            "TSA Trainee | Section 2",
            "TSA | Security Check",
            "TSA | Certified",
        ),
    ),
    *_role_group(
        "🗼 ┃ ATC TRAINEES",
        "atc",
        (
            "ATC Trainee | Section 1",
            "ATC Trainee | Section 2",
            "ATC Trainee | Section 3",
            "ATC Trainee | Section 4",
            "ATC | Controller Check",
            "ATC | Certified",
        ),
    ),
    *_role_group(
        "📚 ┃ TRAINING STATUS",
        "status",
        (
            "PROPEL | Trainee",
            "PROPEL | Training Scheduled",
            "PROPEL | Assessment Pending",
            "PROPEL | Retraining Required",
        ),
    ),
    *_role_group(
        "🎓 ┃ PROPEL ALUMNI",
        "alumni",
        (
            "PROPEL | Graduate",
            "PROPEL | Alumni",
        ),
    ),
)


LEADERSHIP_ROLE_NAMES = (
    "PROPEL | Director",
    "PROPEL | Deputy Director",
    "PROPEL | Training Management",
)

TRAINER_ROLE_NAMES = tuple(
    role.name for role in ROLE_SPECS if role.group == "trainers" and not role.decorative
)
EVALUATOR_ROLE_NAMES = tuple(
    role.name for role in ROLE_SPECS if role.group == "evaluators" and not role.decorative
)
STAFF_ROLE_NAMES = TRAINER_ROLE_NAMES + EVALUATOR_ROLE_NAMES
ALUMNI_ROLE_NAMES = ("PROPEL | Graduate", "PROPEL | Alumni")
ACTUAL_ROLE_NAMES = tuple(role.name for role in ROLE_SPECS if not role.decorative)


FLIGHT_DECK_ROLES = (
    "Flight Deck | Certified Trainer",
    "Flight Deck | Check Pilot",
    "Flight Deck Trainee | Section 1",
    "Flight Deck Trainee | Section 2",
    "Flight Deck Trainee | Section 3",
    "Flight Deck Trainee | Section 4",
    "Flight Deck | Line Check",
    "Flight Deck | Certified",
)
CABIN_CREW_ROLES = (
    "Cabin Crew | Certified Trainer",
    "Cabin Crew | Evaluator",
    "Cabin Crew Trainee | Section 1",
    "Cabin Crew Trainee | Section 2",
    "Cabin Crew Trainee | Section 3",
    "Cabin Crew Trainee | Section 4",
    "Cabin Crew | Cabin Check",
    "Cabin Crew | Certified",
)
GROUND_CREW_ROLES = (
    "Ground Crew | Certified Trainer",
    "Ground Crew | Evaluator",
    "Ground Crew Trainee | Section 1",
    "Ground Crew Trainee | Section 2",
    "Ground Crew Trainee | Section 3",
    "Ground Crew Trainee | Section 4",
    "Ground Crew | Ground Check",
    "Ground Crew | Certified",
)
CUSTOMER_SERVICE_ROLES = (
    "Customer Service | Certified Trainer",
    "Customer Service | Evaluator",
    "Customer Service Trainee | Section 1",
    "Customer Service Trainee | Section 2",
    "Customer Service | Service Check",
    "Customer Service | Certified",
)
TSA_ROLES = (
    "TSA | Certified Trainer",
    "TSA | Evaluator",
    "TSA Trainee | Section 1",
    "TSA Trainee | Section 2",
    "TSA | Security Check",
    "TSA | Certified",
)
ATC_ROLES = (
    "ATC | Certified Trainer",
    "ATC | Check Controller",
    "ATC Trainee | Section 1",
    "ATC Trainee | Section 2",
    "ATC Trainee | Section 3",
    "ATC Trainee | Section 4",
    "ATC | Controller Check",
    "ATC | Certified",
)


def _department(
    key: str,
    name: str,
    audience: tuple[str, ...],
    staff: tuple[str, ...],
    information: str,
    sections: tuple[str, ...],
    results: str,
    voice: str,
    *,
    discussion_sections: bool,
) -> CategorySpec:
    section_kind = "forum" if discussion_sections else "text"
    section_policy = "discussion" if discussion_sections else "chat"
    return CategorySpec(
        key=key,
        name=name,
        audience_role_names=audience,
        staff_role_names=staff,
        channels=(
            ChannelSpec(information, "text", "department_information"),
            *(ChannelSpec(section, section_kind, section_policy) for section in sections),
            ChannelSpec(results, "text", "department_results"),
            ChannelSpec(voice, "voice", "voice"),
        ),
    )


CATEGORY_SPECS: tuple[CategorySpec, ...] = (
    CategorySpec(
        key="information",
        name="🎓 PROPEL | INFORMATION",
        audience_role_names=ACTUAL_ROLE_NAMES,
        staff_role_names=(),
        channels=(
            ChannelSpec("welcome", "text", "read_only"),
            ChannelSpec("training-information", "text", "read_only"),
            ChannelSpec("announcements", "text", "read_only"),
            ChannelSpec("training-schedule", "text", "read_only"),
            ChannelSpec("support", "text", "chat"),
        ),
    ),
    _department(
        "flight_deck",
        "✈️ PROPEL | FLIGHT DECK",
        FLIGHT_DECK_ROLES,
        ("Flight Deck | Certified Trainer", "Flight Deck | Check Pilot"),
        "fd-information",
        (
            "section-1・indoctrination",
            "section-2・aircraft-qualification",
            "section-3・simulator-training",
            "section-4・operating-experience",
        ),
        "fd-results",
        "Flight Deck Training",
        discussion_sections=True,
    ),
    _department(
        "cabin_crew",
        "🛎️ PROPEL | CABIN CREW",
        CABIN_CREW_ROLES,
        ("Cabin Crew | Certified Trainer", "Cabin Crew | Evaluator"),
        "cc-information",
        (
            "section-1・indoctrination",
            "section-2・cabin-safety",
            "section-3・practical-training",
            "section-4・operating-experience",
        ),
        "cc-results",
        "Cabin Crew Training",
        discussion_sections=True,
    ),
    _department(
        "ground_crew",
        "🦺 PROPEL | GROUND CREW",
        GROUND_CREW_ROLES,
        ("Ground Crew | Certified Trainer", "Ground Crew | Evaluator"),
        "gc-information",
        (
            "section-1・introduction",
            "section-2・ramp-procedures",
            "section-3・practical-training",
            "section-4・operating-experience",
        ),
        "gc-results",
        "Ground Crew Training",
        discussion_sections=True,
    ),
    _department(
        "customer_service",
        "🎧 PROPEL | CUSTOMER SERVICE",
        CUSTOMER_SERVICE_ROLES,
        ("Customer Service | Certified Trainer", "Customer Service | Evaluator"),
        "cs-information",
        ("section-1・service-basics", "section-2・practical-training"),
        "cs-results",
        "Customer Service Training",
        discussion_sections=True,
    ),
    _department(
        "tsa",
        "🛡️ PROPEL | TSA",
        TSA_ROLES,
        ("TSA | Certified Trainer", "TSA | Evaluator"),
        "tsa-information",
        ("section-1・security-basics", "section-2・practical-training"),
        "tsa-results",
        "TSA Training",
        discussion_sections=False,
    ),
    _department(
        "atc",
        "🗼 PROPEL | ATC",
        ATC_ROLES,
        ("ATC | Certified Trainer", "ATC | Check Controller"),
        "atc-information",
        (
            "section-1・atc-basics",
            "section-2・ground-delivery",
            "section-3・tower",
            "section-4・approach",
        ),
        "atc-results",
        "ATC Training",
        discussion_sections=False,
    ),
    CategorySpec(
        key="staff",
        name="👨‍🏫 PROPEL | STAFF",
        audience_role_names=STAFF_ROLE_NAMES,
        staff_role_names=STAFF_ROLE_NAMES,
        channels=(
            ChannelSpec("staff-chat", "text", "chat"),
            ChannelSpec("training-records", "text", "staff_log"),
            ChannelSpec("certification-logs", "text", "staff_log"),
            ChannelSpec("Trainer Office", "voice", "voice"),
        ),
    ),
    CategorySpec(
        key="alumni",
        name="🎓 PROPEL | ALUMNI",
        audience_role_names=ALUMNI_ROLE_NAMES,
        staff_role_names=(),
        channels=(
            ChannelSpec("alumni-chat", "text", "chat"),
            ChannelSpec("graduation-board", "text", "read_only"),
        ),
    ),
)


def all_channel_specs() -> tuple[tuple[CategorySpec, ChannelSpec], ...]:
    return tuple(
        (category, channel)
        for category in CATEGORY_SPECS
        for channel in category.channels
    )


def channel_key(category: CategorySpec, channel: ChannelSpec) -> str:
    return f"{category.key}::{channel.name}"

