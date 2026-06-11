# Bitmedia Ad Network API Reference

> Unofficial reference, reverse-engineered from the OpenAPI spec embedded in
> https://bitmedia.io/api/api-docs/ (June 2026). Field names and constraints
> were additionally verified against live API behavior; quirks are noted inline.


**Source:** `https://bitmedia.io/api/api-docs/` (Swagger UI). The OpenAPI 3.0.0 spec (title `BitMedia-App-Backend`, v1.0.0, ~840 KB) is embedded inline in `https://bitmedia.io/api/api-docs/swagger-ui-init.js` under the `swaggerDoc` key (there is no separate swagger.json URL).

---

## 1. Base URL, Authentication, Conventions

- **Base URL:** `https://bitmedia.io` — the spec's `servers` array is empty and Swagger UI defaults to `window.location.origin`. All paths begin with `/api/...`, so calls look like `https://bitmedia.io/api/campaigns/list`.
- **Authentication (global, either of two):**
  - `BearerAuth` — `Authorization: Bearer <token>` (http bearer scheme)
  - `ApiKeyAuth` — header **`X-API-Key: <key>`**
- **Getting an API token:** `POST /api/auth/sign-in-api` (no auth required), body `{"email": "...", "password": "..."}` → `{"success": true, "data": {"accessToken": "some_token", "ttlDate": "2022-11-05 12:12:12 UTC"}, "error": ""}`. The token expires at `ttlDate`.
- **Response envelope (all endpoints):** `{"success": bool, "data": <any>, "error": "<message>"}`. Auth-layer errors (401/403/429) instead return `{"message": "..."}`.
- **Error codes:** `400` validation (message in `error`), `401` `"Not authorized to access this resource."`, `403` `"No access."` / `"Your account is disabled by support."`, `404` not found, `429` `"Too many requests, please try again later."`
- **Rate limiting:** 153 of 205 operations document a 429 response; no numeric limits are published in the spec.
- **Pagination convention:** query params `skip` (default 0) and `limit` (default 10 for most lists, max 100; transactions default 7/max 10; sources-statistics default 25). Responses include `items`, `skip`, `limit`, `total`.
- **IDs:** entities use 24-char hex MongoDB ObjectIds. Publisher *source IDs* are 12-digit numeric strings (SSP sources are alphanumeric).
- **Currencies:** `USD` and `BTC` (`currency` query param on many endpoints; default `USD`). Some embedded `bid` values inside `sources_custom_bids_list` responses appear in micro-units (e.g. `250000`, `50000000`) while request bids are plain currency floats — verify empirically.
- **Dates:** `YYYY-MM-DD` (some accept full ISO strings).
- **Entity hierarchy:** **Campaign → Ad Group → Creative**. Budget (balance) lives on the campaign; bid, daily limit, targeting and site white/blacklists live on the group; the ad itself (image/HTML5/text/responsive) is a creative.

---

## 2. Auth (`/api/auth/*`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/sign-in-api` | **Get API access token** (body `{email, password}`) |
| POST | `/api/auth/login` | UI login, returns auth token |
| POST | `/api/auth/sign-up` | Register account |
| GET | `/api/auth/logout` | Log out |
| GET | `/api/auth/user-data?isProfileInfo=0|1` | Current user info → `fullName, email, active, activePublisher, isCorporate, isDSPAdvertiser, isDSPPublisher, isBackupAdvertiser, customerType, defaultStartPage, preferredLanguage, userId` |
| POST | `/api/auth/verify-access-token` | Validate a token |
| POST | `/api/auth/change-password`, `/api/auth/forgot-password`, `/api/auth/set-new-password/{token}` | Password management |
| GET | `/api/auth/validate-forgot-password-token/{token}`, `/api/auth/activate-user/{token}` | Token validation/activation |
| POST | `/api/auth/google-token`, GET `/api/auth/config` | Google OAuth |
| POST | `/api/auth/lead-sign-up`, `/api/auth/activate-lead/{token}`, GET `/api/auth/validate-lead-token/{token}` | Lead signup flow |
| GET | `/api/auth/generate-chat-token` | Zendesk chat token |

---

## 3. Account / Balance (`/api/user/*`)

