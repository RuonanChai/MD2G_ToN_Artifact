#!/usr/bin/env python3
import json, hashlib
from pathlib import Path
TON = Path(__file__).resolve().parents[1]
STATE = TON/'state'

def test_audit_exists_and_resolves_AF():
    a = json.loads((STATE/'TON_MEDIA_SEMANTICS_AUDIT.json').read_text())
    v = a['verdicts']
    assert v['A_rep1_to_rep9']['verdict'] == 'FULL_INDEPENDENT_REPS_SAME_CONTENT'
    assert 'NOT_RESIDUAL' in v['B_additive_bitstream']['verdict']
    assert 'HEADROOM' in v['C_completion']['verdict']
    assert 'PACKAGING' in v['D_cmaf']['verdict']
    assert v['E_enhanced_delivery']['verdict'] == 'SHARED_MOQ_FANOUT'
    assert 'object' in v['F_granularity']

def test_contract_canonical_plane_and_hash():
    c = json.loads((STATE/'TON_MEDIA_CONTRACT_V1.json').read_text())
    assert c['canonical_plane_for_C28_C29_lineage'] == 'MM26_TWO_TRACK_BASE_ENHANCED'
    assert c['sigcomm_nine_rep_plane']['allowed_as_nine_videos'] is False
    assert c['codec']['not'] == 'residual_SVC_bitstream'
    h = hashlib.sha256((STATE/'TON_MEDIA_CONTRACT_V1.json').read_bytes()).hexdigest()
    assert (STATE/'TON_MEDIA_CONTRACT_V1.sha256').read_text().strip() == h

def test_inventory_does_not_claim_nine_yet():
    a = json.loads((STATE/'TON_MEDIA_SEMANTICS_AUDIT.json').read_text())
    inv = a['independent_content_inventory']
    assert inv['verified_count'] == 1
    assert inv['missing_count'] == 8
    assert inv['do_not_invent'] is True

if __name__ == '__main__':
    test_audit_exists_and_resolves_AF()
    test_contract_canonical_plane_and_hash()
    test_inventory_does_not_claim_nine_yet()
    print('TON_MEDIA_CONTRACT_PASS')
