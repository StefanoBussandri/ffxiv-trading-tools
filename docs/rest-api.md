# Universalis REST API

Welcome to the Universalis documentation page.

There is a rate limit of 25 req/s (50 req/s burst) on the API, and 15 req/s (30 req/s burst) on the website itself, if you're scraping instead. The number of simultaneous connections per IP is capped to 8.

To map item IDs to item names or vice versa, use [XIVAPI](https://xivapi.com/docs/Search#search). In addition to XIVAPI, you can also get item ID mappings from [Lumina](https://lumina.xiv.dev/docs/intro.html), [this sheet](https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/en/Item.csv), or [this](https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json/items.json) pre-made dump.

To get a mapping of world IDs to world names, use [XIVAPI](https://xivapi.com/World) or [this sheet](https://raw.githubusercontent.com/xivapi/ffxiv-datamining/master/csv/en/World.csv). The `key` column represents the world ID, and the `Name` column represents the world name. Note that not all listed worlds are available to be used — many of the worlds in this sheet are test worlds, or Korean worlds (Korea is unsupported at this time).

If you use this API heavily for your projects, please consider supporting the website on [Liberapay](https://liberapay.com/karashiiro), [Ko-fi](https://ko-fi.com/karashiiro), or [Patreon](https://patreon.com/universalis), or making a one-time donation on [Ko-fi](https://ko-fi.com/karashiiro). Any support is appreciated!

Table of contents

Endpoints

1. Available data centers
2. Available worlds
3. Current item price
4. Game entities
5. Least-recently updated items
6. Market board current data
7. Market board sale history
8. Market tax rates
9. Marketable items
10. Most-recently updated items
11. Recently updated items
12. Upload counts by upload application
13. Upload counts by world
14. Uploads per day
15. User lists

Entities

1. Microsoft.AspNetCore.Mvc.ProblemDetails
2. Universalis.Application.Views.V1.CurrentlyShownView
3. Universalis.Application.Views.V1.Extra.ContentView
4. Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView
5. Universalis.Application.Views.V1.Extra.Stats.RecentlyUpdatedItemsView
6. Universalis.Application.Views.V1.Extra.Stats.SourceUploadCountView
7. Universalis.Application.Views.V1.Extra.Stats.UploadCountHistoryView
8. Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView
9. Universalis.Application.Views.V1.Extra.Stats.WorldUploadCountView
10. Universalis.Application.Views.V1.HistoryView
11. Universalis.Application.Views.V1.ListingView
12. Universalis.Application.Views.V1.MateriaView
13. Universalis.Application.Views.V1.MinimizedSaleView
14. Universalis.Application.Views.V1.SaleView
15. Universalis.Application.Views.V1.TaxRatesView
16. Universalis.Application.Views.V2.AggregatedMarketBoardData
17. Universalis.Application.Views.V2.AggregatedMarketBoardData.AggregatedResult
18. Universalis.Application.Views.V2.AggregatedMarketBoardData.AverageSalePrice
19. Universalis.Application.Views.V2.AggregatedMarketBoardData.AverageSalePrice.Entry
20. Universalis.Application.Views.V2.AggregatedMarketBoardData.DailySaleVelocity
21. Universalis.Application.Views.V2.AggregatedMarketBoardData.DailySaleVelocity.Entry
22. Universalis.Application.Views.V2.AggregatedMarketBoardData.MedianListing
23. Universalis.Application.Views.V2.AggregatedMarketBoardData.MedianListing.Entry
24. Universalis.Application.Views.V2.AggregatedMarketBoardData.MinListing
25. Universalis.Application.Views.V2.AggregatedMarketBoardData.MinListing.Entry
26. Universalis.Application.Views.V2.AggregatedMarketBoardData.RecentPurchase
27. Universalis.Application.Views.V2.AggregatedMarketBoardData.RecentPurchase.Entry
28. Universalis.Application.Views.V2.AggregatedMarketBoardData.Result
29. Universalis.Application.Views.V2.AggregatedMarketBoardData.WorldUploadTime
30. Universalis.Application.Views.V2.CurrentlyShownMultiViewV2
31. Universalis.Application.Views.V2.HistoryMultiViewV2
32. Universalis.Application.Views.V2.UserListView
33. Universalis.Application.Views.V3.Game.DataCenter
34. Universalis.Application.Views.V3.Game.World

# Endpoints

# Available data centers

get - /api/v2/data-centers

Returns all data centers supported by the API.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/data-centers

# Available worlds

get - /api/v2/worlds

Returns the IDs and names of all worlds supported by the API.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/worlds

# Current item price

get - /api/v2/aggregated/{worldDcRegion}/{itemIds}

Retrieves aggregated market board data for the given items.
Up to 100 item IDs can be comma-separated in order to retrieve data for multiple items at once.
AverageSalePrice and DailySaleVelocity are calculated based on sales of the last 4 days.
This API uses only cached values and is therefore strongly preferred over CurrentlyShown if individual sales/listings are not required.

Responses

| Code | Description |
| --- | --- |
| 200 | Data retrieved successfully. |
| 400 | The parameters were invalid. |
| 404 | The world/DC or item requested is invalid. When requesting multiple items at once, an invalid item ID will not trigger this. Instead, the returned list of unresolved item IDs will contain the invalid item ID or IDs. |

itemIds \*

`string` *(path)* The item ID or comma-separated item IDs to retrieve data for.

worldDcRegion \*

`string` *(path)* The world, data center, or region to retrieve data for. This may be an ID or a name. Regions should be specified as Japan, Europe, North-America, Oceania, China, or 中国.

User-Agent

`string` *(header)*

CF-Connecting-IP

`string` *(header)*

https://universalis.app/api/v2/aggregated//

# Game entities

get - /api/v2/extra/content/{contentId}

Returns the content object associated with the provided content ID. Please note that this endpoint is largely untested,
and may return inconsistent data at times.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

contentId \*

`string` *(path)* The ID of the content object to retrieve.

https://universalis.app/api/v2/extra/content/

# Least-recently updated items

get - /api/v2/extra/stats/least-recently-updated

Get the least-recently updated items on the specified world or data center, along with the upload times for each item.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |
| 404 | The world/DC requested is invalid. |

world

`string` *(query)* The world to request data for.

dcName

`string` *(query)* The data center to request data for.

entries

`string` *(query)* The number of entries to return (default 50, max 200).

https://universalis.app/api/v2/extra/stats/least-recently-updated

# Market board current data

get - /api/v2/{worldDcRegion}/{itemIds}

Retrieves the data currently shown on the market board for the requested item and world or data center.
Up to 100 item IDs can be comma-separated in order to retrieve data for multiple items at once.

Responses

| Code | Description |
| --- | --- |
| 200 | Data retrieved successfully. |
| 400 | The parameters were invalid. |
| 404 | The world/DC or item requested is invalid. When requesting multiple items at once, an invalid item ID will not trigger this. Instead, the returned list of unresolved item IDs will contain the invalid item ID or IDs. |

itemIds \*

`string` *(path)* The item ID or comma-separated item IDs to retrieve data for.

worldDcRegion \*

`string` *(path)* The world, data center, or region to retrieve data for. This may be an ID or a name. Regions should be specified as Japan, Europe, North-America, Oceania, China, or 中国.

listings

`string` *(query)* The number of listings to return per item. By default, all listings will be returned.

entries

`string` *(query)* The number of recent history entries to return per item. By default, a maximum of 5 entries will be returned.

hq

`string` *(query)* Filter for HQ listings and entries. By default, both HQ and NQ listings and entries will be returned.

statsWithin

`string` *(query)* The amount of time before now to calculate stats over, in milliseconds. By default, this is 7 days.

entriesWithin

`string` *(query)* The amount of time before now to take entries within, in seconds. Negative values will be ignored.

fields

`string` *(query)* A comma separated list of fields that should be included in the response, if omitted will return all fields.
For example, if you're only interested in the listings price per unit you can set this to listings.pricePerUnit.
Note that querying multiple items changes the response schema, which should be reflected in the value provided
for this field. In this case, querying the price per unit requires setting this field to
items.listings.pricePerUnit.

User-Agent

`string` *(header)*

CF-Connecting-IP

`string` *(header)*

https://universalis.app/api/v2//

# Market board sale history

get - /api/v2/history/{worldDcRegion}/{itemIds}

Retrieves the history data for the requested item and world or data center.
Up to 100 item IDs can be comma-separated in order to retrieve data for multiple items at once.

Responses

| Code | Description |
| --- | --- |
| 200 | Data retrieved successfully. |
| 404 | The world/DC or item requested is invalid. When requesting multiple items at once, an invalid item ID will not trigger this. Instead, the returned list of unresolved item IDs will contain the invalid item ID or IDs. |

itemIds \*

`string` *(path)* The item ID or comma-separated item IDs to retrieve data for.

worldDcRegion \*

`string` *(path)* The world or data center to retrieve data for. This may be an ID or a name. Regions should be specified as Japan, Europe, North-America, Oceania, China, or 中国.

entriesToReturn

`string` *(query)* The number of entries to return per item. By default, this is set to 1800, but may be set to a maximum of 99999.

statsWithin

`string` *(query)* The amount of time before now to calculate stats over, in milliseconds. By default, this is 7 days.

entriesWithin

`string` *(query)* The amount of time before entriesUntil or now to take entries within, in seconds. Negative values will be ignored. By default, this is 7 days.

entriesUntil

`string` *(query)* The UNIX timestamp in seconds to take entries until. Negative values will be ignored. By default, this is current time.

minSalePrice

`integer` *(query)* The inclusive minimum unit sale price of entries to return.

maxSalePrice

`integer` *(query)* The inclusive maximum unit sale price of entries to return.

User-Agent

`string` *(header)*

CF-Connecting-IP

`string` *(header)*

https://universalis.app/api/v2/history//?minSalePrice=0&maxSalePrice=2147483647

# Market tax rates

get - /api/v2/tax-rates

Retrieves the current tax rate data for the specified world. This data is provided by the Retainer Vocate in each major city.

Responses

| Code | Description |
| --- | --- |
| 200 | Data retrieved successfully. |
| 404 | The world requested is invalid. |

world

`string` *(query)* The world or to retrieve data for. This may be an ID or a name.

User-Agent

`string` *(header)*

https://universalis.app/api/v2/tax-rates

# Marketable items

get - /api/v2/marketable

Returns the set of marketable item IDs.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/marketable

# Most-recently updated items

get - /api/v2/extra/stats/most-recently-updated

Get the most-recently updated items on the specified world or data center, along with the upload times for each item.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |
| 404 | The world/DC requested is invalid. |

world

`string` *(query)* The world to request data for.

dcName

`string` *(query)* The data center to request data for.

entries

`string` *(query)* The number of entries to return (default 50, max 200).

https://universalis.app/api/v2/extra/stats/most-recently-updated

# Recently updated items

get - /api/v2/extra/stats/recently-updated

Returns a list of some of the most recently updated items on the website. This endpoint
is a legacy endpoint and does not include any data on which worlds or data centers the updates happened on.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/extra/stats/recently-updated

# Upload counts by upload application

get - /api/v2/extra/stats/uploader-upload-counts

Returns the total upload counts for each client application that uploads data to Universalis.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/extra/stats/uploader-upload-counts

# Upload counts by world

get - /api/v2/extra/stats/world-upload-counts

Returns the world upload counts and proportions of the total uploads for each world.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/extra/stats/world-upload-counts

# Uploads per day

get - /api/v2/extra/stats/upload-history

Returns the number of uploads per day over the past 30 days.

Responses

| Code | Description |
| --- | --- |
| 200 | Success |

https://universalis.app/api/v2/extra/stats/upload-history

# User lists

get - /api/v2/lists/{listId}

Retrieves a user list.

Responses

| Code | Description |
| --- | --- |
| 200 | Data retrieved successfully. |
| 404 | The list requested does not exist. |

listId \*

`string` *(path)* The ID of the list to retrieve.

https://universalis.app/api/v2/lists/

# Entities

# Microsoft.AspNetCore.Mvc.ProblemDetails

```typescript
interface Microsoft.AspNetCore.Mvc.ProblemDetails {
  type?: string;
  title?: string;
  status?: number; // int32
  detail?: string;
  instance?: string;
}
```

# Universalis.Application.Views.V1.CurrentlyShownView

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```

# Universalis.Application.Views.V1.Extra.ContentView

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```

# Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView {
  // A list of item upload information in timestamp-descending order.
  items?: Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView[];
}
```

# Universalis.Application.Views.V1.Extra.Stats.RecentlyUpdatedItemsView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.RecentlyUpdatedItemsView {
  // A list of item IDs, with the most recent first.
  items?: number[];
}
```

# Universalis.Application.Views.V1.Extra.Stats.SourceUploadCountView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.SourceUploadCountView {
  // The name of the client application.
  sourceName?: string;
  // The number of uploads originating from the client application.
  uploadCount: number;
}
```

# Universalis.Application.Views.V1.Extra.Stats.UploadCountHistoryView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.UploadCountHistoryView {
  // The list of upload counts per day, over the past 30 days.
  uploadCountByDay?: number[];
}
```

# Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView {
  // The item ID.
  itemID: number; // int32
  // The last upload time for the item on the listed world.
  lastUploadTime: number;
  // The world ID.
  worldID: number; // int32
  // The world name.
  worldName?: string;
}
```

# Universalis.Application.Views.V1.Extra.Stats.WorldUploadCountView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.WorldUploadCountView {
  // The number of times an upload has occurred on this world.
  count: number;
  // The proportion of uploads on this world to the total number of uploads.
  proportion: number;
}
```