### GET `/api/user/balance`
No params. Response `data`:
```json
{"balanceCampaigns": 99.955, "balanceReferralUSD": 0, "balanceReferralUSDPending": 0,
 "btc": 0, "btcPending": 0, "publisherUsd": 0, "usd": 0, "usdPending": 0}
```
`usd` = advertiser main balance; `balanceCampaigns` = sum allocated to campaigns.

- **GET `/api/user/currencies-config?isDepositEnabled=bool`** — currencies configuration.
- **GET `/api/user/wallet?currency=...`** — deposit wallet address, e.g. `{"address": "0x7099..."}`.
- **GET `/api/user/transactions`** — required: `fromDate`, `toDate` (YYYY-MM-DD), `isReferral` (`0|1`); optional: `types` (comma list), `filter` (`all|main|pending`), `limit` (≤10, default 7), `skip`. Items: `{info, amount, type: income|outcome, status, date}` plus `types[]` of available type names.
- **GET `/api/user/withdraws`** — required `fromDate, toDate, isReferral`; optional `type` (`pending|main|cancelled`), `limit`, `skip`.
- **POST `/api/user/create-withdraw-request?type=referral|publisher`** — body `{"btcAddress": "1A1z...", "amountUSD": 50.00}`.
- **POST `/api/user/confirm-withdraw-request`** — confirm via email key.
- **POST `/api/user/change-default-balance`** — `{"defaultDisplayedBalance": "advertiser"}`.
- **POST `/api/user/create-transaction-to-advertiser?type=publisher|affiliate`** — `{"usdAmount": 25.50}` (move publisher earnings to ad balance).
- **POST `/api/user/change-profile-info`** — update profile.

---

## 4. Campaigns (`/api/campaigns/*`)

### POST `/api/campaigns/create`
Query (optional): `currency` = `USD|BTC`.
Body (required): `{"name": "Campaign name", "isInternal": false}`
→ 200 `{"success": true, "data": "<new campaign id>", "error": ""}`
Notes: `name` must be unique per user; `isInternal` is for publisher self-promotion campaigns (requires active publisher); DSP users limited to one campaign. **A campaign carries only name/currency/balance — budget funding, groups and targeting are separate calls.**

### GET `/api/campaigns/list`
Params: `skip` (0–901, default 0), `limit` (1–100, default 10), `archived` (`0|1`, default 0), `currency` (`USD|BTC`, default USD), `name` (filter), `withChartStatistic` (`0|1`).
Item fields: `_id, campaignName, isArchived, groupsCount, created, balance, status.active, isInternal, isBalanceRanOut, impressionsTotalObj{today,total}, clicksTotalObj, spentTotalObj, ctr, cpm, cpc` (archived items return flat `spent/impressions/clicks`).

### GET `/api/campaigns/campaign-info?id=<campaignId>` (required)
→ `data`: `campaignName, userId, created, balance, active, isInternal, isBalanceRanOut, isArchived, currency, groupsStatus[{id,name,status}], creativesStatus[{id,name,status}]`.
Group status enum: `Active | Low balance | Limit reached | Not active`.
Creative status enum: `Pending approval | Rejected | Not active | Limit reached | Low balance | Active`.

### Pause / resume
**POST `/api/campaigns/activate-campaign`** — body `{"id": "<campaignId>", "isActive": true|false}`.

### Budget / money movement (campaign budget = its balance)
- **POST `/api/campaigns/usd-refill-campaign`** — `{"id": "<campaignId>", "usdAmount": 100}` (user balance → campaign).
- **POST `/api/campaigns/campaign-refill-campaign`** — `{"fromId", "toId", "amount"}` (campaign → campaign).
- **POST `/api/campaigns/main-refill-campaign`** — `{"campaignId", "amount"}` (campaign → user balance).
- **GET `/api/campaigns/campaigns-balances?currency=`** — `[{_id, campaignName, balance}, ...]`.

### Other
- **POST `/api/campaigns/copy-campaign`** — `{"id", "name", "groupName"?}` (required: id, name) → new campaign id; copies groups + creatives.
- **POST `/api/campaigns/rename-campaign`** — `{"id", "name"}` (both required).
- Archiving a campaign happens implicitly via group archiving (no direct campaign archive endpoint).

---

## 5. Ad Groups (`/api/groups/*`) — bidding, budget limits, targeting, white/blacklists

