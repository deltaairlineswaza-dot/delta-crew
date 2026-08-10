"""Implementation of the ``/training setup`` command."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from training_blueprint import (
    BLUEPRINT_VERSION,
    CATEGORY_SPECS,
    LEADERSHIP_ROLE_NAMES,
    ROLE_SPECS,
    SERVER_NAME,
    CategorySpec,
    ChannelSpec,
    all_channel_specs,
    channel_key,
)

REASON = f"PROPEL training setup blueprint {BLUEPRINT_VERSION}"
STATE_FILE = Path(
    os.getenv("TRAINING_SETUP_STATE_FILE", "data/training_setup_state.json")
)


class SetupError(RuntimeError):
    """A safe, user-presentable setup failure."""


@dataclass(slots=True)
class PreviewReport:
    role_create: int = 0
    role_reuse: int = 0
    category_create: int = 0
    category_reuse: int = 0
    channel_create: int = 0
    channel_reuse: int = 0
    replacement_count: int = 0
    replacing_previous_version: str | None = None
    global_role_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ApplyResult:
    created_roles: int = 0
    reused_roles: int = 0
    created_categories: int = 0
    reused_categories: int = 0
    created_channels: int = 0
    reused_channels: int = 0
    restored_assignments: int = 0
    warnings: list[str] = field(default_factory=list)


class StateStore:
    """Small atomic JSON store recording only bot-managed Discord object IDs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"guilds": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SetupError(f"Could not read the setup ownership ledger: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("guilds"), dict):
            raise SetupError("The setup ownership ledger has an invalid format.")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self.path)

    async def get_guild(self, guild_id: int) -> dict[str, Any] | None:
        async with self._lock:
            payload = self._read()
            state = payload["guilds"].get(str(guild_id))
            return copy.deepcopy(state) if state is not None else None

    async def save_guild(self, guild_id: int, state: dict[str, Any]) -> None:
        async with self._lock:
            payload = self._read()
            payload["guilds"][str(guild_id)] = copy.deepcopy(state)
            self._write(payload)


def _blank_state(global_access_role_ids: Iterable[int] = ()) -> dict[str, Any]:
    return {
        "blueprint_version": BLUEPRINT_VERSION,
        "status": "applying",
        "global_access_role_ids": sorted(set(global_access_role_ids)),
        "roles": {},
        "categories": {},
        "channels": {},
    }


