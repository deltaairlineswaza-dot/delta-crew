"""Delta Crew Discord bot entrypoint."""

from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands

from health_server import start_health_server
from training_setup import TrainingCommands

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("delta_crew")


def _discord_startup_error(exc: BaseException) -> str:
    """Return a useful message without dumping an upstream HTML error page."""
    details = str(exc)
    if "cf-error-details" in details or "error-footer" in details:
        return (
            "Discord returned a Cloudflare error page while the bot was starting. "
            "This response came from Discord's network, not from this bot. Wait a "
            "few minutes and restart the service; if it continues, check Discord's "
            "status page and the hosting provider's outbound connectivity."
        )
    return f"Discord rejected the startup request: {details}"


class DeltaCrewBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self) -> None:
        await self.add_cog(TrainingCommands(self))
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            commands_synced = await self.tree.sync(guild=guild)
            LOGGER.info("Synced %s command(s) to guild %s", len(commands_synced), guild.id)
        else:
            commands_synced = await self.tree.sync()
            LOGGER.info("Synced %s global command(s)", len(commands_synced))

    async def on_ready(self) -> None:
        if self.user is not None:
            LOGGER.info("Logged in as %s (%s)", self.user, self.user.id)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is required.")
    start_health_server()
    try:
        DeltaCrewBot().run(token, log_handler=None)
    except discord.HTTPException as exc:
        raise SystemExit(_discord_startup_error(exc)) from None


if __name__ == "__main__":
    main()