### POST `/api/groups/create`
Body example: `{"name": "ad group name", "type": "native_cpm", "campaignId": "<id>", "bid": 0.5, "groupDailyLimit": 54}`
Required: `name`, `campaignId`, `bidStrategy`. Other fields: `type`, `bid`, `groupDailyLimit`, `subType`.
- **`type` (pricing model): `native_cpm` | `native_cpc`** (plus `internal` for publisher self-ads). This is where CPM-vs-CPC is chosen.
- **`bidStrategy`: `static` | `smart` | `exact`.** Only one smart group per campaign; DSP users only `static` + `native_cpm`; backup users only `exact|static`; `subType: "web3"` not allowed with exact/smart.
- `bid` must be > 0 and within config range (error example: "Bid must be ≥ 0.1 and ≤ 1.02").
→ `{"success": true, "data": "<groupId>", "error": ""}`

### Bidding
- **GET `/api/groups/group-bid?id=`** → current bid (number; 0 for internal groups).
- **POST `/api/groups/group-bid`** — `{"id", "newBid": 0.5, "type"?: "native_cpm", "subType"?: "web3"}`. Smart groups: bid validated against market-recommended range; exact groups: bid fixed (cannot change). CPC groups require sufficient campaign balance.
- **GET `/api/groups/bid-params?groupType=&currency=`** → `{minBid, maxBid, minOtherBid}`.
- **GET `/api/groups/recommended-bid`** — `id` OR (`devices` required, comma list of `mobile_android, mobile_ios, mobile_winmobile, mobile_others, desktop_windows, desktop_linux, desktop_macos, desktop_others`, or shorthand `mobile`/`desktop`) + optional `countries` ("US,CA,GB"; empty = worldwide), `type` (`native_cpm|native_cpc`, default native_cpm), `currency` → `{min, max, current}`.
- **GET `/api/groups/custom-bids-list?id=`** → `[{source_id, bid, date}]` (per-site custom bids).
- **GET `/api/others/custom-bid-params?currency=`** → `{min, max}` for custom per-source bids.

### Daily budget limit
- **GET `/api/groups/group-limit?id=`** → `{exists, amount, reached, stop_time}`.
- **POST `/api/groups/group-limit`** — `{"id", "dailyLimitStatus": true|false, "groupDailyLimit": 53}`. Range `[0.001; 90000000000]`. Constraints: with a package selected limit must be > $100; smart groups require limit enabled, $300–$3000; exact groups ≥ $100.

### POST `/api/groups/set-group-targeting` — the master targeting call
Full body example (all fields):
```json
{
 "id": "64b5226292ca5930903eba6c",
 "adRerun": 0,
 "displayDesktopOs": [{"name":"linux","value":true},{"name":"windows","value":true},{"name":"macos","value":true},{"name":"others","value":true}],
 "displayMobileOs": [{"name":"android","value":true},{"name":"winmobile","value":false},{"name":"ios","value":true},{"name":"others","value":true}],
 "displayTimeRange": {"from": 0, "to": 24},
 "budgetShouldBeSplit": false,
 "frequencyCapping": false,
 "frequencyTarget": "advertisement",
 "frequencyTime": 24,
 "frequencyValue": 0,
 "language": [],
 "preferredCountries": ["MG", "RE", "EH"],
 "excludedCountries": ["MO"],
 "whitelistedRegions": ["63e3da23718d95b2edafe67c"],
 "blacklistedRegions": ["63e3da24718d95b2edafec3c"],
 "whitelistedAdvertBlocks": [],
 "blacklistedAdvertBlocks": [],
 "whitelistedAudiences": [],
 "blacklistedAudiences": [],
 "trafficType": "included",
 "displayType": {"allow_sticky": true, "allow_regular": true}
}
```
Field semantics (from schemas + validation messages):
- **Geo:** `preferredCountries` / `excludedCountries` — ISO‑2 country codes; `whitelistedRegions`/`blacklistedRegions` — subregion ObjectIds (e.g. US states) from `/api/groups/countries-info`.
- **Device/OS:** `displayDesktopOs` and `displayMobileOs` must each be arrays of exactly 4 `{name, value}` objects (desktop: `linux,windows,macos,others`; mobile: `android,winmobile,ios,others`); at least one device must remain enabled. (No browser targeting exists in this API.)
- **Language:** array of language codes (from `/api/groups/languages`), max 100, no duplicates; group-info shows `"all"` when unrestricted.
- **Frequency capping:** `frequencyCapping` bool, `frequencyValue` (impressions count), `frequencyTime` (hours window), `frequencyTarget` (`"advertisement"` per-ad). Values validated against allowed sets (errors show e.g. 23 and 13 rejected). CPC frequency capping requires account flag.
- **`adRerun`:** hours before re-showing to same user (0 = off; default 72; validated set, 86 rejected).
- **`displayTimeRange`:** `{from, to}` hours 0–24 (dayparting).
- **`budgetShouldBeSplit`:** budget pacing (split over day vs ASAP); requires daily limit > 50 USD.
- **`trafficType`** / response `vpn_traffic`: VPN traffic handling — `"included" | "excluded" | "only_vpn"`.
- **`displayType`:** `{allow_sticky, allow_regular}` placements.
- **`whitelistedAudiences`/`blacklistedAudiences`:** audience ObjectIds; `whitelistedAdvertBlocks`/`blacklistedAdvertBlocks`: ad-unit ids (own units, internal campaigns; not for DSP users).
- Smart-group restrictions: cannot modify targeting while active; must use ASAP pacing, adRerun OFF, all-day range, no frequency-capping changes, no audience/source lists, no data-center targeting, no display-type change.