# Universalis.Application.Views.V1.HistoryView

```typescript
interface Universalis.Application.Views.V1.HistoryView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The historical sales.
  entries?: Universalis.Application.Views.V1.MinimizedSaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // A map of quantities to sale counts, representing the number of sales of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ sale counts, representing the number of sales of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ sale counts, representing the number of sales of each quantity.
  stackSizeHistogramHQ?: Object;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  hqSaleVelocity: number;
  // The world name, if applicable.
  worldName?: string;
}
```

# Universalis.Application.Views.V1.ListingView

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
0

# Universalis.Application.Views.V1.MateriaView

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
1

# Universalis.Application.Views.V1.MinimizedSaleView

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
2

# Universalis.Application.Views.V1.SaleView

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
3

# Universalis.Application.Views.V1.TaxRatesView

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
4

# Universalis.Application.Views.V2.AggregatedMarketBoardData

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
5

# Universalis.Application.Views.V2.AggregatedMarketBoardData.AggregatedResult

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
6

# Universalis.Application.Views.V2.AggregatedMarketBoardData.AverageSalePrice

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
7

# Universalis.Application.Views.V2.AggregatedMarketBoardData.AverageSalePrice.Entry

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
8

# Universalis.Application.Views.V2.AggregatedMarketBoardData.DailySaleVelocity

