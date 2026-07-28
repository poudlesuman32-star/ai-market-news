from __future__ import annotations
import argparse, hashlib, json, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
CONTRACT_ID='PPI-ASSET-CLASSIFICATION-SOURCE-READINESS-001-R1'
INVENTORY_ID='PPI-ASSET-CLASSIFICATION-SOURCES-001-R1'
ENDPOINT='https://api.openfigi.com/v3/mapping/values/securityType2'
HOST='api.openfigi.com'; PATH='/v3/mapping/values/securityType2'
MAX_BYTES=1_000_000; MAX_ATTEMPTS=3
REQUIRED_VALUES={'Common Stock','Depositary Receipt'}
OUTPUT_PATHS={'readiness.json','readiness.md'}
class ReadinessError(RuntimeError): pass
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def canon(v): return (json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def digest(v): return hashlib.sha256(v).hexdigest()
def read_object(path):
    try: value=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError) as exc: raise ReadinessError(f'Invalid JSON at {path}: {exc}') from exc
    if not isinstance(value,dict): raise ReadinessError(f'{path} must contain one object')
    return value
def validate_endpoint(url=ENDPOINT):
    p=urllib.parse.urlparse(url)
    if (p.scheme,p.hostname,p.path,p.query,p.fragment)!=('https',HOST,PATH,'',''): raise ReadinessError('OpenFIGI enum endpoint left the frozen allowlist')
class RedirectGuard(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_endpoint(newurl); return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch_values(opener=None,sleep=time.sleep):
    validate_endpoint(); opener=opener or urllib.request.build_opener(RedirectGuard())
    req=urllib.request.Request(ENDPOINT,headers={'Accept':'application/json','User-Agent':'PPI-Asset-Classification-Readiness/1.0'})
    errors=[]
    for attempt in range(1,MAX_ATTEMPTS+1):
        try:
            with opener.open(req,timeout=30) as response:
                raw=response.read(MAX_BYTES+1)
                if response.status!=200 or len(raw)>MAX_BYTES: raise ReadinessError('OpenFIGI enum response failed status or size gate')
                try: payload=json.loads(raw)
                except json.JSONDecodeError as exc: raise ReadinessError(f'OpenFIGI enum response is invalid JSON: {exc}') from exc
                values=payload.get('values') if isinstance(payload,dict) else None
                if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v for v in values): raise ReadinessError('OpenFIGI enum response lacks a valid values array')
                if len(values)!=len(set(values)): raise ReadinessError('OpenFIGI enum response contains duplicate values')
                return sorted(values),{'status':response.status,'attempts':attempt,'response_bytes':len(raw),'response_sha256':digest(raw)}
        except urllib.error.HTTPError as exc:
            errors.append(f'attempt={attempt}:HTTP:{exc.code}')
            if exc.code not in {429,500,503} or attempt==MAX_ATTEMPTS: break
        except urllib.error.URLError as exc:
            errors.append(f'attempt={attempt}:URL:{exc.reason}')
            if attempt==MAX_ATTEMPTS: break
        sleep(2.5*attempt)
    raise ReadinessError('OpenFIGI enum probe failed: '+'; '.join(errors))
def validate_inventory(value):
    if value.get('inventory_id')!=INVENTORY_ID: raise ReadinessError('Asset-classification source inventory ID differs')
    prohibited=set(value.get('prohibited_methods') or [])
    required={'security_name_substring_classification','ticker_suffix_classification','issuer_country_only_classification','absence_of_f6_as_common_stock_proof'}
    if not required.issubset(prohibited): raise ReadinessError('Required anti-heuristic policies are missing')
    sources=value.get('sources')
    if not isinstance(sources,list): raise ReadinessError('Source inventory must contain a source list')
    by_id={}
    for source in sources:
        if not isinstance(source,dict) or not isinstance(source.get('source_id'),str): raise ReadinessError('Every source must have source_id')
        if source['source_id'] in by_id: raise ReadinessError('Source IDs must be unique')
        by_id[source['source_id']]=source
    expected={'openfigi_v3_instrument_metadata','sec_edgar_f6_subject_filings','sec_company_tickers_exchange','nasdaq_symbol_directory'}
    if set(by_id)!=expected: raise ReadinessError('Source inventory IDs differ from the frozen set')
    if by_id['openfigi_v3_instrument_metadata'].get('status')!='approved_objective_instrument_metadata': raise ReadinessError('OpenFIGI source status differs')
    if by_id['sec_edgar_f6_subject_filings'].get('status')!='approved_positive_adr_evidence_pending_collector': raise ReadinessError('SEC F-6 source status differs')
    if by_id['sec_company_tickers_exchange'].get('classification_authority') is not False: raise ReadinessError('SEC ticker seed must not classify')
    if by_id['nasdaq_symbol_directory'].get('status')!='pending_terms_and_semantics_review': raise ReadinessError('Nasdaq directory must remain pending')
    return by_id