### Site whitelist/blacklist + custom bids
- **GET `/api/groups/sources-white-black-list?id=`** → `{buyOtherWebsites, buyOtherWebsitesValue, blackListEnable, whiteList: ["123456789012",...], blackList: [...]}`.
- **POST `/api/groups/sources-white-black-list/{action}`** — `action` = `add|delete`; body `{"id", "list": "white_list"|"blocked_sources", "sourceIds": ["..."]}`.
- **POST `/api/groups/set-group-targeting-sources`** — bulk set: `{"id", "selectedPackage": "<packageId>", "whitelistedSources": ["768038395146",...], "blacklistedSources": ["834183544201"], "sourcesCustomBidsList": [{"bid": 2.08845, "source_id": "772686094652"}]}`.
- **POST `/api/groups/set-buy-traffic-from-other-websites`** — `{"id", "buyTrafficFromOtherWebsites": bool, "buyTrafficFromOtherWebsitesValue": 1-100}` (% of traffic from non-whitelisted sites). Returns the full snake_case targeting object (`locations_preferred_list`, `frequency_capping`, `vpn_traffic`, `white_list`, `blocked_sources`, `sources_custom_bids_list`, `allow_rtb_sources_list`, `display_type`, ...).
- **POST `/api/sources/validate-sources`** — `{"sourceIds": ["123456789012"], "groupType": "native_cpm"|"native_cpc"|"internal"}` validate before adding to lists.

### Packages (curated source bundles)
- **GET `/api/groups/packages?id=`** → `[{_id, name, description, active, status, sourceIds: [{sourceId, bid}], minPriceUSD, minPriceBTC, lastUpdated}]`
- **GET `/api/groups/package-placement?packageId=&groupId=`**, **GET `/api/groups/calculated-package-placement?packageId=&groupId=`** — resulting white/black lists + custom bids for a package.
- **POST `/api/groups/set-auto-update-packages`** — `{"id", "autoUpdatePackages": bool}`.

