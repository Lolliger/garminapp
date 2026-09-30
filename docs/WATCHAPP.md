# Watch app (Connect IQ, Approach S62)

Foreground watch-app: polls the relay while it is open, vibrates once on a new question, shows title + description,
Enter/tap opens a Menu2 with the options, your choice is POSTed to `/answer/{id}`. Selection only, no text input.

## Facts this is built on (Garmin docs, read 2026-09-30, SDK 9.2.0 local docs)
- S62: API level 3.0, 260x260 round, MIP 64 colors, touch = true, buttons enter/menu/esc, memory limit watch-app 1 MB, background 64 KB.
- `Menu2` since API 3.0.0 (ok). `Communications.makeWebRequest` needs the `Communications` permission, works through the phone
  (Garmin Connect Mobile) and requires HTTPS (`-1001 SECURE_CONNECTION_REQUIRED`). POST default content type is url-encoded,
  so the app sets `Content-Type: application/json`.
- Error codes used in the app: -104 BLE_CONNECTION_UNAVAILABLE (no BLE connection), -1 BLE_ERROR (generic), -300 request timeout, -402 response too large. The code is shown on screen.

## Build and install (needs your machine: the compiler needs the device data from the SDK Manager, which needs a Garmin login)
1. Install Java 11+, the Connect IQ SDK Manager, download the SDK and, in the *Devices* tab, **Approach S62**.
   Install VS Code + the "Monkey C" extension (Garmin), run *Monkey C: Verify Installation* (creates a developer key).
2. `python3 watchapp/gen_config.py` writes `watchapp/source/Secrets.mc` from `.env` (`PUBLIC_URL`, `RELAY_TOKEN`).
   The file is git-ignored. The token is compiled into the .prg on your watch: fine for your own watch only.
3. Open the `watchapp/` folder in VS Code, *Monkey C: Build for Device* (Edit Products if the device list is empty),
   choose `approachs62` and an output folder.
4. Connect the watch by USB and copy the `.prg` to `GARMIN/APPS/`. Start "Claude" from the app list.
   (Docs: "Copy the generated PRG files to your device's GARMIN/APPS directory".)
5. The watch needs the phone connected via Bluetooth with Garmin Connect Mobile. `PUBLIC_URL` must be reachable
   from the phone (see `docs/TUNNEL.md`) and start with `https://`.

Logs on the device: create an empty `GARMIN/APPS/LOGS/<APPNAME>.TXT` (same name as the .prg); `System.println` output goes there.
A crash shows the "IQ!" icon and writes `CIQ_LOG.YAML`.

## Status: NOT compiled yet
I could not compile this in the sandbox (no device data for `approachs62` without a Garmin login), so the code is written against
the SDK samples and API reference but has never run through the compiler. Expect that the first build may show a few type/syntax
errors: copy the compiler output to me and I fix them. Things most likely to need adjusting: `private const` in `MainView`,
type annotations on the callback signatures, and the manifest attributes.

## Test steps
1. Build succeeds (or send me the errors).
2. Relay + Funnel running, `curl` a request:
   `curl -X POST -H "Authorization: Bearer $RELAY_TOKEN" -H 'Content-Type: application/json' -d '{"title":"demo: Bash","description":"git push origin main","options":["Erlauben","Ablehnen","Terminal"]}' $PUBLIC_URL/request`
3. Open the app on the watch: within ~4 s it vibrates and shows the question. Enter/tap, pick an option, expect "Gesendet: ...".
   `curl -H "Authorization: Bearer $RELAY_TOKEN" $PUBLIC_URL/wait/<id>?timeout=0` shows the answer.
4. Error paths: phone Bluetooth off -> "Handy nicht verbunden"; wrong token in .env (rebuild) -> "Token falsch";
   answer twice / expired -> "Schon beantwortet oder abgelaufen".
5. Check how a long command looks on the round display (description is cut to 240 chars by the relay, 6 lines on screen).

## Does a background service pay off? No (for permission prompts)
- Temporal events: "cannot be set to occur less than 5 minutes after the last temporal event" (API docs). A permission prompt is
  answered within `HOOK_TIMEOUT` (120 s); with a 5 minute cycle the answer would usually come too late and the hook would already
  have fallen back to the terminal.
- A background process has 64 KB memory on the S62 and must exit within 30 s (Backgrounding article).
- No real push: the "Phone App Message" background event needs API 3.2.0 and the Notifications API needs 5.1.0; the S62 has 3.0.
- The closest thing is `Background.requestApplicationWake(msg)` (API 2.3.0): after the background task exits, the watch shows a
  confirmation dialog "open the app?". Still bound by the 5 minute polling. I did not verify that `makeWebRequest` is allowed in the
  background process, and did not build this.
- Recommended alternative: the ntfy notification on the phone as the alert (it may be mirrored to the watch, unverified) and the
  foreground app for answering. If you want the background variant anyway (e.g. with a longer `HOOK_TIMEOUT` for non-urgent
  prompts), say so and I build it as a separate step.
