#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

# -*- coding: utf-8 -*-
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))

from ton_cell_scoped_net import (
    MD2G_BRIDGES, MD2G_CORE_IFACES, assert_clear, md2g_host_ifaces, topology_key,
)


def test_topology_key_and_iface_list_are_cell_scoped():
    names = md2g_host_ifaces(20)
    assert "r1-eth1" in names
    assert "s1-eth0" in names
    assert "h20-eth0" in names
    assert topology_key(20, "sigcell_x_") == "md2g_tree_u20:sigcell_x_"
    assert "s1" in MD2G_BRIDGES
    assert "n0-eth0" in MD2G_CORE_IFACES


def test_assert_clear_schema(monkeypatch):
    inv = {
        "topology_key": "md2g_tree_u4:test_",
        "ifaces_declared": ["r1-eth1", "s1-eth0"],
        "bridges_declared": ["s1", "s2"],
        "num_subscribers": 4,
    }
    monkeypatch.setattr("ton_cell_scoped_net.current_link_names", lambda: set())
    monkeypatch.setattr("ton_cell_scoped_net.current_ovs_bridges", lambda: set())
    chk = assert_clear(inv)
    assert chk["clear"] is True
    monkeypatch.setattr("ton_cell_scoped_net.current_link_names", lambda: {"r1-eth1"})
    chk = assert_clear(inv)
    assert chk["clear"] is False
    assert "r1-eth1" in chk["stale_ifaces"]