### Lifecycle / listing
- **GET `/api/groups/list`** — params `id` (campaign filter), `skip`, `limit` (1–100, default 10), `archived` (`0|1`), `currency` (`USD|BTC`), `name`. Items: `_id, name, campaignId, campaignName, isArchived, campaignGroupsCount, bidStrategy, isWaitTopUp, created, status{active,paused}, limit{exists,reached}, isInternal, isBalanceRanOut, spent, impressions/clicks/spentTotalObj, ctr, cpm, cpc`.
- **GET `/api/groups/group-info?id=`** — full group: `targetingOptions` (camelCase: `displayMobileOs{...}`, `displayDesktopOs{...}`, `displayTimeRange`, `displayType`, `language`, `locationsPreferred(List)`, `locationsExcluded(List)`, `regionsWhitelistList`, `regionsBlacklistList`, `advertblocksIdsWhitelist/Blacklist`, `budgetShouldBeSplit`, `buyOther(+Value)`, `displayDesktop`, `displayMobile`, `adRerun`, `frequencyCapping/Value/Time/Target`, `blockedSources`, `whiteList`, `buyOtherForlist(+Value)`, `blacklistEnable`, `vpnTraffic`, `sourcesCustomBidsList`, `audiencesWhitelist/BlacklistList`, `minLimitBudgetPacing`) plus `_id, userId, campaignId, groupName, type, selectedPackageId, isArchived, isInternal, currency, networkType, createdAt, modifiedAt, bid, active, paused, isBalanceRanOut, minLimitPackagesCPM, limitRange{min,max}, creativesStatus[], bidStrategy, isWaitTopUp, isAutoUpdatePackagesActive`.
- **POST `/api/groups/activate-group`** — `{"id", "isActive": bool}` (pause/resume).
- **POST `/api/groups/copy-group`** — `{"id", "name", "type"?}` → new group id (copies creatives).
- **POST `/api/groups/rename-group`** — `{"id", "name"}`.
- **POST `/api/groups/set-archived`** — `{"id", "archive": bool}` (soft delete; cascades to creatives/conversions).
- Helpers: **GET `/api/groups/languages`** (`[{_id, short_code, title, country_code}]`), **GET `/api/groups/countries-info`** (regions → countries `{id, name, double_code, regionName, subregions[{name, subregionId, countryCode}]}`), **GET `/api/groups/ad-units-list?skip=&limit=`**, **GET `/api/groups/audience-by-name?searchValue=&isOnlyActive=&archived=`**, **GET `/api/groups/source-by-id/{source_id}?onlyUserSources=`**.

---

## 6. Creatives / Ads (`/api/creatives/*`)

Creative ad types: `image`, `html5`, `text`, `responsive`, `dsp`. All create endpoints double as update endpoints (pass `creativeId`). New/updated creatives enter **moderation** (`approved: null` = pending; `denyReason`/`declineReason` on rejection); `isRunAdAfterApproval: true` auto-starts after approval. `clickUrl` supports macros, e.g. `{source}`.

### GET `/api/creatives/available-sizes`
Params: `type` (`dsp|responsive|image|html5|text`), `sticky_position` (`top|bottom|left|right`).
→ `[{width: "728", height: "90", orientation: "horizontal", deviceTypes: ["desktop"], sticky_positions: ["top","bottom"]}, {width: "468", height: "60", ...}, ...]` (query at runtime per type for the authoritative list; creative-info examples also show 336×280, 320×100).

### Image banner flow (two steps)
1. **POST `/api/creatives/create-image`** (JSON): `{"groupId", "title", "clickUrl", "isRunAdAfterApproval": true, "creativeId"?: "<for update>"}` → creative id.
2. **POST `/api/creatives/upload-images`** (multipart/form-data): fields `creativeId` (string, required), `images` (file(s), required), `imagesForRemove` (array, required — image URLs to delete on update).

### HTML5 flow (two steps)
1. **POST `/api/creatives/validate-html5-archive`** (multipart): `groupId`, `archive` (zip file), `creativeId` (`0` when creating) → `{date, directoryId, html5PreviewUrl}`.
2. **POST `/api/creatives/create-html5`** (JSON): `{"groupId", "title", "clickUrl", "directoryId": "<from step 1>", "creativeViewSizes": [{"width": 300, "height": 100}], "isRunAdAfterApproval": true, "creativeId"?}`.

### Text ads
**POST `/api/creatives/create-text`** (JSON): `{"groupId", "title", "clickUrl", "description1", "description2", "displayUrl", "isRunAdAfterApproval", "creativeId"?}`.

### Responsive ads
**POST `/api/creatives/create-responsive`** (multipart, all required): `groupId`, `headline`, `clickUrl`, `description`, `businessName`, `isRunAdAfterApproval`, `logoFile` (file), `backgroundFile` (file), `creativeId` (`0` to create).

### DSP banners
**POST `/api/creatives/create-dsp`** (DSP accounts only, auto-approved): `{"groupId", "title", "bannerViewSize": "300x250", "creativeId"?}`.

