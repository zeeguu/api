# Apple Family Controls Entitlement Request

**App Name:** Zeeguu: News for learners
**App Store URL:** https://apps.apple.com/dk/app/zeeguu-news-for-lea...
**Team ID:** E9Y43LYCSK

---

## What's your app's primary purpose?

Zeeguu helps people learn foreign languages by reading real articles. Users read news and web content in their target language while the app provides instant translations, tracks vocabulary, and generates personalized review exercises using spaced repetition.

---

## What service do you provide or plan to provide users and how will you use Family Controls to support this service within your app?

Zeeguu is a language learning app that helps users improve their reading skills in foreign languages by reading real news articles with built-in translation support and personalized vocabulary exercises.

We plan to add an optional "Anti-Procrastination Mode" that helps users build consistent reading habits. Many users tell us they want to practice daily but default to social media when they have free moments.

With Family Controls, users will be able to:
1. Select apps they find distracting (using the system FamilyActivityPicker)
2. See a motivational shield when opening those apps, with a message like "Maybe study a bit instead?" and a button that opens Zeeguu's reader
3. Set their own schedule for when blocking is active

This is strictly for individual self-control (`.individual` authorization), not parental monitoring. Users opt-in explicitly, choose their own apps to block, and can disable the feature anytime. We do not collect data about which apps users select or block.

---

## Explain why you need this entitlement and how it will be used in your app.

We need the Family Controls entitlement to implement app blocking and shield overlays that redirect users to language learning.

Without this entitlement, there is no iOS API that allows an app to:
- Present a blocking screen when another app is launched
- Let users select which apps to block via a system-provided picker
- Schedule when blocking is active

We will use:
- **FamilyControls** framework to request `.individual` authorization and display the `FamilyActivityPicker` for app selection
- **ManagedSettings** framework to apply shield overlays on user-selected apps
- **DeviceActivity** framework to schedule blocking periods based on user preferences

The shield will display a custom message encouraging the user to read, with a button that deep-links into Zeeguu's article reader. Users control everything: which apps, what schedule, and can disable anytime.

---

# Distribution requests for the two extensions (2026-10-19)

Distribution approval is per bundle ID. The main app (`org.zeeguu.app`) has it;
the two extensions added for Aiki mode (web#1334) need their own requests at
https://developer.apple.com/contact/request/family-controls-distribution, one
per bundle ID. What we built differs from the plan above in one way: the shield
explains what to do and its button only closes it (no deep link).

In the end the form asked no questions and no bundle ID: one request per team.
Submitted 2026-10-19, request ID MCAT6LHJP6; approved for the team within
hours. Then tick Family Controls (Distribution) on each App ID.

## Request 1: `org.zeeguu.app.ShieldConfiguration`

**What's your app's primary purpose?** (same as above)

**How will you use Family Controls?**

This is the Shield Configuration extension of Zeeguu (org.zeeguu.app, already
approved for Family Controls distribution). It belongs to an optional feature
called Aiki mode: the user picks the apps they find distracting with the system
FamilyActivityPicker, and while Aiki mode is on, opening one of those apps shows
a shield instead. Each minute of language learning in Zeeguu unlocks the apps
for 5 minutes; 15 minutes of learning in a day unlocks them until midnight.

This extension only provides the shield's appearance (ShieldConfigurationDataSource):
the Zeeguu logo, "<App> is paused", a sentence explaining how to unlock it, and
today's progress ("Today: 4 of 15 minutes"). Its button closes the shield.

**Why do you need this entitlement?**

A Shield Configuration extension cannot customize the shield without the Family
Controls entitlement, and an App Store build of the app cannot include the
extension unless its bundle ID is approved for distribution. Authorization is
`.individual` (self-control, not parental monitoring); the user opts in and can
turn Aiki mode off at any time. The extension reads the user's progress from
the app's App Group on the device; nothing about the chosen apps leaves the
device.

## Request 2: `org.zeeguu.app.AikiMonitor`

**What's your app's primary purpose?** (same as above)

**How will you use Family Controls?**

This is the Device Activity Monitor extension of Zeeguu (org.zeeguu.app,
already approved for Family Controls distribution). It belongs to an optional
feature called Aiki mode: the user picks the apps they find distracting with
the system FamilyActivityPicker, and while Aiki mode is on, opening one of
those apps shows a shield instead. Each minute of language learning in Zeeguu
unlocks the apps for 5 minutes; 15 minutes of learning in a day unlocks them
until midnight.

This extension (DeviceActivityMonitor) is woken by iOS at two moments: when an
earned break ends, and at midnight, when the day's progress resets. Both times
it re-applies the shield with ManagedSettings to the apps the user chose, even
if Zeeguu is not running.

**Why do you need this entitlement?**

Without this extension, the shield could only come back when the user next
opens Zeeguu, so an earned 5-minute break would never end. A Device Activity
Monitor extension needs the Family Controls entitlement, and an App Store
build of the app cannot include it unless its bundle ID is approved for
distribution. Authorization is `.individual` (self-control, not parental
monitoring); the user opts in and can turn Aiki mode off at any time. No data
about the chosen apps or the user's activity leaves the device.
