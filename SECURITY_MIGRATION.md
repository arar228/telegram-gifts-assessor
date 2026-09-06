# Telegram credential migration

`price_checker.py` and `test_gifts.py` now require `API_ID` and `API_HASH` from the environment loaded by their existing `load_dotenv()` call. The embedded fallback credentials have been removed. `API_ID` must be positive; `API_HASH` must contain 32 hexadecimal characters. Errors identify the setting and exclude its value.

Before deploying, provision the owning Telegram application's credentials in the same environment or ignored `.env` used by the current process. `.env.example` contains empty fields only. `PHONE_NUMBER` remains optional and preserves the existing interactive login flow. `GIFTASSET_API_KEY` remains optional for the separate Giftasset script.

Preserve existing authorized `.session` files at their current paths and retain file permissions. This patch changes neither session names nor authentication flow. Session files authorize account access and belong outside Git.

## Offline verification

```bash
python -m unittest discover -s tests -p "test_credentials_config.py"
```

These tests validate the helper and credential initialization using synthetic values; they never start a Telegram client. The repository's `test_gifts.py` is an interactive/network utility, not an offline test command.

The patch changes no dependencies. Existing dependency gaps remain a separate maintenance task. Deploy only after the required environment is ready. Source cleanup does not remove earlier credentials from Git history or revoke them; review Telegram application/session controls and coordinate any replacement before history cleanup or service restart.