### Listing / management
- **GET `/api/creatives/list`** — params: `by` (`user|group|campaign`, default user), `id` (required when by=group/campaign), `skip`, `limit` (1–100, default 10), `archived` (`0|1`), `currency` (`USD|BTC`), `name`. Items: `_id, title, adType, campaignId, groupId, groupName, groupBidStrategy, currency, isArchived, isInternal, created, modified, status{active, approved, denyReason, new}, spent, impressions/clicks/spentTotalObj, ctr, cpm, cpc, impressionsChart[], clicksChart[]`.
- **GET `/api/creatives/creative-info?id=`** — full details incl. `details{title, description1/2, displayurl, clickurl, headline, businessName, viewSizes, images{"ad-336-280": {imgId, imgWidth, imgHeight}, ...}}`, `approved, active, new, denyReason, sensitiveContent[], categories[], adType, imageMediaUrl, impressionTrackers[], isRunAdAfterApproval`.
- **POST `/api/creatives/activate-creative`** — `{"id", "isActive": bool}`.
- **POST `/api/creatives/copy-creative`** — `{"id", "name", "targetGroupId"?}`.
- **POST `/api/creatives/set-archived`** — `{"id", "archive": bool}`.
- **POST `/api/creatives/update-click-url`** — `{"creativesForUpdate": [{"id", "clickurl"}, ...]}` — **resets approval** (creatives go back to moderation, become inactive).
- **GET `/api/creative/banner-html?type=&width=&height=`** — HTML template for a banner.
- **GET `/api/creatives/creative-clicks-charge-statistics?id=&fromDate=&toDate=&prevPeriod=`** → `{clicks, charge, impressions}`.

---

## 7. Statistics & Reporting

### Time-series (advertiser)
**GET `/api/owner-statistics/detailed-daily-statistics/{entity}`** — `entity` ∈ `campaign|group|creative`; query `id` (required), `groupBy` = `1h|1d` (required), `fromDate`, `toDate` (required, YYYY-MM-DD). **Limits: `1h` → period ≤ 7 days back / interval ≤ 2 days; `1d` → ≤ 90 days.**
→ rows: `{date, impressions, uniqueImpressions, clicks, spends, ctr, cpm, cpc, desktopImpressionsPercent, mobileImpressionsPercent}`.

**GET `/api/owner-statistics/detailed-daily-country-statistics/{entity}`** — same plus optional `country` (ISO-2); rows add `country`.

### By site (source)
**GET `/api/owner-statistics/sources-statistics/{entity}`** (duplicate: `/api/groups/sources-statistics/{entity}`) — `entity` ∈ `campaign|group`; `id`, `fromDate`, `toDate` required; optional `sourceId`, `skip`, `limit` (default 25, max 100).
→ items `{sourceId, topCountry, clicks, imps, ctr, totalTraficPercentage, uniqueImps}`.

### Aggregated tables (with previous-period % change)
- **GET `/api/owner-statistics/general-statistics-advert`** — `statisticsOf` = `campaign|group|creative`, `fromDate`, `toDate`, `skip`, `limit` → per-entity `{_id, entity_id, name, isArchived, imps, clicks, spends, ctr, cpm, cpc, percentage{...}}`.
- **GET `/api/owner-statistics/statistics-advert`** — children within a parent: `id`, `statisticsBy` (`campaign|group`), `statisticsOf` (`campaign|group|creative`), dates, pagination.
- **GET `/api/owner-statistics/general-statistics-countries`** / **`/statistics-countries`** (`id` + `statisticsBy` for the latter) → `{countryCode, imps, clicks, spends, ctr, cpm, cpc, percentage{...}}`.
- **GET `/api/owner-statistics/general-statistics-devices`** / **`/statistics-devices`** → Desktop/Mobile rows with metrics + share `percentage` + `percentageChange`.
- **GET `/api/groups/creatives-statistics`** — `id`, `statisticsBy` (`campaign|group`), `fromDate`, `toDate`, `limit` (default 5), `skip` → `{_id, imps, clicks, spends, name, type, isArchived}`.

### Advertiser dashboard widgets
- **GET `/api/owner-statistics/head-info-statistics`** — last 14 days charts: `spends, impressions, clicks, cpc, cpm` as `[{value, date}]`.
- **GET `/api/owner-statistics/impressions-clicks-statistics`** — `fromDate`, `toDate`, `groupBy` (`1h|1d`), `currency` → `{impressions:{totalAmount, chart[]}, clicks:{...}}`.
- **GET `/api/owner-statistics/spends-statistics`** — same params → `{totalAmount, chart[]}`.
- **GET `/api/owner-statistics/platforms-statistics`** — `fromDate`, `toDate`, `currency` → `{desktop, mobile}` spend split.
- **GET `/api/owner-statistics/today-so-far-statistics?currency=` → `{spends, cpm, cpc, clicks, impressions, ctr, uniques}`.
- **GET `/api/owner-statistics/transactions`** — `fromDate`, `toDate` required; `types`, `limit` (≤10), `skip`, `filter` (`all|completed|hold`).