def _normalise_role_name(name: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", name.casefold()))


def _is_automatic_global_role(role: discord.Role) -> bool:
    name = _normalise_role_name(role.name)
    padded = f" {name} "
    configured = {
        _normalise_role_name(item)
        for item in os.getenv("TRAINING_GLOBAL_ACCESS_ROLES", "").split(",")
        if item.strip()
    }
    return (
        name in configured
        or "department management" in name
        or "human resources" in name
        or name == "hr"
        or " hr " in padded
    )


def _role_by_name(guild: discord.Guild, name: str) -> discord.Role | None:
    matches = [role for role in guild.roles if role.name == name]
    return max(matches, key=lambda role: role.position) if matches else None


def _categories_by_name(
    guild: discord.Guild, name: str
) -> list[discord.CategoryChannel]:
    return [category for category in guild.categories if category.name == name]


def _channels_by_name(
    category: discord.CategoryChannel, name: str
) -> list[discord.abc.GuildChannel]:
    return [channel for channel in category.channels if channel.name == name]


def _channel_has_kind(channel: discord.abc.GuildChannel, kind: str) -> bool:
    return (
        (kind == "text" and isinstance(channel, discord.TextChannel))
        or (kind == "forum" and isinstance(channel, discord.ForumChannel))
        or (kind == "voice" and isinstance(channel, discord.VoiceChannel))
    )


def _managed_count(state: dict[str, Any] | None) -> int:
    if not state:
        return 0
    return sum(
        1
        for section in ("roles", "categories", "channels")
        for entry in state.get(section, {}).values()
        if entry.get("owned")
    )


def _trim_lines(lines: list[str], limit: int = 900) -> str:
    if not lines:
        return "None"
    result: list[str] = []
    length = 0
    for line in lines:
        addition = len(line) + 2
        if length + addition > limit:
            result.append("• …")
            break
        result.append(f"• {line}")
        length += addition
    return "\n".join(result)


class TrainingSetupService:
    def __init__(self, store: StateStore | None = None) -> None:
        self.store = store or StateStore(STATE_FILE)
        self._guild_locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        return self._guild_locks.setdefault(guild_id, asyncio.Lock())

    def _global_roles(
        self,
        guild: discord.Guild,
        state: dict[str, Any] | None,
        extra_role_ids: Iterable[int],
    ) -> list[discord.Role]:
        role_ids = set(extra_role_ids)
        if state:
            role_ids.update(state.get("global_access_role_ids", []))
        roles = [
            role
            for role in guild.roles
            if role.id in role_ids or _is_automatic_global_role(role)
        ]
        return sorted(set(roles), key=lambda role: role.position, reverse=True)

    async def preview(
        self, guild: discord.Guild, extra_role_ids: Iterable[int] = ()
    ) -> PreviewReport:
        state = await self.store.get_guild(guild.id)
        report = PreviewReport()
        current_state = bool(
            state and state.get("blueprint_version") == BLUEPRINT_VERSION
        )
        if state and not current_state:
            report.replacing_previous_version = str(
                state.get("blueprint_version", "unknown")
            )
            report.replacement_count = _managed_count(state)

        for spec in ROLE_SPECS:
            entry = state.get("roles", {}).get(spec.name) if current_state else None
            tracked = guild.get_role(int(entry["id"])) if entry else None
            if tracked or _role_by_name(guild, spec.name):
                report.role_reuse += 1
            else:
                report.role_create += 1

        for category_spec in CATEGORY_SPECS:
            categories = _categories_by_name(guild, category_spec.name)
            if categories:
                category = categories[0]
                report.category_reuse += 1
                if len(categories) > 1:
                    report.warnings.append(
                        f"Multiple categories are named {category_spec.name!r}; the first will be reused."
                    )
            else:
                category = None
                report.category_create += 1

            for channel_spec in category_spec.channels:
                if category is None:
                    report.channel_create += 1
                    continue
                matches = _channels_by_name(category, channel_spec.name)
                correct = [
                    channel
                    for channel in matches
                    if _channel_has_kind(channel, channel_spec.kind)
                ]
                if correct:
                    report.channel_reuse += 1
                    if len(matches) > 1:
                        report.warnings.append(
                            f"Multiple channels are named {channel_spec.name!r} in {category_spec.name!r}; one will be reused."
                        )
                elif matches:
                    tracked_entry = (
                        state.get("channels", {}).get(
                            channel_key(category_spec, channel_spec)
                        )
                        if state
                        else None
                    )
                    replaceable = bool(
                        tracked_entry
                        and tracked_entry.get("owned")
                        and any(
                            channel.id == int(tracked_entry["id"])
                            for channel in matches
                        )
                    )
                    if replaceable:
                        report.channel_create += 1
                    else:
                        report.conflicts.append(
                            f"{category_spec.name} / {channel_spec.name} exists as the wrong channel type."
                        )
                else:
                    report.channel_create += 1

        global_roles = self._global_roles(guild, state, extra_role_ids)
        report.global_role_names = [role.name for role in global_roles]
        if not report.global_role_names:
            report.warnings.append(
                "No existing Department Management or HR role was detected. You can select those roles in the command options or configure TRAINING_GLOBAL_ACCESS_ROLES."
            )

        forums_needed = any(channel.kind == "forum" for _, channel in all_channel_specs())
        if forums_needed and "COMMUNITY" not in guild.features:
            report.conflicts.append(
                "Discord Community is not enabled; it is required for the requested Discussion/Forum channels."
            )

        missing_roles = report.role_create
        missing_channels = report.channel_create + report.category_create
        if len(guild.roles) + missing_roles > 250:
            report.conflicts.append("The setup would exceed Discord's 250-role limit.")
        if len(guild.channels) + missing_channels > 500:
            report.conflicts.append("The setup would exceed Discord's 500-channel limit.")
        return report

    def preview_embed(self, report: PreviewReport, *, confirmation: bool) -> discord.Embed:
        colour = discord.Colour.orange() if confirmation else discord.Colour.blurple()
        title = (
            "Are you sure?"
            if confirmation
            else f"{SERVER_NAME} setup preview"
        )
        embed = discord.Embed(
            title=title,
            description=(
                "Review the planned changes below. Nothing is changed until **Apply changes** is confirmed."
                if confirmation
                else "Read-only preview. Existing matching resources are reused and no duplicate managed setup is created."
            ),
            colour=colour,
        )
        embed.add_field(
            name="Roles",
            value=f"Create: **{report.role_create}**\nReuse: **{report.role_reuse}**",
        )
        embed.add_field(
            name="Categories",
            value=f"Create: **{report.category_create}**\nReuse: **{report.category_reuse}**",
        )
        embed.add_field(
            name="Channels",
            value=f"Create: **{report.channel_create}**\nReuse: **{report.channel_reuse}**",
        )
        if report.replacing_previous_version:
            embed.add_field(
                name="Managed replacement",
                value=(
                    f"Blueprint `{report.replacing_previous_version}` → `{BLUEPRINT_VERSION}`. "
                    f"Up to **{report.replacement_count}** bot-owned objects will be replaced. "
                    "Adopted and untracked server objects are preserved."
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="Blueprint",
                value=f"`{BLUEPRINT_VERSION}` — repeat applies reconcile in place.",
                inline=False,
            )
        embed.add_field(
            name="Existing all-access roles",
            value=_trim_lines(report.global_role_names),
            inline=False,
        )
        if report.warnings:
            embed.add_field(
                name="Warnings", value=_trim_lines(report.warnings), inline=False
            )
        if report.conflicts:
            embed.add_field(
                name="Apply blocked",
                value=_trim_lines(report.conflicts),
                inline=False,
            )
            embed.colour = discord.Colour.red()
        embed.set_footer(
            text="Server administrators always bypass channel overwrites."
        )
        return embed

    def _verify_bot_permissions(self, guild: discord.Guild) -> None:
        me = guild.me
        if me is None:
            raise SetupError("The bot's guild member record is unavailable.")
        missing = [
            label
            for attribute, label in (
                ("manage_roles", "Manage Roles"),
                ("manage_channels", "Manage Channels"),
            )
            if not getattr(me.guild_permissions, attribute)
            and not me.guild_permissions.administrator
        ]
        if missing:
            raise SetupError(
                "The bot is missing required server permissions: " + ", ".join(missing)
            )

    async def apply(
        self, guild: discord.Guild, extra_role_ids: Iterable[int] = ()
    ) -> ApplyResult:
        async with self._lock_for(guild.id):
            self._verify_bot_permissions(guild)
            report = await self.preview(guild, extra_role_ids)
            if report.conflicts:
                raise SetupError("Apply is blocked:\n" + "\n".join(report.conflicts))

            state = await self.store.get_guild(guild.id)
            carried_global_ids = set(extra_role_ids)
            if state:
                carried_global_ids.update(state.get("global_access_role_ids", []))

            result = ApplyResult()
            member_snapshot: dict[str, list[int]] = {}
            if state and state.get("blueprint_version") != BLUEPRINT_VERSION:
                member_snapshot = await self._cleanup_previous(guild, state, result)
                state = None

            if state is None:
                state = _blank_state(carried_global_ids)
                await self.store.save_guild(guild.id, state)
            else:
                state["global_access_role_ids"] = sorted(carried_global_ids)
                state["status"] = "applying"
                await self.store.save_guild(guild.id, state)

            roles = await self._ensure_roles(guild, state, result)
            if member_snapshot:
                await self._restore_role_assignments(
                    guild, roles, member_snapshot, result
                )

            global_roles = self._global_roles(guild, state, extra_role_ids)
            for category_spec in CATEGORY_SPECS:
                category = await self._ensure_category(
                    guild, category_spec, state, roles, global_roles, result
                )
                for channel_spec in category_spec.channels:
                    await self._ensure_channel(
                        guild,
                        category_spec,
                        channel_spec,
                        category,
                        state,
                        roles,
                        global_roles,
                        result,
                    )

            state["status"] = "applied"
            await self.store.save_guild(guild.id, state)
            return result

    async def _cleanup_previous(
        self,
        guild: discord.Guild,
        state: dict[str, Any],
        result: ApplyResult,
    ) -> dict[str, list[int]]:
        snapshot: dict[str, list[int]] = {}
        tracked_channel_ids = {
            int(entry["id"])
            for entry in state.get("channels", {}).values()
            if entry.get("owned")
        }

        for key, entry in list(state.get("roles", {}).items()):
            role = guild.get_role(int(entry["id"])) if entry.get("owned") else None
            if role is not None:
                snapshot[key] = [member.id for member in role.members]

        for key, entry in list(state.get("channels", {}).items()):
            if not entry.get("owned"):
                continue
            channel = guild.get_channel(int(entry["id"]))
            if channel is not None:
                try:
                    await channel.delete(reason=f"Replacing {REASON}")
                except discord.HTTPException as exc:
                    raise SetupError(
                        f"Could not replace managed channel {channel.name!r}: {exc}"
                    ) from exc
            state["channels"].pop(key, None)
            await self.store.save_guild(guild.id, state)

        for key, entry in list(state.get("categories", {}).items()):
            if not entry.get("owned"):
                continue
            category = guild.get_channel(int(entry["id"]))
            if isinstance(category, discord.CategoryChannel):
                unmanaged_children = [
                    channel
                    for channel in category.channels
                    if channel.id not in tracked_channel_ids
                ]
                if unmanaged_children:
                    result.warnings.append(
                        f"Preserved {category.name!r} because it contains untracked channels."
                    )
                else:
                    try:
                        await category.delete(reason=f"Replacing {REASON}")
                    except discord.HTTPException as exc:
                        raise SetupError(
                            f"Could not replace managed category {category.name!r}: {exc}"
                        ) from exc
            state["categories"].pop(key, None)
            await self.store.save_guild(guild.id, state)

        for key, entry in list(state.get("roles", {}).items()):
            if not entry.get("owned"):
                continue
            role = guild.get_role(int(entry["id"]))
            if role is not None:
                try:
                    await role.delete(reason=f"Replacing {REASON}")
                except discord.HTTPException as exc:
                    raise SetupError(
                        f"Could not replace managed role {role.name!r}: {exc}"
                    ) from exc
            state["roles"].pop(key, None)
            await self.store.save_guild(guild.id, state)
        return snapshot

    async def _ensure_roles(
        self,
        guild: discord.Guild,
        state: dict[str, Any],
        result: ApplyResult,
    ) -> dict[str, discord.Role]:
        resolved: dict[str, discord.Role] = {}
        for spec in ROLE_SPECS:
            entry = state["roles"].get(spec.name)
            role = guild.get_role(int(entry["id"])) if entry else None
            same_tracked_role = role is not None
            if role is None:
                role = _role_by_name(guild, spec.name)
            created = role is None
            if created:
                role = await guild.create_role(
                    name=spec.name,
                    colour=discord.Colour(spec.colour),
                    permissions=discord.Permissions.none(),
                    hoist=False,
                    mentionable=False,
                    reason=REASON,
                )
                result.created_roles += 1
            else:
                result.reused_roles += 1

            owned = created or bool(
                same_tracked_role and entry and entry.get("owned")
            )
            if owned and not role.managed:
                updates: dict[str, Any] = {}
                if role.name != spec.name:
                    updates["name"] = spec.name
                if role.colour.value != spec.colour:
                    updates["colour"] = discord.Colour(spec.colour)
                if updates:
                    role = await role.edit(reason=REASON, **updates)

            state["roles"][spec.name] = {
                "id": role.id,
                "name": spec.name,
                "owned": owned,
            }
            resolved[spec.name] = role
            await self.store.save_guild(guild.id, state)
        return resolved

    async def _restore_role_assignments(
        self,
        guild: discord.Guild,
        roles: dict[str, discord.Role],
        snapshot: dict[str, list[int]],
        result: ApplyResult,
    ) -> None:
        for role_name, member_ids in snapshot.items():
            role = roles.get(role_name)
            if role is None:
                continue
            for member_id in member_ids:
                member = guild.get_member(member_id)
                if member is None:
                    try:
                        member = await guild.fetch_member(member_id)
                    except discord.HTTPException:
                        result.warnings.append(
                            f"Could not restore {role_name!r} to member ID {member_id}."
                        )
                        continue
                try:
                    await member.add_roles(role, reason=f"Migrating {REASON}")
                    result.restored_assignments += 1
                except discord.HTTPException:
                    result.warnings.append(
                        f"Could not restore {role_name!r} to {member}."
                    )

    def _set_overwrite(
        self,
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite],
        target: discord.abc.Snowflake,
        **permissions: bool | None,
    ) -> None:
        overwrite = overwrites.get(target, discord.PermissionOverwrite())
        for name, value in permissions.items():
            setattr(overwrite, name, value)
        overwrites[target] = overwrite

    def _base_overwrites(
        self,
        guild: discord.Guild,
        existing: dict[discord.abc.Snowflake, discord.PermissionOverwrite],
        audience_roles: Iterable[discord.Role],
        leadership_roles: Iterable[discord.Role],
        global_roles: Iterable[discord.Role],
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        overwrites = dict(existing)
        self._set_overwrite(
            overwrites,
            guild.default_role,
            view_channel=False,
            send_messages=False,
            send_messages_in_threads=False,
            connect=False,
            speak=False,
        )
        for role in audience_roles:
            self._set_overwrite(
                overwrites, role, view_channel=True, read_message_history=True
            )
        for role in global_roles:
            self._set_overwrite(
                overwrites, role, view_channel=True, read_message_history=True
            )
        manager_permissions = {
            "view_channel": True,
            "read_message_history": True,
            "send_messages": True,
            "send_messages_in_threads": True,
            "create_public_threads": True,
            "create_private_threads": True,
            "manage_channels": True,
            "manage_messages": True,
            "manage_threads": True,
            "connect": True,
            "speak": True,
            "mute_members": True,
            "move_members": True,
        }
        for role in leadership_roles:
            self._set_overwrite(overwrites, role, **manager_permissions)
        if guild.me is not None:
            self._set_overwrite(overwrites, guild.me, **manager_permissions)
        return overwrites

    def _category_overwrites(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel | None,
        spec: CategorySpec,
        roles: dict[str, discord.Role],
        global_roles: list[discord.Role],
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        existing = category.overwrites if category is not None else {}
        audience = [roles[name] for name in spec.audience_role_names]
        leadership = [roles[name] for name in LEADERSHIP_ROLE_NAMES]
        return self._base_overwrites(
            guild, existing, audience, leadership, global_roles
        )

    async def _ensure_category(
        self,
        guild: discord.Guild,
        spec: CategorySpec,
        state: dict[str, Any],
        roles: dict[str, discord.Role],
        global_roles: list[discord.Role],
        result: ApplyResult,
    ) -> discord.CategoryChannel:
        entry = state["categories"].get(spec.key)
        tracked = guild.get_channel(int(entry["id"])) if entry else None
        category = tracked if isinstance(tracked, discord.CategoryChannel) else None
        same_tracked_category = category is not None
        if category is None:
            matches = _categories_by_name(guild, spec.name)
            category = matches[0] if matches else None
        created = category is None
        initial_overwrites = self._category_overwrites(
            guild, category, spec, roles, global_roles
        )
        if created:
            category = await guild.create_category(
                spec.name, overwrites=initial_overwrites, reason=REASON
            )
            result.created_categories += 1
        else:
            result.reused_categories += 1
            edited_category = await category.edit(
                name=spec.name, overwrites=initial_overwrites, reason=REASON
            )
            if edited_category is not None:
                category = edited_category

        owned = created or bool(
            same_tracked_category and entry and entry.get("owned")
        )
        state["categories"][spec.key] = {
            "id": category.id,
            "name": spec.name,
            "owned": owned,
        }
        await self.store.save_guild(guild.id, state)
        return category

    def _channel_overwrites(
        self,
        guild: discord.Guild,
        category_spec: CategorySpec,
        channel_spec: ChannelSpec,
        channel: discord.abc.GuildChannel | None,
        roles: dict[str, discord.Role],
        global_roles: list[discord.Role],
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        existing = channel.overwrites if channel is not None else {}
        audience = [roles[name] for name in category_spec.audience_role_names]
        leadership = [roles[name] for name in LEADERSHIP_ROLE_NAMES]
        overwrites = self._base_overwrites(
            guild, existing, audience, leadership, global_roles
        )
        staff = [roles[name] for name in category_spec.staff_role_names]

        if channel_spec.policy in {"chat", "staff_log"}:
            for role in audience:
                self._set_overwrite(
                    overwrites,
                    role,
                    send_messages=True,
                    send_messages_in_threads=True,
                    create_public_threads=True,
                )
        elif channel_spec.policy == "discussion":
            for role in audience:
                self._set_overwrite(
                    overwrites,
                    role,
                    # A forum post is a thread. Trainees may reply inside an
                    # existing post, but only staff may create new posts.
                    send_messages=False,
                    send_messages_in_threads=True,
                    create_public_threads=False,
                    create_private_threads=False,
                )
        elif channel_spec.policy in {
            "read_only",
            "department_information",
            "department_results",
        }:
            for role in audience:
                self._set_overwrite(
                    overwrites,
                    role,
                    send_messages=False,
                    send_messages_in_threads=False,
                    create_public_threads=False,
                )

        if channel_spec.policy in {
            "department_information",
            "department_results",
            "discussion",
            "staff_log",
        }:
            for role in staff:
                self._set_overwrite(
                    overwrites,
                    role,
                    send_messages=True,
                    send_messages_in_threads=True,
                    create_public_threads=True,
                    manage_messages=True,
                    manage_threads=True,
                )

        if channel_spec.policy == "voice":
            for role in audience:
                self._set_overwrite(
                    overwrites, role, connect=True, speak=True, stream=True
                )
            for role in staff:
                self._set_overwrite(
                    overwrites, role, mute_members=True, move_members=True
                )
        return overwrites

    async def _ensure_channel(
        self,
        guild: discord.Guild,
        category_spec: CategorySpec,
        spec: ChannelSpec,
        category: discord.CategoryChannel,
        state: dict[str, Any],
        roles: dict[str, discord.Role],
        global_roles: list[discord.Role],
        result: ApplyResult,
    ) -> discord.abc.GuildChannel:
        key = channel_key(category_spec, spec)
        entry = state["channels"].get(key)
        tracked = guild.get_channel(int(entry["id"])) if entry else None
        same_tracked_channel = bool(
            tracked is not None
            and tracked.category_id == category.id
            and _channel_has_kind(tracked, spec.kind)
        )
        channel = tracked if same_tracked_channel else None

        if tracked is not None and not same_tracked_channel and entry.get("owned"):
            await tracked.delete(reason=f"Correcting channel type for {REASON}")
            state["channels"].pop(key, None)
            await self.store.save_guild(guild.id, state)
            entry = None

        if channel is None:
            matches = _channels_by_name(category, spec.name)
            correct = [item for item in matches if _channel_has_kind(item, spec.kind)]
            if correct:
                channel = correct[0]
            elif matches:
                raise SetupError(
                    f"{category.name} / {spec.name} already exists as the wrong channel type; it was not created by this blueprint, so it will not be deleted."
                )

        created = channel is None
        overwrites = self._channel_overwrites(
            guild, category_spec, spec, channel, roles, global_roles
        )
        if created:
            marker = f"Managed by PROPEL training setup • {BLUEPRINT_VERSION}"
            if spec.kind == "text":
                channel = await guild.create_text_channel(
                    spec.name,
                    category=category,
                    topic=marker,
                    overwrites=overwrites,
                    reason=REASON,
                )
            elif spec.kind == "forum":
                channel = await guild.create_forum(
                    spec.name,
                    category=category,
                    topic=marker,
                    overwrites=overwrites,
                    reason=REASON,
                )
            elif spec.kind == "voice":
                channel = await guild.create_voice_channel(
                    spec.name,
                    category=category,
                    overwrites=overwrites,
                    reason=REASON,
                )
            else:
                raise AssertionError(f"Unknown channel kind: {spec.kind}")
            result.created_channels += 1
        else:
            result.reused_channels += 1
            edited = await channel.edit(
                name=spec.name,
                category=category,
                overwrites=overwrites,
                reason=REASON,
            )
            if edited is not None:
                channel = edited

        owned = created or bool(
            same_tracked_channel and entry and entry.get("owned")
        )
        state["channels"][key] = {
            "id": channel.id,
            "name": spec.name,
            "kind": spec.kind,
            "category_key": category_spec.key,
            "owned": owned,
        }
        await self.store.save_guild(guild.id, state)
        return channel


class TrainingSetupConfirmView(discord.ui.View):
    def __init__(
        self,
        *,
        service: TrainingSetupService,
        author_id: int,
        guild_id: int,
        extra_role_ids: tuple[int, ...],
        blocked: bool,
    ) -> None:
        super().__init__(timeout=120)
        self.service = service
        self.author_id = author_id
        self.guild_id = guild_id
        self.extra_role_ids = extra_role_ids
        if blocked:
            self.apply_changes.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who opened this confirmation can use it.",
                ephemeral=True,
            )
            return False
        return True

    def _disable(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(
        label="Apply changes",
        style=discord.ButtonStyle.danger,
        emoji="✅",
    )
    async def apply_changes(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        self._disable()
        await interaction.response.edit_message(content="Applying setup…", view=self)
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.edit_original_response(
                content="Setup failed: the server is no longer available.", view=None
            )
            return
        try:
            result = await self.service.apply(guild, self.extra_role_ids)
        except (SetupError, discord.HTTPException) as exc:
            await interaction.edit_original_response(
                content=f"Setup failed safely: {exc}", embed=None, view=None
            )
            return

        embed = discord.Embed(
            title=f"{SERVER_NAME} setup applied",
            description=(
                "The managed blueprint is installed. Re-running the same version will reconcile it without creating duplicates."
            ),
            colour=discord.Colour.green(),
        )
        embed.add_field(
            name="Roles",
            value=f"Created: **{result.created_roles}**\nReused: **{result.reused_roles}**",
        )
        embed.add_field(
            name="Categories",
            value=f"Created: **{result.created_categories}**\nReused: **{result.reused_categories}**",
        )
        embed.add_field(
            name="Channels",
            value=f"Created: **{result.created_channels}**\nReused: **{result.reused_channels}**",
        )
        if result.restored_assignments:
            embed.add_field(
                name="Role migration",
                value=f"Restored **{result.restored_assignments}** member assignments.",
                inline=False,
            )
        if result.warnings:
            embed.add_field(
                name="Warnings", value=_trim_lines(result.warnings), inline=False
            )
        await interaction.edit_original_response(content=None, embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        self._disable()
        await interaction.response.edit_message(
            content="Training setup cancelled. No changes were made.",
            embed=None,
            view=self,
        )
        self.stop()


class TrainingCommands(
    commands.GroupCog,
    group_name="training",
    group_description="Manage the PROPEL training server blueprint.",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = TrainingSetupService()

    @app_commands.command(
        name="setup", description="Preview or apply the PROPEL training setup."
    )
    @app_commands.describe(
        action="Preview only, or request confirmation to apply changes.",
        department_management_role="Optional existing role that should see every training channel.",
        human_resources_role="Optional existing HR role that should see every training channel.",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Preview", value="preview"),
            app_commands.Choice(name="Apply changes", value="apply"),
        ]
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def setup(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        department_management_role: discord.Role | None = None,
        human_resources_role: discord.Role | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        extra_role_ids = tuple(
            role.id
            for role in (department_management_role, human_resources_role)
            if role is not None
        )
        try:
            report = await self.service.preview(interaction.guild, extra_role_ids)
        except SetupError as exc:
            await interaction.response.send_message(
                f"Preview failed safely: {exc}", ephemeral=True
            )
            return

        confirmation = action.value == "apply"
        embed = self.service.preview_embed(report, confirmation=confirmation)
        if not confirmation:
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = TrainingSetupConfirmView(
            service=self.service,
            author_id=interaction.user.id,
            guild_id=interaction.guild.id,
            extra_role_ids=extra_role_ids,
            blocked=bool(report.conflicts),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "You need the Manage Server permission to run /training setup."
        else:
            message = f"The command could not be completed: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
