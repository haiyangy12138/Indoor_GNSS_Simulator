"""Regression tests for externally visible configuration and data provenance semantics."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from indoor_gnss.config import load,DEFAULT,validate
from indoor_gnss.engine import Model
from indoor_gnss.iq import render_iq


class IntegrationTests(unittest.TestCase):
    def test_invalid_prn_keys_are_rejected_instead_of_ignored(self):
        for key in ['01','G01','99']:
            cfg=deepcopy(DEFAULT)
            cfg['relay']['mapping']={key:'V1'}
            with self.assertRaisesRegex(ValueError,'Mapping keys'): validate(cfg)
            cfg=deepcopy(DEFAULT)
            cfg['compensation']['per_prn']={key:deepcopy(DEFAULT['compensation']['default'])}
            with self.assertRaisesRegex(ValueError,'per_prn keys'): validate(cfg)
        cfg=deepcopy(DEFAULT)
        cfg['satellites']['prns']=[1.5]
        with self.assertRaisesRegex(ValueError,'integers'): validate(cfg)
    def test_resource_and_reserved_name_validation(self):
        cfg=deepcopy(DEFAULT)
        cfg['iq']['output_name']='run_summary.json'
        with self.assertRaisesRegex(ValueError,'reserved'): validate(cfg)
        cfg=deepcopy(DEFAULT)
        cfg['time']['trajectory_distance_step_m']=1e-8
        with self.assertRaisesRegex(ValueError,'epoch count'): validate(cfg)
    def test_per_prn_inherits_default(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'config.json'
            p.write_text(json.dumps({'compensation':{'default':{'range_offset_m':2.},'per_prn':{'3':{'range_rate_mps':.1}}}}),encoding='utf-8')
            c=load(p)
            self.assertEqual(c['compensation']['per_prn']['3']['range_offset_m'],2.)
            self.assertEqual(c['compensation']['per_prn']['3']['range_rate_mps'],.1)

    def test_iq_add_noise_configuration_is_honored(self):
        c=deepcopy(DEFAULT)
        c['iq'].update(duration_s=.001,sample_rate_hz=2046000.,format='cf32_le',start_s=0.,add_noise=False)
        series={'t_s':np.array([0.,.01]),'prn':np.array([1]),'cn0_dbhz':np.array([40.]),
            'code_path_m':np.zeros((2,1)),'carrier_path_m':np.zeros((2,1)),
            'phase_offset_rad':np.zeros((2,1)),'gain_linear':np.ones((2,1))}
        with tempfile.TemporaryDirectory() as folder:
            meta=render_iq(c,series,folder)
            self.assertFalse(meta['noise_enabled'])
            a=np.fromfile(Path(folder)/'signal.iq',dtype='<c8')
            np.testing.assert_allclose(np.abs(a),100.,atol=1e-5)

    def test_unhealthy_satellite_rejection_does_not_abort_selection(self):
        # Real downloaded input is an optional smoke regression, not an independent orbit reference.
        nav=Path(__file__).resolve().parents[1]/'data/raw/brdc0010.22n'
        if not nav.exists(): self.skipTest('Optional public NAV sample has not been downloaded')
        cfg=load(Path(__file__).resolve().parents[1]/'configs/rinex_template.json')
        model=Model(cfg)
        self.assertGreaterEqual(len(model.prns),6)
        self.assertNotIn(11,model.prns)
        self.assertIn(11,model.rejected_satellites)


if __name__=='__main__': unittest.main()
