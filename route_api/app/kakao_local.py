"""ONE-TIME coordinate lookup via Kakao Local keyword search.

This is NOT a paid route request and NOT a place-detail parser. For safety,
we only accept a result if its Kakao `id` exactly matches the source place_id.
Never pick a similarly named restaurant with a different place ID.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float
    address: str


class KakaoLocalSearch:
    URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'

    def __init__(self, api_key: str, *, client: httpx.Client | None = None):
        if not api_key.strip():
            raise ValueError('KAKAO_REST_API_KEY is required')
        self.api_key = api_key.strip()
        self.client = client

    def find_exact_id(self, place_id: str, name: str) -> Coordinate | None:
        headers = {'Authorization': f'KakaoAK {self.api_key}'}
        queries = (name, f'부산 {name}')
        with httpx.Client(timeout=12) if self.client is None else _BorrowedClient(self.client) as client:
            for query in dict.fromkeys(queries):
                for page in range(1, 4):
                    try:
                        response = client.get(self.URL, headers=headers, params={'query': query, 'page': page, 'size': 15})
                        response.raise_for_status()
                        payload = response.json()
                    except httpx.HTTPStatusError as exc:
                        code = exc.response.status_code
                        if code == 401 or code == 403:
                            raise RuntimeError('Kakao API key rejected or lacks Local Search permission') from exc
                        if code == 429:
                            raise RuntimeError('Kakao API quota exceeded; stop and retry later') from exc
                        raise RuntimeError(f'Kakao Local HTTP {code}') from exc
                    except (httpx.HTTPError, ValueError) as exc:
                        raise RuntimeError(f'Kakao Local lookup failed: {type(exc).__name__}') from exc
                    for result in payload.get('documents', []):
                        if str(result.get('id')) != place_id:
                            continue
                        latitude = float(result['y'])
                        longitude = float(result['x'])
                        if not (33 < latitude < 39 and 124 < longitude < 133):
                            raise RuntimeError(f'Kakao result out of Korea range: {place_id}')
                        return Coordinate(latitude, longitude, result.get('road_address_name') or result.get('address_name') or '')
                    if payload.get('meta', {}).get('is_end', True):
                        break
        return None


class _BorrowedClient:
    def __init__(self, client: httpx.Client):
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, *_: object) -> None:
        pass
