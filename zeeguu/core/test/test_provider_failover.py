"""
One provider's billing state must not stop all assessment.

Through August the Anthropic monthly spend cap did exactly that: every article in
every language failed to assess, for a week at a time, with nothing in the logs
but a per-article error. Switching the crawl to DeepSeek moved the same risk
rather than removing it — running out of DeepSeek credit would look identical.

Two funded providers should degrade to one, not to zero.
"""
from unittest import TestCase
from unittest.mock import patch

from zeeguu.core.llm_services import simplification_and_classification as sac

# The exact body Anthropic returns when the monthly spend cap is reached. Note
# the 400 and invalid_request_error: this is NOT a 429 or any other quota status,
# so a failover keyed on status codes alone would sail straight past it.
ANTHROPIC_CAP_BODY = (
    'Anthropic API error: 400 - {"type":"error","error":{"type":'
    '"invalid_request_error","message":"You have reached your specified API '
    'usage limits. You will regain access on 2026-09-01 at 00:00 UTC."}}'
)

# DeepSeek's out-of-credit response. Carries 402 as well, so it is caught twice.
DEEPSEEK_NO_CREDIT_BODY = '{"error":{"message":"Insufficient Balance"}}'


class ProviderUnavailableClassificationTest(TestCase):
    def test_the_anthropic_spend_cap_counts_as_unavailable(self):
        assert sac._is_provider_unavailable(400, ANTHROPIC_CAP_BODY)

    def test_deepseek_insufficient_balance_counts_as_unavailable(self):
        assert sac._is_provider_unavailable(402, DEEPSEEK_NO_CREDIT_BODY)
        # ...on the body alone too, in case the status ever changes.
        assert sac._is_provider_unavailable(200, DEEPSEEK_NO_CREDIT_BODY)

    def test_rate_limits_outages_and_bad_keys_count(self):
        for status in (401, 403, 429, 500, 503, 529):
            assert sac._is_provider_unavailable(status, ""), status

    def test_an_ordinary_bad_request_does_not_count(self):
        """A 400 that is genuinely our fault must NOT burn the other provider's
        quota retrying the same broken request."""
        assert not sac._is_provider_unavailable(
            400, '{"error":{"message":"max_tokens must be positive"}}'
        )

    def test_the_anthropic_status_is_recovered_from_the_message(self):
        """haiku_client raises a bare Exception carrying the status in its text,
        so the classifier has to read it back out."""
        relabelled = sac._as_provider_unavailable_if_applicable(
            Exception("Anthropic API error: 429 - rate limited")
        )
        assert isinstance(relabelled, sac.ProviderUnavailable)

    def test_a_network_error_is_left_alone(self):
        """No status and no marker: retrying a timeout on the other provider just
        doubles the wait on a slow article."""
        original = Exception("Connection reset by peer")
        assert sac._as_provider_unavailable_if_applicable(original) is original


