import logging
from typing import Any

from app.core import cache
from app.core.config import settings
from app.core.http_client import xivapi_client

log = logging.getLogger("xivapi")

PAGE_LIMIT = 500


class XIVAPIClient:
    def __init__(self) -> None:
        self.base = settings.XIVAPI_BASE.rstrip("/")

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        client = xivapi_client()
        url = f"{self.base}{path}"
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def populate_vendor_items(self, *, force: bool = False) -> list[dict]:
        if not force and cache.exists("vendor_items"):
            log.info("cache hit vendor_items")
            return cache.read("vendor_items") or []

        log.info("populating vendor_items from XIVAPI v2 /sheet/GilShopItem")
        out: list[dict] = []
        seen: set[tuple[int, int]] = set()
        after: int | None = None
        page = 0
        while True:
            params: dict[str, Any] = {
                "fields": "Item.Name,Item.PriceMid",
                "limit": PAGE_LIMIT,
            }
            if after is not None:
                params["after"] = after
            data = await self._get_json("/sheet/GilShopItem", params=params)
            rows = data.get("rows") or []
            if not rows:
                break
            new_count = 0
            for r in rows:
                row_id = r.get("row_id")
                sub = r.get("subrow_id", 0)
                if row_id is None:
                    continue
                key = (int(row_id), int(sub))
                if key in seen:
                    continue
                seen.add(key)
                new_count += 1
                fields = r.get("fields") or {}
                item = fields.get("Item") or {}
                iid = item.get("row_id") or item.get("value")
                ifields = item.get("fields") or {}
                price = ifields.get("PriceMid") or 0
                if not iid or not isinstance(price, int) or price <= 0:
                    continue
                out.append({
                    "itemId": int(iid),
                    "name": ifields.get("Name") or "",
                    "gilPrice": int(price),
                    "shopId": int(row_id),
                    "subrowId": int(sub),
                    "shopName": "",
                })
            page += 1
            log.info(
                "vendor v2 page=%d rows=%d new=%d total=%d after=%s",
                page, len(rows), new_count, len(out), after,
            )
            if new_count == 0:
                break
            last_row_id = int(rows[-1]["row_id"])
            next_after = last_row_id - 1
            if after is not None and next_after <= after:
                break
            after = next_after

        await self._enrich_shop_names(out)
        cache.write("vendor_items", out)
        log.info("vendor_items cached n=%d", len(out))
        return out

    async def populate_maps(self, *, force: bool = False) -> list[dict]:
        """Treasure-map catalogue from XIVAPI v2 /sheet/TreasureHuntRank.

        TreasureHuntRank.ItemName is the authoritative list of treasure-map
        items — filtered here to marketable ones (drops non-tradeable special
        maps that also use the "Timeworn" name). Auto-includes new maps when
        Square Enix adds a rank, so name-pattern guessing is unnecessary.
        """
        if not force and cache.exists("maps"):
            log.info("cache hit maps")
            return cache.read("maps") or []
        log.info("populating maps from XIVAPI v2 /sheet/TreasureHuntRank")
        marketable = {int(i) for i in (cache.read("marketable") or [])}
        out: list[dict] = []
        seen: set[int] = set()
        after: int | None = None
        while True:
            params: dict[str, Any] = {"fields": "ItemName.Name", "limit": PAGE_LIMIT}
            if after is not None:
                params["after"] = after
            data = await self._get_json("/sheet/TreasureHuntRank", params=params)
            rows = data.get("rows") or []
            if not rows:
                break
            last_row_id = after or 0
            for r in rows:
                rid = r.get("row_id")
                if rid is not None:
                    last_row_id = max(last_row_id, int(rid))
                item = (r.get("fields") or {}).get("ItemName") or {}
                if not isinstance(item, dict):
                    continue
                iid = item.get("row_id")
                name = ((item.get("fields") or {}).get("Name") or "").strip()
                if not iid or int(iid) in seen:
                    continue
                seen.add(int(iid))
                if int(iid) in marketable and name:
                    out.append({"item_id": int(iid), "name": name})
            if len(rows) < PAGE_LIMIT or last_row_id == (after or 0):
                break
            after = last_row_id
        cache.write("maps", out)
        log.info("maps cached n=%d (marketable treasure maps)", len(out))
        return out

    async def _scan_npc_shop_map(self, shop_ids: set[int]) -> dict[int, int]:
        """Walk ENpcBase, build shopId -> first npcId map."""
        out: dict[int, int] = {}
        after: int | None = None
        page = 0
        while True:
            params: dict[str, Any] = {"fields": "ENpcData[].value", "limit": PAGE_LIMIT}
            if after is not None:
                params["after"] = after
            data = await self._get_json("/sheet/ENpcBase", params=params)
            rows = data.get("rows") or []
            if not rows:
                break
            last_row_id = after or 0
            for r in rows:
                rid = r.get("row_id")
                if rid is None:
                    continue
                last_row_id = max(last_row_id, int(rid))
                for e in (r.get("fields") or {}).get("ENpcData") or []:
                    val = e.get("value", 0) if isinstance(e, dict) else 0
                    if val in shop_ids and val not in out:
                        out[val] = int(rid)
            page += 1
            if page == 1 or page % 20 == 0 or len(rows) < PAGE_LIMIT:
                log.info("enpc page=%d rows=%d shops_mapped=%d/%d", page, len(rows), len(out), len(shop_ids))
            if len(out) == len(shop_ids):
                log.info("enpc scan complete (all shops mapped) page=%d", page)
                break
            if len(rows) < PAGE_LIMIT:
                break
            if last_row_id == (after or 0):
                break
            after = last_row_id
        return out

    async def _fetch_npc_names(self, npc_ids: list[int]) -> dict[int, str]:
        out: dict[int, str] = {}
        for i in range(0, len(npc_ids), 100):
            chunk = npc_ids[i:i + 100]
            ids_str = ",".join(str(n) for n in chunk)
            data = await self._get_json(
                "/sheet/ENpcResident",
                params={"rows": ids_str, "fields": "Singular,Title"},
            )
            for r in data.get("rows", []):
                f = r.get("fields") or {}
                name = (f.get("Singular") or "").strip()
                title = (f.get("Title") or "").strip()
                if name and title:
                    label = f"{name} ({title})"
                elif name:
                    label = name
                elif title:
                    label = title
                else:
                    label = ""
                out[int(r["row_id"])] = label
        return out

    async def populate_item_icons(self, *, force: bool = False) -> dict[str, str]:
        if not force and cache.exists("item_icons"):
            log.info("cache hit item_icons")
            return cache.read("item_icons") or {}
        log.info("populating item_icons from XIVAPI v2 /sheet/Item")
        out: dict[str, str] = {}
        after: int | None = None
        page = 0
        while True:
            params: dict[str, Any] = {"fields": "Icon.path", "limit": PAGE_LIMIT}
            if after is not None:
                params["after"] = after
            data = await self._get_json("/sheet/Item", params=params)
            rows = data.get("rows") or []
            if not rows:
                break
            last_row_id = after or 0
            for r in rows:
                rid = r.get("row_id")
                if rid is None:
                    continue
                last_row_id = max(last_row_id, int(rid))
                icon = (r.get("fields") or {}).get("Icon") or {}
                path = icon.get("path") if isinstance(icon, dict) else None
                if path:
                    out[str(rid)] = path
            page += 1
            if page == 1 or page % 20 == 0 or len(rows) < PAGE_LIMIT:
                log.info("item icons page=%d rows=%d total=%d", page, len(rows), len(out))
            if len(rows) < PAGE_LIMIT:
                break
            if last_row_id == (after or 0):
                break
            after = last_row_id
        cache.write("item_icons", out)
        log.info("item_icons cached n=%d", len(out))
        return out

    async def _enrich_shop_names(self, vendor_rows: list[dict]) -> None:
        shop_ids = {int(r["shopId"]) for r in vendor_rows if r.get("shopId")}
        if not shop_ids:
            return
        log.info("looking up NPC names for %d unique shops", len(shop_ids))
        shop_to_npc = await self._scan_npc_shop_map(shop_ids)
        npc_ids = sorted(set(shop_to_npc.values()))
        log.info("found %d shop->NPC links, fetching %d NPC names", len(shop_to_npc), len(npc_ids))
        npc_names = await self._fetch_npc_names(npc_ids)
        shop_to_name = {sid: npc_names.get(nid, "") for sid, nid in shop_to_npc.items()}
        for row in vendor_rows:
            row["shopName"] = shop_to_name.get(int(row.get("shopId") or 0), "")
        named = sum(1 for r in vendor_rows if r["shopName"])
        log.info("named %d/%d vendor rows", named, len(vendor_rows))
