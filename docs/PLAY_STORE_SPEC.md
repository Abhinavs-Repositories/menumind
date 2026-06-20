# MenuMind — Play Store Release Spec

> Status: **DRAFT / planning** (2026-06-20). We implement this later; this doc is
> the plan of record. Check boxes as we complete them.

Goal: turn the current Expo (SDK 56) app in [`mobile/`](../mobile/) into a
standalone, installable Android app published on the Google Play Store — no
dependency on Expo Go.

---

## 0. Where we are vs. where we're going

| | Now | Target for Play |
|---|---|---|
| Run method | Expo Go / web dev server | Standalone signed app (AAB) |
| App name | `mobile` (placeholder) | `MenuMind` |
| Package id | none set | `com.seahawk.menumind` (permanent once live) |
| Backend | HF Space free tier | Hardened, reliable, rate-limited |
| Distribution | QR / localhost | Play Console tracks (internal → production) |
| Privacy policy | none | required (hosted URL) |

The native build path **bypasses the current Expo Go SDK-56 bug entirely** — that
bug only affects the Expo Go sandbox, not standalone builds.

---

## 1. App identity & branding

- [ ] **App name:** `MenuMind`
- [ ] **Android applicationId / package:** `com.seahawk.menumind`
      ⚠️ Permanent after first publish — choose deliberately.
- [ ] **`scheme`** (deep links): `menumind`
- [ ] Update [`mobile/app.json`](../mobile/app.json): `name`, `slug`, `scheme`,
      `android.package`, `version`, `android.versionCode`.
- [ ] **Icon** (1024×1024, no transparency) + **adaptive icon** (foreground +
      background) + **splash**. Replace the template assets in
      `mobile/assets/images/`.
- [ ] **Permissions:** INTERNET only. Strip anything the template added; declare
      nothing else (keeps the Data Safety form + review simple).

---

## 2. Tooling: EAS (Expo Application Services)

EAS builds the signed app in the cloud (no Android Studio needed locally).

- [ ] `npm i -g eas-cli`
- [ ] `eas login` (the `seahawk` Expo account)
- [ ] `eas build:configure` → generates `eas.json`
- [ ] Free tier is sufficient to start: **15 Android builds/month**, EAS Update
      for 1,000 MAU, 100 GiB bandwidth.

### `eas.json` profiles (target shape)

```jsonc
{
  "cli": { "version": ">= 16.0.0" },
  "build": {
    "development": {            // dev client APK — replaces Expo Go for on-device dev
      "developmentClient": true,
      "distribution": "internal",
      "android": { "buildType": "apk" }
    },
    "preview": {                // shareable internal APK for testers
      "distribution": "internal",
      "android": { "buildType": "apk" }
    },
    "production": {             // AAB for the Play Store
      "autoIncrement": true,
      "android": { "buildType": "app-bundle" }
    }
  },
  "submit": { "production": {} }
}
```

> **Migrate off Expo Go for dev:** build the `development` profile once, install
> that APK, then `npx expo start --dev-client`. This is the long-term dev flow.

---

## 3. Android target API & build format

- [ ] **Target SDK 35 (Android 15)** — minimum for new Play apps today.
- [ ] **Plan SDK 36 (Android 16) before 2026-08-31** — becomes mandatory; if we
      launch after that date, target 36 from the start. Expo SDK 56 supports
      configuring `targetSdkVersion` via `expo-build-properties`.
- [ ] **minSdkVersion:** keep Expo's default (24) unless a dependency forces higher.
- [ ] Output format: **AAB** (`.aab`) — Play no longer accepts APKs for new apps.

---

## 4. Signing

- [ ] Use **Google Play App Signing** (recommended): EAS generates an *upload*
      keystore; Google holds the *app signing* key.
- [ ] Let EAS manage the upload keystore (`eas credentials`). **Back it up** —
      losing it complicates updates (recoverable via Play support, but avoid it).
- [ ] Record where credentials live (EAS-managed vs. local keystore) in the team
      notes.

---

## 5. Backend hardening (do BEFORE public launch)

The API at `https://seahawk-menumind-api.hf.space` is currently open and on a
free tier. A published app makes it a public, unauthenticated endpoint that
burns our **shared** Groq/Gemini/Qdrant free quotas — abuse = outage for everyone.

- [ ] **Reliability:** HF free Spaces can sleep / cold-start. Decide: keep HF
      (add a keep-warm ping) **or** move to an always-on host. Re-evaluate cost.