```typescript
interface Universalis.Application.Views.V1.CurrentlyShownView {
  // The item ID.
  itemID: number; // int32
  // The world ID, if applicable.
  worldID?: number; // int32
  // The last upload time for this endpoint, in milliseconds since the UNIX epoch.
  lastUploadTime: number; // int64
  // The currently-shown listings.
  listings?: Universalis.Application.Views.V1.ListingView[];
  // The currently-shown sales.
  recentHistory?: Universalis.Application.Views.V1.SaleView[];
  // The DC name, if applicable.
  dcName?: string;
  // The region name, if applicable.
  regionName?: string;
  // The average listing price.
  currentAveragePrice: number;
  // The average NQ listing price.
  currentAveragePriceNQ: number;
  // The average HQ listing price.
  currentAveragePriceHQ: number;
  // The average number of sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  regularSaleVelocity: number;
  // The average number of NQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  nqSaleVelocity: number;
  // The average number of HQ sales per day, over the past seven days (or the entirety of the shown sales, whichever comes first).
  // This number will tend to be the same for every item, because the number of shown sales is the same and over the same period.
  // This statistic is more useful in historical queries.
  hqSaleVelocity: number;
  // The average sale price.
  averagePrice: number;
  // The average NQ sale price.
  averagePriceNQ: number;
  // The average HQ sale price.
  averagePriceHQ: number;
  // The minimum listing price.
  minPrice: number; // int32
  // The minimum NQ listing price.
  minPriceNQ: number; // int32
  // The minimum HQ listing price.
  minPriceHQ: number; // int32
  // The maximum listing price.
  maxPrice: number; // int32
  // The maximum NQ listing price.
  maxPriceNQ: number; // int32
  // The maximum HQ listing price.
  maxPriceHQ: number; // int32
  // A map of quantities to listing counts, representing the number of listings of each quantity.
  stackSizeHistogram?: Object;
  // A map of quantities to NQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramNQ?: Object;
  // A map of quantities to HQ listing counts, representing the number of listings of each quantity.
  stackSizeHistogramHQ?: Object;
  // The world name, if applicable.
  worldName?: string;
  // The last upload times in milliseconds since epoch for each world in the response, if this is a DC request.
  worldUploadTimes?: Object;
  // The number of listings retrieved for the request. When using the "listings" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  listingsCount: number; // int32
  // The number of sale entries retrieved for the request. When using the "entries" limit parameter, this may be
  // different from the number of sale entries returned in an API response.
  recentHistoryCount: number; // int32
  // The number of items (not listings) up for sale.
  unitsForSale: number; // int32
  // The number of items (not sale entries) sold over the retrieved sales.
  unitsSold: number; // int32
  // Whether this item has ever been updated. Useful for newly-released items.
  hasData: boolean;
}
```
9

