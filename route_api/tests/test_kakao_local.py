import httpx
from app.kakao_local import KakaoLocalSearch


def test_kakao_only_exact_place_id_matches():
    requested=[]
    def respond(request):
        requested.append(request)
        assert request.headers['Authorization']=='KakaoAK mocked-key'
        return httpx.Response(200,json={
            'meta':{'is_end':True},
            'documents':[
                {'id':'999','place_name':'식당 A','x':'129.01','y':'35.12'},
                {'id':'123','place_name':'식당 A 본점','x':'129.06','y':'35.15', 'road_address_name':'부산광역시 실제 주소'},
            ],
        })
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        service=KakaoLocalSearch('mocked-key',client=client)
        found=service.find_exact_id('123','식당 A')
        assert found is not None and found.longitude==129.06
        assert found.latitude==35.15
        assert service.find_exact_id('888','식당 A') is None
    assert len(requested)==3 # 1 matching + 2 queries for not found
