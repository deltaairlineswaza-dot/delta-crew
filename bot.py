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
    DeltaCrewBot().run(token, log_handler=None)


if __name__ == "__main__":
    main()