# Universalis.Application.Views.V2.AggregatedMarketBoardData.DailySaleVelocity.Entry

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
0

# Universalis.Application.Views.V2.AggregatedMarketBoardData.MedianListing

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
1

# Universalis.Application.Views.V2.AggregatedMarketBoardData.MedianListing.Entry

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
2

# Universalis.Application.Views.V2.AggregatedMarketBoardData.MinListing

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
3

# Universalis.Application.Views.V2.AggregatedMarketBoardData.MinListing.Entry

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
4

# Universalis.Application.Views.V2.AggregatedMarketBoardData.RecentPurchase

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
5

# Universalis.Application.Views.V2.AggregatedMarketBoardData.RecentPurchase.Entry

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
6

# Universalis.Application.Views.V2.AggregatedMarketBoardData.Result

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
7

# Universalis.Application.Views.V2.AggregatedMarketBoardData.WorldUploadTime

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
8

# Universalis.Application.Views.V2.CurrentlyShownMultiViewV2

```typescript
interface Universalis.Application.Views.V1.Extra.ContentView {
  // The content ID of the object.
  contentID?: string;
  // The content type of this object.
  contentType?: string;
  // The character name associated with this character object, if this is one.
  characterName?: string;
}
```
9

# Universalis.Application.Views.V2.HistoryMultiViewV2

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView {
  // A list of item upload information in timestamp-descending order.
  items?: Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView[];
}
```
0

# Universalis.Application.Views.V2.UserListView

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView {
  // A list of item upload information in timestamp-descending order.
  items?: Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView[];
}
```
1

# Universalis.Application.Views.V3.Game.DataCenter

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView {
  // A list of item upload information in timestamp-descending order.
  items?: Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView[];
}
```
2

# Universalis.Application.Views.V3.Game.World

```typescript
interface Universalis.Application.Views.V1.Extra.Stats.MostRecentlyUpdatedItemsView {
  // A list of item upload information in timestamp-descending order.
  items?: Universalis.Application.Views.V1.Extra.Stats.WorldItemRecencyView[];
}
```
3
