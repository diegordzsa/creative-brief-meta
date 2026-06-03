import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _generate_mock_ads(n: int) -> list[dict[str, Any]]:
    base_date = datetime.now(timezone.utc) - timedelta(days=20)
    mock_ads = []
    profiles = [
        {"ctr_mult": 0.035, "roas": 4.2, "hook_mult": 0.42, "hold_mult": 0.18, "days": 45},
        {"ctr_mult": 0.030, "roas": 3.8, "hook_mult": 0.38, "hold_mult": 0.15, "days": 35},
        {"ctr_mult": 0.022, "roas": 2.5, "hook_mult": 0.28, "hold_mult": 0.10, "days": 20},
        {"ctr_mult": 0.018, "roas": 2.0, "hook_mult": 0.24, "hold_mult": 0.08, "days": 15},
        {"ctr_mult": 0.015, "roas": 1.8, "hook_mult": 0.20, "hold_mult": 0.06, "days": 10},
        {"ctr_mult": 0.012, "roas": 1.5, "hook_mult": 0.18, "hold_mult": 0.05, "days": 8},
        {"ctr_mult": 0.010, "roas": 1.2, "hook_mult": 0.15, "hold_mult": 0.04, "days": 5},
        {"ctr_mult": 0.008, "roas": 0.9, "hook_mult": 0.12, "hold_mult": 0.035, "days": 4},
        {"ctr_mult": 0.006, "roas": 0.6, "hook_mult": 0.10, "hold_mult": 0.03, "days": 3},
        {"ctr_mult": 0.005, "roas": 0.4, "hook_mult": 0.08, "hold_mult": 0.025, "days": 2},
    ]

    for i in range(n):
        p = profiles[i % len(profiles)]
        created = base_date - timedelta(days=p["days"])
        spend = round(500 - (i * 35), 2)
        impressions = int(spend * 200)
        clicks = int(impressions * p["ctr_mult"])
        video_3s_views = int(impressions * p["hook_mult"])
        thruplay = int(impressions * p["hold_mult"])

        mock_ads.append({
            "id": f"mock_ad_{1000 + i}",
            "name": f"HB_ES_Video_{['REDENSIFY_Testimonio', 'AntiCaida_Podcast', 'Pack_Completo_React', 'Serum_Salon', 'REDENSIFY_Emotional', 'AntiCaida_Paradigm', 'Pack_3D_Authority', 'Serum_Bottleneck', 'REDENSIFY_UGC', 'AntiCaida_Montage'][i % 10]}_{i + 1:02d}",
            "status": "ACTIVE",
            "created_time": created.isoformat(),
            "creative": {
                "id": f"creative_{2000 + i}",
                "name": f"Creative_{i + 1}",
                "video_id": f"video_{3000 + i}",
                "thumbnail_url": f"https://example.com/thumb_{i}.jpg",
            },
            "adset": {
                "name": f"Adset_Mujeres_25-55_ES_{i + 1}",
                "targeting": {"age_min": 25, "age_max": 55, "genders": [2], "geo_locations": {"countries": ["ES"]}},
            },
            "campaign": {
                "name": f"HB_ES_Conversiones_Q2_{i + 1}",
                "objective": "OUTCOME_SALES",
            },
            "insights": {
                "spend": str(spend),
                "impressions": str(impressions),
                "clicks": str(clicks),
                "ctr": str(round(clicks / impressions * 100, 4)) if impressions else "0",
                "purchase_roas": [{"value": str(p["roas"])}],
                "video_play_actions": [{"value": str(video_3s_views)}],
                "video_thruplay_watched_actions": [{"value": str(thruplay)}],
                "video_p25_watched_actions": [{"value": str(int(impressions * 0.30))}],
                "video_p50_watched_actions": [{"value": str(int(impressions * 0.22))}],
                "video_p75_watched_actions": [{"value": str(int(impressions * 0.16))}],
                "video_p100_watched_actions": [{"value": str(int(impressions * 0.10))}],
                "date_start": (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"),
                "date_stop": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
        })
    return mock_ads


def _parse_metric(value: Any) -> float:
    if isinstance(value, list) and value:
        return float(value[0].get("value", 0))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def normalize_ad(raw_ad: dict[str, Any]) -> dict[str, Any]:
    insights = raw_ad.get("insights", {})
    impressions = _parse_metric(insights.get("impressions", 0))
    video_3s = _parse_metric(insights.get("video_play_actions", 0))
    thruplay = _parse_metric(insights.get("video_thruplay_watched_actions", 0))

    created_str = raw_ad.get("created_time", "")
    if created_str:
        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        days_active = (datetime.now(timezone.utc) - created_dt).days
    else:
        days_active = 0

    return {
        "id": raw_ad["id"],
        "name": raw_ad.get("name", ""),
        "status": raw_ad.get("status", ""),
        "created_time": created_str,
        "days_active": days_active,
        "creative": raw_ad.get("creative", {}),
        "adset": raw_ad.get("adset", {}),
        "campaign": raw_ad.get("campaign", {}),
        "metrics": {
            "spend": _parse_metric(insights.get("spend", 0)),
            "impressions": impressions,
            "clicks": _parse_metric(insights.get("clicks", 0)),
            "ctr": _parse_metric(insights.get("ctr", 0)),
            "purchase_roas": _parse_metric(insights.get("purchase_roas", 0)),
            "video_3s_views": video_3s,
            "thruplay": thruplay,
            "hook_rate": (video_3s / impressions * 100) if impressions else 0.0,
            "hold_rate": (thruplay / impressions) if impressions else 0.0,
        },
    }


class MetaClient:
    def __init__(self, access_token: str, ad_account_id: str):
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.mock_mode = not access_token
        if self.mock_mode:
            logger.warning("META_ACCESS_TOKEN not set — running in MOCK mode")

    def get_top_video_ads(self, n: int = 10, date_preset: str = "last_30_days") -> list[dict[str, Any]]:
        if self.mock_mode:
            logger.info(f"Returning {n} mock ads")
            raw_ads = _generate_mock_ads(n)
        else:
            raw_ads = self._fetch_from_api(n, date_preset)

        normalized = [normalize_ad(ad) for ad in raw_ads]
        normalized.sort(key=lambda a: a["metrics"]["spend"], reverse=True)
        return normalized[:n]

    def _fetch_from_api(self, n: int, date_preset: str) -> list[dict[str, Any]]:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount
        from config.settings import META_AD_FIELDS, META_INSIGHT_FIELDS

        FacebookAdsApi.init(access_token=self.access_token)
        account = AdAccount(self.ad_account_id)

        params = {
            "filtering": [
                {"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]},
            ],
            "date_preset": date_preset,
            "limit": n * 2,
        }

        fields_str = META_AD_FIELDS + [
            f"insights{{{','.join(META_INSIGHT_FIELDS)}}}"
        ]

        ads = account.get_ads(fields=fields_str, params=params)
        results = []
        for ad in ads:
            ad_data = dict(ad)
            insights_data = ad_data.get("insights", {})
            if isinstance(insights_data, dict) and "data" in insights_data:
                ad_data["insights"] = insights_data["data"][0] if insights_data["data"] else {}
            results.append(ad_data)

        video_ads = [
            a for a in results
            if a.get("creative", {}).get("video_id")
        ]

        video_ads.sort(key=lambda a: float(a.get("insights", {}).get("spend", "0")), reverse=True)
        return video_ads[:n]

    def get_video_url(self, video_id: str) -> str:
        if self.mock_mode:
            return f"https://example.com/mock_video_{video_id}.mp4"

        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.advideo import AdVideo

        FacebookAdsApi.init(access_token=self.access_token)
        video = AdVideo(video_id)
        video.api_get(fields=["source"])
        return video.get("source", "")
