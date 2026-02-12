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
