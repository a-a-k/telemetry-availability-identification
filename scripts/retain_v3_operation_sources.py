"""Retain bounded exact upstream source files for operation/observation semantics."""
import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha1, sha256
import json
from pathlib import Path
import subprocess

ROOT = Path('docs/evidence/v3-operation-sources')
SPECS = {
    'deathstar': ('delimitrou/DeathStarBench', '6ecb09706140f8730b5385c08f1386c654c3c526', {
        'LICENSE': 'LICENSE',
        'compose.lua': 'socialNetwork/nginx-web-server/lua-scripts/wrk2-api/post/compose.lua',
        'home-read.lua': 'socialNetwork/nginx-web-server/lua-scripts/wrk2-api/home-timeline/read.lua',
        'user-read.lua': 'socialNetwork/nginx-web-server/lua-scripts/wrk2-api/user-timeline/read.lua',
        'ComposePostHandler.h': 'socialNetwork/src/ComposePostService/ComposePostHandler.h',
        'HomeTimelineHandler.h': 'socialNetwork/src/HomeTimelineService/HomeTimelineHandler.h',
        'UserTimelineHandler.h': 'socialNetwork/src/UserTimelineService/UserTimelineHandler.h',
        'PostStorageHandler.h': 'socialNetwork/src/PostStorageService/PostStorageHandler.h',
        'tracing.h': 'socialNetwork/src/tracing.h'}),
    'otel': ('open-telemetry/opentelemetry-demo', '8c47d47c9ac27710d2b2a153bcd53e483bffe66d', {
        'LICENSE': 'LICENSE',
        'cart.ts': 'src/frontend/pages/api/cart.ts',
        'checkout.ts': 'src/frontend/pages/api/checkout.ts',
        'ProductCatalog.service.ts': 'src/frontend/services/ProductCatalog.service.ts',
        'checkout-main.go': 'src/checkout/main.go',
        'product-catalog-main.go': 'src/product-catalog/main.go'}),
    'petclinic': ('spring-petclinic/spring-petclinic-microservices', '3858f9c630cf989bb6809a86edf47c2be78dc9f1', {
        'LICENSE': 'LICENSE',
        'ApiGatewayController.java': 'spring-petclinic-api-gateway/src/main/java/org/springframework/samples/petclinic/api/boundary/web/ApiGatewayController.java',
        'VisitsServiceClient.java': 'spring-petclinic-api-gateway/src/main/java/org/springframework/samples/petclinic/api/application/VisitsServiceClient.java',
        'CustomersServiceClient.java': 'spring-petclinic-api-gateway/src/main/java/org/springframework/samples/petclinic/api/application/CustomersServiceClient.java',
        'VisitResource.java': 'spring-petclinic-visits-service/src/main/java/org/springframework/samples/petclinic/visits/web/VisitResource.java',
        'VisitRepository.java': 'spring-petclinic-visits-service/src/main/java/org/springframework/samples/petclinic/visits/model/VisitRepository.java',
        'OwnerResource.java': 'spring-petclinic-customers-service/src/main/java/org/springframework/samples/petclinic/customers/web/OwnerResource.java',
        'OwnerRepository.java': 'spring-petclinic-customers-service/src/main/java/org/springframework/samples/petclinic/customers/model/OwnerRepository.java',
        'VetResource.java': 'spring-petclinic-vets-service/src/main/java/org/springframework/samples/petclinic/vets/web/VetResource.java'})}


def fetch(spec):
    profile, repository, commit, local, path = spec
    response = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/contents/{path}?ref={commit}']))
    assert response['type'] == 'file' and response['path'] == path and response['encoding'] == 'base64'
    data = base64.b64decode(response['content'])
    assert len(data) == response['size'] and len(data) < 100000
    assert sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == response['sha']
    record = dict(profile=profile, repository=repository, commit=commit, path=path, local=f'{profile}-{local}',
        bytes=len(data), git_blob=response['sha'], sha256=sha256(data).hexdigest(),
        url=f'https://github.com/{repository}/blob/{commit}/{path}')
    return record, data


def main():
    jobs = [(profile, repo, commit, local, path) for profile, (repo, commit, paths) in SPECS.items() for local, path in paths.items()]
    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(fetch, jobs))
    ROOT.mkdir(parents=True, exist_ok=True)
    for record, data in results:
        (ROOT/record['local']).write_bytes(data)
    (ROOT/'sources.json').write_bytes((json.dumps([r for r, _ in results], indent=2) + '\n').encode())
    (ROOT/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps(dict(files=len(results), bytes=sum(len(v) for _, v in results))))


if __name__ == '__main__':
    main()
