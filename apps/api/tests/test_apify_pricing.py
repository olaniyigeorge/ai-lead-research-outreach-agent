from unittest.mock import AsyncMock, patch

import httpx
import pytest

from apps.api.integrations import apify_client


@pytest.fixture(autouse=True)
def _reset_price_cache():
    """The lookup caches its result at module scope for the process's
    lifetime -- reset it around each test so tests don't leak state into
    each other."""
    apify_client._cached_price_per_result_usd = None
    yield
    apify_client._cached_price_per_result_usd = None


@pytest.mark.asyncio
async def test_get_price_per_result_usd_parses_live_pricing():
    fake_response = httpx.Response(
        200,
        json={
            "data": {
                "pricingInfos": [
                    {
                        "pricingPerEvent": {
                            "actorChargeEvents": {
                                "apify-default-dataset-item": {
                                    "eventTieredPricingUsd": {"FREE": {"tieredEventPriceUsd": 0.006}}
                                }
                            }
                        }
                    }
                ]
            }
        },
        request=httpx.Request("GET", "https://api.apify.com/v2/acts/x"),
    )

    with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=fake_response)):
        price = await apify_client.get_price_per_result_usd()

    assert price == 0.006


@pytest.mark.asyncio
async def test_get_price_per_result_usd_falls_back_on_network_error():
    with patch.object(httpx.AsyncClient, "get", AsyncMock(side_effect=httpx.ConnectError("down"))):
        price = await apify_client.get_price_per_result_usd()

    assert price == apify_client._FALLBACK_PRICE_PER_RESULT_USD


@pytest.mark.asyncio
async def test_get_price_per_result_usd_is_cached_across_calls():
    fake_response = httpx.Response(
        200,
        json={
            "data": {
                "pricingInfos": [
                    {
                        "pricingPerEvent": {
                            "actorChargeEvents": {
                                "apify-default-dataset-item": {
                                    "eventTieredPricingUsd": {"FREE": {"tieredEventPriceUsd": 0.006}}
                                }
                            }
                        }
                    }
                ]
            }
        },
        request=httpx.Request("GET", "https://api.apify.com/v2/acts/x"),
    )
    mock_get = AsyncMock(return_value=fake_response)

    with patch.object(httpx.AsyncClient, "get", mock_get):
        await apify_client.get_price_per_result_usd()
        await apify_client.get_price_per_result_usd()

    assert mock_get.call_count == 1
