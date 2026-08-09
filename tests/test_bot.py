import unittest

from bot import _discord_startup_error


class DiscordStartupErrorTests(unittest.TestCase):
    def test_cloudflare_html_is_replaced_with_actionable_message(self) -> None:
        error = Exception(
            "upstream failure </div><!-- /.error-footer --> "
            "<!-- /#cf-error-details -->"
        )

        message = _discord_startup_error(error)

        self.assertIn("Discord returned a Cloudflare error page", message)
        self.assertIn("restart the service", message)
        self.assertNotIn("</div>", message)

    def test_non_cloudflare_error_keeps_diagnostic(self) -> None:
        error = Exception("401 Unauthorized")

        message = _discord_startup_error(error)

        self.assertEqual(
            message, "Discord rejected the startup request: 401 Unauthorized"
        )


if __name__ == "__main__":
    unittest.main()