class ProviderFailoverTest(TestCase):
    def _call(self, side_effect, keys):
        with patch.dict("os.environ", keys, clear=False), patch.object(
            sac, "_call_simplification_llm", side_effect=side_effect
        ) as llm:
            return sac._call_llm_with_provider_failover(
                "prompt", "deepseek", "dsk-key", max_tokens=100
            ), llm

    def test_a_capped_provider_fails_over_to_the_other(self):
        (result, model, used), llm = self._call(
            side_effect=[
                sac.ProviderUnavailable(DEEPSEEK_NO_CREDIT_BODY),
                ("ORIGINAL_LEVEL: B1", "claude-haiku"),
            ],
            keys={
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
        )
        assert used == "anthropic", "should have switched providers"
        assert model == "claude-haiku"
        assert llm.call_count == 2

    def test_the_provider_actually_used_is_reported_back(self):
        """The caller records the model on the row it writes; reporting the
        originally-selected provider after a failover would attribute the text to
        a model that never wrote it."""
        (_, _, used), _ = self._call(
            side_effect=[
                sac.ProviderUnavailable("capped"),
                ("ORIGINAL_LEVEL: B1", "claude-haiku"),
            ],
            keys={
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
        )
        assert used != "deepseek"

    def test_a_content_failure_is_not_retried_elsewhere(self):
        """A paywalled or malformed response is a fact about the ARTICLE. Retrying
        it on the other provider spends twice for the same answer."""
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
            clear=False,
        ), patch.object(
            sac, "_call_simplification_llm", side_effect=Exception("PAYWALL: nope")
        ) as llm:
            with self.assertRaises(Exception):
                sac._call_llm_with_provider_failover(
                    "prompt", "deepseek", "dsk-key", max_tokens=100
                )
        assert llm.call_count == 1, "must not have tried the other provider"

    def test_with_only_one_key_the_original_error_surfaces(self):
        """Nothing to fail over to: raise the real reason rather than a confusing
        secondary error from an unconfigured provider."""
        with patch.dict(
            "os.environ", {"ANTHROPIC_TEXT_SIMPLIFICATION_KEY": ""}, clear=False
        ), patch.object(
            sac,
            "_call_simplification_llm",
            side_effect=sac.ProviderUnavailable("out of credit"),
        ) as llm:
            with self.assertRaises(sac.ProviderUnavailable):
                sac._call_llm_with_provider_failover(
                    "prompt", "deepseek", "dsk-key", max_tokens=100
                )
        assert llm.call_count == 1

    def test_a_healthy_provider_is_not_second_guessed(self):
        (result, model, used), llm = self._call(
            side_effect=[("ORIGINAL_LEVEL: B1", "deepseek-chat")],
            keys={
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
        )
        assert used == "deepseek"
        assert llm.call_count == 1


class FailoverNotificationTest(TestCase):
    """
    A failover must be visible, but a dead provider fails over on EVERY article —
    ~2000/day. Per-event mail would bury the signal it exists to raise, so this is
    once per process (≈ one per hourly crawl run while degraded).
    """

    def setUp(self):
        sac._failover_notified.clear()

    def _failover(self, times=1, llm_side_effect=None):
        side_effect = llm_side_effect or (
            [sac.ProviderUnavailable("Insufficient Balance"), ("ok", "claude-haiku")]
            * times
        )
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
            clear=False,
        ), patch.object(
            sac, "_call_simplification_llm", side_effect=side_effect
        ), patch(
            "zeeguu.core.emailer.zeeguu_mailer.ZeeguuMailer.send_mail"
        ) as send_mail:
            for _ in range(times):
                sac._call_llm_with_provider_failover(
                    "prompt", "deepseek", "dsk-key", max_tokens=100
                )
            return send_mail

    def test_a_failover_sends_one_email(self):
        send_mail = self._failover()
        assert send_mail.call_count == 1
        subject = send_mail.call_args[0][0]
        assert "DEEPSEEK" in subject and "ANTHROPIC" in subject

    def test_repeated_failovers_do_not_repeat_the_email(self):
        send_mail = self._failover(times=25)
        assert send_mail.call_count == 1, "one per process, not one per article"

    def test_the_reason_is_included_so_the_mail_is_actionable(self):
        send_mail = self._failover()
        body = "\n".join(send_mail.call_args[0][1])
        assert "Insufficient Balance" in body

    def test_a_broken_mailer_does_not_break_the_crawl(self):
        """The article WAS assessed. Losing the notification must not turn that
        into a failure."""
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
            clear=False,
        ), patch.object(
            sac,
            "_call_simplification_llm",
            side_effect=[sac.ProviderUnavailable("capped"), ("ok", "claude-haiku")],
        ), patch(
            "zeeguu.core.emailer.zeeguu_mailer.ZeeguuMailer.send_mail",
            side_effect=Exception("SMTP down"),
        ):
            result, _, used = sac._call_llm_with_provider_failover(
                "prompt", "deepseek", "dsk-key", max_tokens=100
            )
        assert result == "ok"
        assert used == "anthropic"

    def test_no_email_when_both_providers_are_down(self):
        """Nothing was rescued, so there is nothing to report as a rescue — the
        error propagates and the coverage check is what catches it."""
        with patch.dict(
            "os.environ",
            {
                "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
                "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
            },
            clear=False,
        ), patch.object(
            sac,
            "_call_simplification_llm",
            side_effect=[
                sac.ProviderUnavailable("out of credit"),
                sac.ProviderUnavailable("capped"),
            ],
        ), patch(
            "zeeguu.core.emailer.zeeguu_mailer.ZeeguuMailer.send_mail"
        ) as send_mail:
            with self.assertRaises(sac.ProviderUnavailable):
                sac._call_llm_with_provider_failover(
                    "prompt", "deepseek", "dsk-key", max_tokens=100
                )
        assert send_mail.call_count == 0
