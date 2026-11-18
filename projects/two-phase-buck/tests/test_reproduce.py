import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('buck_reproduce', PROJECT/'scripts/reproduce.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublishedMeasurements(unittest.TestCase):
    def test_full_counts_and_counterexample_retained(self):
        data = module.load('r8_measurements.json')
        module.verify_measurements(data, 47, 24)
        unload = module.event(data, 'v3_pdn_hard_p0', 'load_down')
        self.assertGreater(unload['overshoot_from_target_v_variant'], unload['overshoot_from_target_v_baseline'])
        self.assertIsNone(data['physical_overall_efficiency'])

    def test_pair_arithmetic_mutation_rejected(self):
        data = copy.deepcopy(module.load('r9_measurements.json'))
        data['pairs'][0]['events'][0]['raw_recovery_s_delta_variant_minus_baseline'] += 1e-6
        with self.assertRaisesRegex(ValueError, 'arithmetic'):
            module.verify_measurements(data, 8, 4)

    def test_completion_cannot_become_performance_pass(self):
        data = module.load('r8_measurements.json')
        data['performance_pass'] = True
        with self.assertRaisesRegex(ValueError, 'unassigned'):
            module.verify_measurements(data, 47, 24)

    def test_manifest_rejects_parent_path(self):
        project = MagicMock()
        project.__truediv__.return_value.read_text.return_value = json.dumps({'files':[
            {'path':'../other.json','bytes':0,'sha256':'0'*64}]})
        with patch.object(module, 'PROJECT', project):
            with self.assertRaisesRegex(ValueError, 'path'):
                module.verify_manifest()

    def test_all_59_devices_are_enumerated(self):
        result=module.verify_dimensions()
        self.assertEqual(result['complete_MOS_rows'],59)
        self.assertEqual(result['block_counts'],{'Gate drivers':24,'Power bridges':12,
                         'Source/sink assist':3,'Window comparators':20})

    def test_comparison_diagnostics_keep_negative_tradeoff(self):
        datasets={r:module.load(r+'_measurements.json') for r in ('r8','r9')}
        metrics=module.comparison_metrics(datasets,module.load('assist_port_work.json'))
        record=next(r for r in metrics if r['pair']=='v3_pdn_hard_p0' and r['event']=='load_down')
        self.assertLess(record['relative_peak_reduction_pct'],0)
        self.assertAlmostEqual(record['net_assist_VLOAD_work_nj_variant'],
            record['source_VLOAD_port_work_nj_variant']-record['sink_VLOAD_port_work_nj_variant'])

    def test_metric_condition_mismatch_rejected(self):
        data=module.load('r8_measurements.json')
        name=data['pairs'][0]['variant']
        next(c for c in data['cases'] if c['name']==name)['config']['parameters']['COUT'] *= 2
        with self.assertRaisesRegex(ValueError,'conditions differ'):
            module.comparison_metrics({'r8':data},module.load('assist_port_work.json'))


if __name__ == '__main__':
    unittest.main()