- [ ] **Rate limiting:** per-IP throttle on `/chat` (e.g. `slowapi`) + a global
      cap to protect quotas.
- [ ] **Abuse protection:** lightweight app attestation or a shared app key/header
      checked server-side (note: a key shipped in the app is not a real secret —
      pair with rate limits; consider Play Integrity API later).
- [ ] **CORS:** tighten `ALLOWED_ORIGINS` for the web/PWA build (native apps are
      not subject to CORS).
- [ ] **Input limits:** cap question length; reject empty/oversized payloads
      (partly done — `/chat` already 400s on empty).
- [ ] **Observability:** basic request logging / error alerting.
- [ ] **Versioning:** consider `/v1` route prefix so the app and API can evolve
      independently.

---

## 6. Privacy, data safety & compliance (Play requirements)

- [ ] **Privacy policy URL** (required by Play). Must disclose that typed
      questions are sent to our backend and processed by third parties
      (Groq / Google Gemini / Qdrant). Host it (GitHub Pages / simple page).
- [ ] **Data Safety form** in Play Console: declare what's collected/shared.
      Current app: questions sent to backend (not tied to identity, no account);
      chat history stored **locally** on device (AsyncStorage — not "collected").
- [ ] **Content rating** questionnaire (likely "Everyone").
- [ ] **Ads:** none → declare no ads.
- [ ] **Account deletion:** N/A while there are no user accounts (revisit if we
      add auth/sync later).

---

## 7. Google Play Console setup

- [ ] **Create a Play Developer account** — one-time **$25** fee. Personal vs.
      org: new personal accounts may face additional identity/testing
      requirements — verify current rules when we register.
- [ ] Create the app → category **Food & Drink**.
- [ ] **Store listing assets:**
  - [ ] App name (30 chars), short description (80), full description (4000)
  - [ ] **Feature graphic** 1024×500
  - [ ] **Phone screenshots** (min 2; 2–8 recommended) — menu picker + streaming chat
  - [ ] App icon 512×512
- [ ] **Release tracks (in order):** Internal testing → Closed → (Open optional)
      → Production. Start on **internal** to validate the signed build end-to-end.
- [ ] **`eas submit -p android`** to upload (needs a Google Play **service
      account JSON** for API submission; first upload can be manual).

---

## 8. Updates strategy

- [ ] **EAS Update (OTA)** for JS-only changes — ship bug fixes without a new
      store review. Free tier covers 1,000 MAU.
- [ ] **New store build required** when native deps / SDK / permissions / app
      version change.
- [ ] **Versioning policy:** bump `versionName` (semver, user-facing);
      `versionCode` auto-increments via `autoIncrement` in the production profile.

---

## 9. Cost summary

| Item | Cost |
|---|---|
| Google Play Developer account | **$25 one-time** |
| EAS Build/Update | **$0** on free tier to start (15 Android builds/mo) |
| Backend (HF free) | $0, but reliability/quota risk — may need a paid host |
| Apple App Store (later) | $99/yr (out of scope here) |

---

## 10. Execution order (when we build this)

1. Set app identity (name, package, icon/splash, permissions) in `app.json`.
2. `eas build:configure`; add the three build profiles.
3. Backend hardening (rate limit + reliability) — gate for public launch.
4. Write + host the privacy policy.
5. `eas build --profile development` → on-device dev without Expo Go.
6. `eas build --profile production` → AAB.
7. Register Play account ($25); create app; fill listing + Data Safety + rating.
8. Upload to **Internal testing**; verify the signed build end-to-end.
9. Promote → Closed → Production; staged rollout.
10. Wire EAS Update for OTA JS patches.

---

## Open decisions (need answers before starting)

- [ ] Final package id — lock `com.seahawk.menumind`?
- [ ] Keep backend on HF (with keep-warm) or move to an always-on host?
- [ ] Per-app key + rate limit now, or rate limit only for v1?
- [ ] Where to host the privacy policy?
- [ ] Developer account type: personal or organization?

## References

- Play target API levels: https://developer.android.com/google/play/requirements/target-sdk
- Play target API policy: https://support.google.com/googleplay/android-developer/answer/11926878
- Expo plans / EAS pricing: https://docs.expo.dev/billing/plans/
- EAS Build setup: https://docs.expo.dev/build/setup/
- Expo Go SDK-56 Android bug (why we go standalone): https://github.com/expo/expo/issues/46846
