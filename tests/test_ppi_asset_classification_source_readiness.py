from __future__ import annotations
import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/validate_ppi_asset_classification_source_readiness.py'; INVENTORY=ROOT/'config/ppi_asset_classification_source_inventory.json'; CONTRACT=ROOT/'contracts/PPI-ASSET-CLASSIFICATION-SOURCE-READINESS-001-R1.json'; WORKFLOW=ROOT/'.github/workflows/ppi-asset-classification-source-readiness.yml'
spec=importlib.util.spec_from_file_location('readiness',SCRIPT); assert spec and spec.loader
readiness=importlib.util.module_from_spec(spec); spec.loader.exec_module(readiness)
class Tests(unittest.TestCase):
    def values(self): return ['Common Stock','Depositary Receipt','Preferred Stock','Warrant']
    def test_contract_grants_only_readiness_authority(self):
        value=json.loads(CONTRACT.read_text())
        self.assertTrue(value['authority']['asset_classification_source_readiness'])
        for key,state in value['authority'].items():
            if key!='asset_classification_source_readiness': self.assertFalse(state,key)
        self.assertEqual(value['authorized_actions'],['asset_classification_source_readiness_probe'])
    def test_inventory_preserves_objective_boundaries(self):
        value=json.loads(INVENTORY.read_text()); sources=readiness.validate_inventory(value)
        self.assertEqual(sources['openfigi_v3_instrument_metadata']['positive_evidence']['adr']['security_type2'],'Depositary Receipt')
        self.assertFalse(sources['sec_company_tickers_exchange']['classification_authority'])
        self.assertEqual(sources['nasdaq_symbol_directory']['status'],'pending_terms_and_semantics_review')
        self.assertIn('absence_of_f6_as_common_stock_proof',value['prohibited_methods'])
    def test_exact_enum_values_make_future_classifier_ready(self):
        result=readiness.evaluate(self.values(),{'status':200,'attempts':1,'response_bytes':100,'response_sha256':'a'*64},json.loads(INVENTORY.read_text()),json.loads(CONTRACT.read_text()),'2026-07-29T00:00:00Z')
        self.assertTrue(result['ready_for_future_classifier']); self.assertFalse(result['classification_performed']); self.assertEqual(len(result['readiness_core_sha256']),64)
    def test_missing_depositary_receipt_holds_readiness(self):
        result=readiness.evaluate(['Common Stock'],{'status':200,'attempts':1,'response_bytes':20,'response_sha256':'b'*64},json.loads(INVENTORY.read_text()),json.loads(CONTRACT.read_text()),'2026-07-29T00:00:00Z')
        self.assertFalse(result['ready_for_future_classifier']); self.assertFalse(result['probe']['required_values_present']['Depositary Receipt'])
    def test_endpoint_allowlist_is_exact(self):
        readiness.validate_endpoint()
        for bad in ('http://api.openfigi.com/v3/mapping/values/securityType2','https://api.openfigi.com/v3/mapping','https://example.com/v3/mapping/values/securityType2','https://api.openfigi.com/v3/mapping/values/securityType2?x=1'):
            with self.subTest(bad=bad), self.assertRaises(readiness.ReadinessError): readiness.validate_endpoint(bad)
    def test_outputs_are_exact_and_safe(self):
        result=readiness.evaluate(self.values(),{'status':200,'attempts':1,'response_bytes':100,'response_sha256':'c'*64},json.loads(INVENTORY.read_text()),json.loads(CONTRACT.read_text()),'2026-07-29T00:00:00Z')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); readiness.write_outputs(root,result)
            self.assertEqual({p.name for p in root.iterdir()},{'readiness.json','readiness.md'})
            receipt=json.loads((root/'readiness.json').read_text()); self.assertFalse(receipt['authority']['private_access']); self.assertFalse(receipt['authority']['asset_classification'])
    def test_workflow_is_secret_free(self):
        text=WORKFLOW.read_text(); self.assertIn("cron: '11 7 * * 1'",text); self.assertIn('permissions:\n  contents: read',text); self.assertIn('persist-credentials: false',text)
        self.assertIn('actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',text); self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',text)
        for forbidden in ('secrets.','contents: write','issues: write','pull-requests: write','musksuman3/ai-signal-engine','PPI_SEC_CONTACT_EMAIL'):
            self.assertNotIn(forbidden,text)
if __name__=='__main__': unittest.main()