### Custom reports (`/api/report/*`, async)
- **GET `/api/report/settings?type=advertiser|publisher`** → available `metrics` (e.g. impressions, clicks, spent — typed number/currency), `grouping` (e.g. `day`, `campaign`, `country`), `available_devices` (desktop/mobile), `max_period: 90`.
- **POST `/api/report/generate`** — body:
```json
{"type": "advertiser",
 "dates": {"from": "2023-11-01", "to": "2023-11-30"},
 "filters": {"campaigns": ["<id>"], "countries": ["US","CA","GB"], "devices": ["desktop","mobile"]},
 "metrics": ["impressions","clicks","spent","ctr","cpm"],
 "groupBy": ["day","campaign","country"]}
```
(publisher type uses `filters.adUnits`, metrics incl. `revenue`). Generation is asynchronous.
- **GET `/api/report/data?type=&id=&skip=&limit=`** — latest or specific report → `{id, status: "successfully_generated", groupBy, metrics, reportExpirationDate, totalStatistic{...}, items: [{day, impressions, clicks, spent, ctr}, ...], skip, limit, total}`.
- Saved configs: **GET `/api/report/saved-options`** (filters `type` required, `dateFrom/dateTo/name/skip/limit`), **GET `/api/report/saved-options/{id}`**, **POST `/api/report/create-update-saved-options`** (same shape as generate + `name`, `id` for update), **POST `/api/report/remove-saved-options`** `{"id": ["...", "..."]}`.

---

## 8. Conversions (`/api/conversions/*`)

- **POST `/api/conversions/new`** — `{"name", "description", "type": "landing"|"registration"|"purchase"|"custom", "eventId"}`.
- **GET `/api/conversions/list`** — `skip`, `limit` (≤100), `title`, `type`, `status` (`1|0`) → `{_id, name, description, event_id, type, active, count, amount}`.
- **GET `/api/conversions/statistics`** — `dateFrom`, `dateTo` required; `groupId`, `campId`, `conversionId`, `skip`, `limit` → rows `{date, source_id, creative_id, campaign_id, group_id, user_country, user_os, user_browser, user_mobile, user_ip, value, conversion_type}`.
- **GET `/api/conversions/entity/{id}`**, **POST `/api/conversions/activate-conversion`**, **POST `/api/conversions/set-archived`**, **POST `/api/conversions/update`** (name/description).

## 9. Audiences (`/api/audiences/*`)

- **POST `/api/audiences/create`** — `{"title", "description", "refreshPeriod": 30, "eventId", "dmp_settings_types_id", "items": {"values": [...], "conditions": {"impressions": {"condition": "gte", "count": 5}, "clicks": {...}}, "logical_condition": "and"}}`.
- **POST `/api/audiences/update?id=`** — `{title, description}`.
- **GET `/api/audiences/list`** — `skip`, `limit`, `archived`, `isOnlyActive`, `isPromoted` → `{id, name, users, eventId, description, active, approved}`.
- **GET `/api/audiences/info?id=`**, **GET `/api/audiences/settings`**, **POST `/api/audiences/activate-audience`**, **POST `/api/audiences/set-archived`**.

## 10. Publisher side (brief)

**Sources (sites/apps)** — `/api/sources/*`: `create-source` (`{websiteUrl, categories: [{key, value[]}], mainLanguage, pageViews: {from,to}, topGeos[]}`; Google Play URL ⇒ in-app), `list` (stats incl. `earnings, eCPM, cpmFloorStatusCode`), `info`, `activate-source`, `archive-source`, `create-request-cpm-floor` (`{idsArray}`), `set-political-content`, `validation-publisher-site-request`, `post-become`, `validate-sources`.

**Ad Units** — `/api/ad-units/*`: `create` (`{sourceId, name, adType (banner/native/video), display_type (standard/sticky/prebid), sticky_options, sizes: [{pc:{width,height}, mobile:{...}}], backupInfo}`; `?currency=`), `list` (requires `fromDate`/`toDate`; returns `clicks, impressions, earnings, ctr, eCPM, cpmFloor, size`), `info` (incl. `clientKey`, backup `noContent` per device, Google AdSense backup fields), `activate-ad-unit`, `set-archived`, `{id}/edit-cpm-floor`, `edit-settings` (`allowCpa, allowDisplayAds, allowMobile, allowPartners, allowTextAds`), `update`.

