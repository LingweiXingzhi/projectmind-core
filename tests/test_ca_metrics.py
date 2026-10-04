import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('ca_metrics', Path(__file__).resolve().parents[1]/'experiments/ca_experiment/compute_metrics.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)

class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.gt = [{'qid': f'q{i:02}'} for i in range(1,21)]
        self.judgments = [{'run': r,'condition': c,'qid':q['qid'],'verdict':'CORRECT','normalized_answer':'same','used_stale_source':False,'unsupported_assumption':False,'reason':'Independent evidence agrees'} for r,c in metrics.RUNS.items() for q in self.gt]
    def test_complete_pair_denominator(self):
        self.assertEqual(metrics.aggregate(self.gt,self.judgments)['per_condition']['raw']['pairs'],60)
    def test_different_wrong_facts_disagree(self):
        for j in self.judgments:
            if j['qid']=='q01' and j['condition']=='raw':
                j.update(verdict='WRONG',normalized_answer=j['run'])
        self.assertEqual(metrics.aggregate(self.gt,self.judgments)['per_condition']['raw']['disagreeing_pairs'],3)
    def test_same_fact_different_verdict_does_not_disagree(self):
        self.judgments[0]['verdict']='PARTIAL'
        self.assertEqual(metrics.aggregate(self.gt,self.judgments)['per_condition']['raw']['factual_disagreement_rate'],0)
    def test_missing_judgment_rejected(self):
        with self.assertRaises(ValueError): metrics.aggregate(self.gt,self.judgments[:-1])
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError): metrics.aggregate(self.gt,self.judgments+[copy.deepcopy(self.judgments[0])])
    def test_wrong_condition_rejected(self):
        self.judgments[0]['condition']='ca'
        with self.assertRaises(ValueError): metrics.aggregate(self.gt,self.judgments)
    def test_self_score_without_normalization_rejected(self):
        del self.judgments[0]['normalized_answer']
        with self.assertRaises(ValueError): metrics.aggregate(self.gt,self.judgments)
    def test_conflict_detection_not_invented(self):
        self.assertIsNone(metrics.aggregate(self.gt,self.judgments)['conflict_detection_rate'])
    def test_reason_missing_rejected(self):
        del self.judgments[0]['reason']
        with self.assertRaises(ValueError): metrics.aggregate(self.gt,self.judgments)
