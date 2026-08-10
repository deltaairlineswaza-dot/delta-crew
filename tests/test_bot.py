import unittest
from unittest.mock import MagicMock, call, patch

import discord

from bot import _discord_startup_error, _run_bot


class DiscordStartupErrorTests(unittest.TestCase):
    def test_cloudflare_html_is_replaced_with_actionable_message(self) -> None:
        error = Exception(
            "upstream failure </div><!-- /.error-footer --> "
            "<!-- /#cf-error-details -->"
        )

        message = _discord_startup_error(error)

        self.assertIn("Discord returned a Cloudflare error page", message)
        self.assertIn("retry automatically", message)
        self.assertNotIn("</div>", message)

    def test_non_cloudflare_error_keeps_diagnostic(self) -> None:
        error = Exception("401 Unauthorized")

        message = _discord_startup_error(error)

        self.assertEqual(
            message, "Discord rejected the startup request: 401 Unauthorized"
        )

    @patch("bot.time.sleep")
    @patch("bot.DeltaCrewBot")
    def test_cloudflare_errors_retry_with_bounded_backoff(
        self, bot_class: MagicMock, sleep: MagicMock
    ) -> None:
        cloudflare = discord.HTTPException(
            MagicMock(status=502, reason="Bad Gateway"),
            "<!-- /#cf-error-details -->",
        )
        bot_class.return_value.run.side_effect = [cloudflare, cloudflare, None]

        _run_bot("token")

        self.assertEqual(bot_class.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(5), call(10)])

    @patch("bot.DeltaCrewBot")
    def test_non_cloudflare_http_error_exits(self, bot_class: MagicMock) -> None:
        rejected = discord.HTTPException(
            MagicMock(status=401, reason="Unauthorized"), "invalid token"
        )
        bot_class.return_value.run.side_effect = rejected

        with self.assertRaisesRegex(SystemExit, "Discord rejected"):
            _run_bot("token")


if __name__ == "__main__":
    unittest.main()