**Publisher statistics** — `/api/publisher-statistics/*`: `detailed-statistics` (`fromDate, toDate, groupBy 1h|1d, sourceId?, adUnitId?`) → `{date, impressions, clicks, earnings, ctr, cpm, desktop/mobileImpressionsPercent}`; `blocks-statistics` (per ad unit), `device-statistics`, `head-info-statistics` (charts incl. pageViews), `info-statistics` (`type` = `os|source|country`), `detailed-daily-statistics/{entity}`.

## 11. Other endpoint groups (enumerated)

- **Others** (`/api/others/*`): `exchange-rate?currency=` → `{usd: 45000.5}`; `custom-bid-params`; `entity-count` (`countBy` = campaign/group/user/advertiser/publisher; `count` = campaigns/groups/creatives/audiences/conversions/domains/ad_blocks/saved_report_options); `countries-list` (filter/search/sort, regions enum incl. Europe, CIS, Northern America…); `filter-advert-list` (`entityName` = creative/campaign/group); `filter-sources-list` (`type` = advertiser/publisher); `categories-list`; `main-languages`; `current-promotion`; `stripe-info`; `create-checkout-session` (Stripe deposit); `stripe-webhook`; `wordpress-counts/{type}`; `update-referrer-stat`.
- **Deposit**: GET `/api/deposit/available-promotions` → deposit bonus tiers `{minDeposit, maxDeposit, bonusPercent}`.
- **Referral** (`/api/referral/*`): `main-info`, `balance` (`{todayProfit, totalProfit, pending}`), `stat` (`fromDate, toDate, groupBy 1h|1d, referralUrls`), `links` (`?withHits=`), `create` (`{url}`), `delete` (`{referralUrls[]}`), `post-corporate-request`.
- **Notifications**: `categories`, `count-new`, `messages` (`is_unread` required, `category`, `skip`, `limit`), `set-read-field` (`{notificationIds[], markAllAsRead, markIsRead}`).
- **Marketplace** (`/api/marketplace/*`, content marketplace for buying placements/articles): `items`, `grouped-items`, `item/{id}`, `items-public`, `top-items`, `categories`, `niches`, `countries`, `languages`, `sources`, `price-range`, `audience-range`, `filter-counts`, `shopping-cart(+counts)`, `change-shopping-cart/{action}`, `wish-list(+counts)`, `change-wish-list/{action}`, `create-order`, `order-list`, `order-summary/{id}`, `order-for-pay/{id}`, `order-payment/{id}`, `save-archive`.
- **Events/Quests**: `/api/events/available(-not-auth)`, `/api/events/user-promo-rewards`, `/api/events/claim-prize`; `/api/quests/quest-tasks`, `/api/quests/quest-not-logged`.
- **Analytics**: GET `/api/analytic/config` (click-ID param mappings), POST `/api/analytic/save-utm-tags`.
- Spec artifacts: bare paths `available` (GET), `identifier` (GET), `referral` (DELETE) exist as empty stubs with no schema — ignore.

## 12. Client-building notes

1. **Minimal campaign launch sequence:** `sign-in-api` → `POST /api/campaigns/create` → `POST /api/campaigns/usd-refill-campaign` (fund it) → `POST /api/groups/create` (type `native_cpm`/`native_cpc`, bidStrategy, bid, daily limit) → `POST /api/groups/set-group-targeting` (geo/OS/language/frequency) → optionally `set-group-targeting-sources` (white/blacklist) → create creative(s) (`create-image` + `upload-images`, etc.) → wait for moderation (`creative-info.approved`) → `activate-campaign`/`activate-group`/`activate-creative`.
2. There is no campaign-level *total budget* field — total budget is the campaign balance; daily caps are per group via `group-limit`.
3. OS targeting only (Windows/Linux/macOS/others; Android/iOS/WinMobile/others) — no browser targeting in this API; language and VPN-traffic targeting exist; geo by country code and by subregion ObjectId.
4. `archived=0/1` + `set-archived` is the delete model (soft delete everywhere); `isActive` toggles are pause/resume.
5. All 4xx validation errors arrive as human-readable strings in `error` (or `message` for 401/403/429); `success` is the primary success signal.