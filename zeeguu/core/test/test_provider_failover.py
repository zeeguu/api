"""
One provider's billing state must not stop all assessment.

Through August 2026 the Anthropic monthly spend cap did exactly that: every
article in every language failed to assess, for a week at a time, with nothing in
the logs but a per-article error. Moving the crawl to DeepSeek moved the same
risk rather than removing it — running out of DeepSeek credit would look
identical.

Two funded providers should degrade to one, not to zero.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch

import anthropic
import httpx2  # the HTTP client the Anthropic SDK builds its errors on

from zeeguu.core.llm_services import simplification_and_classification as sac

# The exact body Anthropic returns when the monthly spend cap is reached. Note
# the 400 and invalid_request_error: this is NOT a 429 or any other quota status,
# so a failover keyed on status codes alone would sail straight past it.
ANTHROPIC_CAP_BODY = {
    "type": "error",
    "error": {
        "type": "invalid_request_error",
        "message": "You have reached your specified API usage limits. "
        "You will regain access on 2026-09-01 at 00:00 UTC.",
    },
}

# DeepSeek's out-of-credit response. Carries 402 as well, so it is caught twice.
DEEPSEEK_NO_CREDIT_BODY = '{"error":{"message":"Insufficient Balance"}}'

BOTH_KEYS = {
    "DEEPSEEK_API_SIMPLIFICATIONS": "dsk-key",
    "ANTHROPIC_TEXT_SIMPLIFICATION_KEY": "ant-key",
}


def _anthropic_error(error_class, status, body):
    """An SDK status error as the client raises it: message "Error code: N - body"."""
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    return error_class(f"Error code: {status} - {body}", response=response, body=body)


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


class AnthropicErrorsTest(TestCase):
    """haiku_client raises the SDK's typed errors; _call_simplification_llm
    decides which of them mean the provider is gone."""

    def _call_anthropic(self, error):
        with patch.object(sac, "haiku_completion_or_raise", side_effect=error):
            sac._call_simplification_llm("prompt", "anthropic", "ant-key", 100)

    def test_the_spend_cap_400_becomes_provider_unavailable(self):
        error = _anthropic_error(anthropic.BadRequestError, 400, ANTHROPIC_CAP_BODY)
        with self.assertRaises(sac.ProviderUnavailable) as raised:
            self._call_anthropic(error)
        assert "usage limits" in str(raised.exception)
        assert raised.exception.__cause__ is error

    def test_rate_limit_and_overload_become_provider_unavailable(self):
        for error_class, status in (
            (anthropic.RateLimitError, 429),
            (anthropic.AuthenticationError, 401),
            (anthropic.InternalServerError, 500),
            (anthropic.APIStatusError, 529),
        ):
            error = _anthropic_error(error_class, status, {"error": {}})
            with self.assertRaises(sac.ProviderUnavailable, msg=str(status)):
                self._call_anthropic(error)

    def test_an_ordinary_bad_request_is_left_alone(self):
        error = _anthropic_error(
            anthropic.BadRequestError,
            400,
            {"error": {"type": "invalid_request_error", "message": "prompt too long"}},
        )
        with self.assertRaises(anthropic.BadRequestError):
            self._call_anthropic(error)

    def test_a_timeout_is_left_alone(self):
        """No status: retrying a slow article on the other provider just doubles
        the wait."""
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        with self.assertRaises(anthropic.APITimeoutError):
            self._call_anthropic(anthropic.APITimeoutError(request=request))

    def test_a_refusal_is_left_alone(self):
        """The model declined THIS article; the other provider is not the fix."""
        refusal = Exception("Haiku declined the request (stop_reason refusal)")
        with self.assertRaises(Exception) as raised:
            self._call_anthropic(refusal)
        assert not isinstance(raised.exception, sac.ProviderUnavailable)


class DeepSeekErrorsTest(TestCase):
    def _call_deepseek(self, status, text):
        response = MagicMock(status_code=status, text=text)
        with patch.object(sac.requests, "post", return_value=response):
            sac._call_simplification_llm("prompt", "deepseek", "dsk-key", 100)

    def test_insufficient_balance_becomes_provider_unavailable(self):
        with self.assertRaises(sac.ProviderUnavailable):
            self._call_deepseek(402, DEEPSEEK_NO_CREDIT_BODY)

    def test_an_ordinary_bad_request_is_a_plain_error(self):
        with self.assertRaises(Exception) as raised:
            self._call_deepseek(400, '{"error":{"message":"bad max_tokens"}}')
        assert not isinstance(raised.exception, sac.ProviderUnavailable)


class ProviderFailoverTest(TestCase):
    def _call(self, side_effect, keys=BOTH_KEYS):
        with patch.dict("os.environ", keys, clear=False), patch.object(
            sac, "_call_simplification_llm", side_effect=side_effect
        ) as llm, patch(
            "zeeguu.core.emailer.zeeguu_mailer.ZeeguuMailer.send_mail"
        ):
            return sac._call_llm_with_provider_failover(
                "prompt", "deepseek", "dsk-key", max_tokens=100
            ), llm

    def setUp(self):
        sac._failover_notified.clear()

    def test_a_capped_provider_fails_over_to_the_other(self):
        (result, model, used), llm = self._call(
            side_effect=[
                sac.ProviderUnavailable(DEEPSEEK_NO_CREDIT_BODY),
                ("ORIGINAL_LEVEL: B1", "claude-haiku-5-5"),
            ],
        )
        assert used == "anthropic", "should have switched providers"
        assert model == "claude-haiku-5-5"
        assert llm.call_count == 2
        # The retry goes to the other provider, with its own key.
        _, fallback_provider, fallback_key, *_ = llm.call_args_list[1][0]
        assert (fallback_provider, fallback_key) == ("anthropic", "ant-key")

    def test_stop_sequences_survive_the_failover(self):
        """The assess path stops early on a rejection flag; the fallback call
        must stop on the same flags or it pays for summaries it throws away."""
        stop = ["INCOMPLETE_ARTICLE: YES"]
        with patch.dict("os.environ", BOTH_KEYS, clear=False), patch.object(
            sac,
            "_call_simplification_llm",
            side_effect=[sac.ProviderUnavailable("capped"), ("ok", "claude")],
        ) as llm, patch("zeeguu.core.emailer.zeeguu_mailer.ZeeguuMailer.send_mail"):
            sac._call_llm_with_provider_failover(
                "prompt", "deepseek", "dsk-key", max_tokens=100, stop=stop
            )
        assert llm.call_args_list[1].kwargs["stop"] == stop

    def test_a_content_failure_is_not_retried_elsewhere(self):
        """A paywalled or malformed response is a fact about the ARTICLE. Retrying
        it on the other provider spends twice for the same answer."""
        with patch.dict("os.environ", BOTH_KEYS, clear=False), patch.object(
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
        )
        assert used == "deepseek"
        assert llm.call_count == 1


class AssessFailoverAttributionTest(TestCase):
    def test_the_assessment_records_the_provider_that_wrote_it(self):
        """The caller stores the model on the row it writes; reporting the
        originally-selected provider after a failover would attribute the text to
        a model that never wrote it."""
        sac._failover_notified.clear()
        with patch.object(
            sac, "_select_provider_and_key", return_value=("deepseek", "dsk-key")
        ), patch.dict("os.environ", BOTH_KEYS, clear=False), patch.object(
            sac,
            "_call_simplification_llm",
            side_effect=[
                sac.ProviderUnavailable("Insufficient Balance"),
                (
                    "INCOMPLETE_ARTICLE: NO\nADVERTORIAL_CONTENT: NO\n"
                    "ORIGINAL_LEVEL: B1\nARTICLE_TYPE: news\nDISTURBING: NO\n"
                    "ORIGINAL_SUMMARY: Kort resumé.",
                    "claude-haiku-5-5",
                ),
            ],
        ), patch(
            "zeeguu.core.emailer.zeeguu_mailer.ZeeguuMailer.send_mail"
        ), patch.object(
            sac, "generate_in_language", side_effect=lambda gen, *a, **k: gen("")
        ):
            result = sac.assess_and_summarize("Titel", "Indhold", "da")
        assert result["provider"] == "anthropic"
        assert result["model_name"] == "claude-haiku-5-5"


class FailoverNotificationTest(TestCase):
    """
    A failover must be visible, but a dead provider fails over on EVERY article.
    Per-event mail would bury the signal it exists to raise, so this is once per
    process (≈ one per hourly crawl run while degraded).
    """

    def setUp(self):
        sac._failover_notified.clear()

    def _failover(self, times=1):
        side_effect = [
            sac.ProviderUnavailable("Insufficient Balance"),
            ("ok", "claude-haiku-5-5"),
        ] * times
        with patch.dict("os.environ", BOTH_KEYS, clear=False), patch.object(
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
        with patch.dict("os.environ", BOTH_KEYS, clear=False), patch.object(
            sac,
            "_call_simplification_llm",
            side_effect=[sac.ProviderUnavailable("capped"), ("ok", "claude")],
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
        with patch.dict("os.environ", BOTH_KEYS, clear=False), patch.object(
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
