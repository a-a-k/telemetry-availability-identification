from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import numpy as np

from telemetry_availability.isolated_stochastic_fit import load_analysis
from telemetry_availability.live_validation_analysis import (QualifiedCell,RequestRecord,HealthTick,
    prepare_mode,_likelihood_data,_negative_log_likelihood,route_probability)
from telemetry_availability.live_validation_config import LiveObservationMode,LiveOperationSpec


class TraceOnlyDependencyTests(unittest.TestCase):
    def test_masked_health_change_leaves_actual_likelihood_inputs_equal(self):
        root=Path(__file__).resolve().parents[1]
        analysis=load_analysis(root/'configs/isolated_stochastic_analysis.json')
        profile='opentelemetry_demo'
        analysis=replace(analysis,operations={profile:(LiveOperationSpec('checkout',True,'artificial control'),)})
        mode=LiveObservationMode('trace_only','none',0.0,1.0)
        origin=datetime(2026,9,8,tzinfo=timezone.utc)
        requests=tuple(RequestRecord('baseline' if i<20 else 'calibration',str(i),'checkout',(origin+timedelta(seconds=i)).timestamp(),
             int(i%10!=9),True,2,frozenset({'entry','target'}),frozenset({'a' if i%2 else 'b'})) for i in range(60))
        old=tuple(HealthTick((origin+timedelta(seconds=i)).timestamp(),float(i),(1,1,0 if i%3==0 else 1,1)) for i in range(61))
        new=tuple(replace(t,signals=(1,1,1,1)) for t in old)
        cell=QualifiedCell(profile,'colocated','ND',0,'target',requests,old,(),(),{},Path('artificial'))
        a=prepare_mode(cell,mode,analysis);b=prepare_mode(replace(cell,health=new),mode,analysis)
        self.assertEqual(a.topology['checkout'].status,'confirmed')
        self.assertEqual(a.ticks,b.ticks)
        self.assertEqual(a.topology,b.topology)
        self.assertEqual(a.q_by_operation,b.q_by_operation)
        self.assertEqual(a.calibration_by_operation,b.calibration_by_operation)
        x=_likelihood_data(a,'colocated',analysis);y=_likelihood_data(b,'colocated',analysis)
        for name in ('consistency','log_outcome_route_down','log_outcome_route_up','multiplicities'):
            self.assertTrue(np.array_equal(getattr(x,name),getattr(y,name)))
        # Same current observable law; different unobserved-placement target.
        theta1=dict(g=.9,ea=.8,eb=4/9,ca=1.,cb=1.)
        theta2=dict(g=.95,ea=.8,eb=4/19,ca=1.,cb=1.)
        for theta in (theta1,theta2):self.assertAlmostEqual(route_probability(theta,'colocated'),.8,places=12)
        self.assertAlmostEqual(route_probability(theta1,'split'),.832,places=12)
        self.assertAlmostEqual(route_probability(theta2,'split'),.808,places=12)
        values=[_negative_log_likelihood(np.array([t[k] for k in ('g','ea','eb')]),('g','ea','eb'),x,
                analysis.numerical_probability_floor) for t in (theta1,theta2)]
        self.assertLessEqual(abs(values[0]-values[1]),1e-12)


if __name__=='__main__':unittest.main()