def validate_contract(value):
    if value.get('contract_id')!=CONTRACT_ID or value.get('inventory_id')!=INVENTORY_ID: raise ReadinessError('Readiness contract identity differs')
    probe=value.get('probe') or {}
    if probe.get('endpoint')!=ENDPOINT or probe.get('required_values')!=['Common Stock','Depositary Receipt']: raise ReadinessError('Readiness probe is not frozen')
    policy=value.get('readiness_policy') or {}
    if policy.get('name_heuristics_allowed') is not False or policy.get('absence_of_f6_is_common_stock_evidence') is not False or policy.get('classification_performed') is not False: raise ReadinessError('Readiness policy is unsafe')
    authority=value.get('authority') or {}
    if authority.get('asset_classification_source_readiness') is not True: raise ReadinessError('Readiness authority missing')
    forbidden={'asset_classification','screening','deep_evidence_collection','private_repository_access','private_dispatch','provider_credentials','billing_budget_mutation','registry_mutation','production','publication','broker','orders','trading'}
    if any(authority.get(k) is not False for k in forbidden): raise ReadinessError('Readiness contract grants forbidden authority')
    if value.get('authorized_actions')!=['asset_classification_source_readiness_probe']: raise ReadinessError('Authorized actions differ')
def evaluate(values,http,inventory,contract,generated_at):
    by_id=validate_inventory(inventory); validate_contract(contract)
    present={name:name in values for name in sorted(REQUIRED_VALUES)}
    ready=all(present.values()) and by_id['sec_edgar_f6_subject_filings']['status']=='approved_positive_adr_evidence_pending_collector'
    core={'schema_version':'1.0.0','contract_id':CONTRACT_ID,'generated_at_utc':generated_at,'probe':{'endpoint':ENDPOINT,'authentication_mode':'unauthenticated_free_public','request_count':1,'http_status':http.get('status'),'attempts':http.get('attempts'),'response_bytes':http.get('response_bytes'),'response_sha256':http.get('response_sha256'),'enum_value_count':len(values),'required_values_present':present,'enum_values_sha256':digest(canon(values))},'source_states':{k:v['status'] for k,v in sorted(by_id.items())},'ready_for_future_classifier':ready,'classification_performed':False,'limitations':['Readiness does not classify any instrument.','OpenFIGI metadata requires exact reviewed mapping lineage.','SEC F-6 or F-6EF is positive ADR evidence only; absence is not common-stock evidence.','Nasdaq security-name heuristics remain prohibited.'],'authority':{'asset_classification':False,'screening':False,'deep_evidence_collection':False,'private_access':False,'private_dispatch':False,'registry_mutation':False,'publication':False,'trading':False}}
    return {**core,'readiness_core_sha256':digest(canon(core))}
def write_outputs(root,value):
    root.mkdir(parents=True,exist_ok=True)
    if any(root.iterdir()): raise ReadinessError('Readiness output root must be empty')
    (root/'readiness.json').write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    p=value['probe']['required_values_present']
    lines=['# PPI asset-classification source readiness','',f"- Future classifier readiness: {'ready' if value['ready_for_future_classifier'] else 'held'}",f"- OpenFIGI `Common Stock` enum present: {'yes' if p['Common Stock'] else 'no'}",f"- OpenFIGI `Depositary Receipt` enum present: {'yes' if p['Depositary Receipt'] else 'no'}",'- SEC F-6/F-6EF policy: positive ADR evidence only','- Name-based classification: prohibited','- Instruments classified: 0','- Screening performed: no','- Private repository accessed: no']
    (root/'readiness.md').write_text('\n'.join(lines)+'\n')
    if {p.name for p in root.iterdir() if p.is_file()}!=OUTPUT_PATHS: raise ReadinessError('Readiness output paths are not exact')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--inventory',type=Path,default=Path('config/ppi_asset_classification_source_inventory.json')); ap.add_argument('--contract',type=Path,default=Path('contracts/PPI-ASSET-CLASSIFICATION-SOURCE-READINESS-001-R1.json')); ap.add_argument('--output-root',type=Path,required=True); ap.add_argument('--fixture-values',type=Path); args=ap.parse_args()
    inventory=read_object(args.inventory); contract=read_object(args.contract)
    if args.fixture_values:
        fixture=read_object(args.fixture_values); values=fixture.get('values')
        if not isinstance(values,list): raise ReadinessError('Fixture must contain values')
        values=sorted(values); raw=canon(fixture); http={'status':200,'attempts':0,'response_bytes':len(raw),'response_sha256':digest(raw)}
    else: values,http=fetch_values()
    write_outputs(args.output_root,evaluate(values,http,inventory,contract,now())); return 0
if __name__=='__main__': raise SystemExit(main())
