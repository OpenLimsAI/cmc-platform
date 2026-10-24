"""Independent validation: old algorithm outputs are not a correctness oracle."""
import numpy as np
import pytest
from statsmodels.stats.weightstats import CompareMeans
from app.services.stats.equivalence import (
    compare_equivalence, decide_equivalence, levene_test, perform_tost, resolve_tost_alpha,
)
from app.services.stats.similarity import evaluate_similarity_pair, tier_similarity_judge


@pytest.mark.parametrize('confidence,alpha,critical', [(.9,.05,1.8595480375228424), (.95,.025,2.306004135204166)])
def test_confidence_hand_calculation(confidence, alpha, critical):
    ref = np.arange(98., 103.)
    result = compare_equivalence(ref, ref+.7, delta=1.5*np.sqrt(2.5),
                                 confidence_level=confidence, variance_method='pooled')
    # Sample variance 2.5 in each group; SE^2=2.5/5+2.5/5=1, df=8.
    assert result['alpha'] == pytest.approx(alpha)
    assert result['confidence_level'] == pytest.approx(confidence)
    assert result['se'] == pytest.approx(1)
    assert result['df'] == 8
    assert result['mean_diff'] == pytest.approx(.7)
    assert (result['ci_low'],result['ci_high']) == pytest.approx((.7-critical,.7+critical))
    assert result['equivalent'] is False


@pytest.mark.parametrize('seed', range(6))
@pytest.mark.parametrize('method,usevar', [('pooled','pooled'),('welch','unequal')])
def test_tost_matches_independent_statsmodels(seed, method, usevar):
    rng = np.random.default_rng(seed)
    ref, comp = rng.normal(10,.3,7), rng.normal(10.4,2.8,19)
    cm = CompareMeans.from_data(comp, ref)
    p = cm.ttost_ind(-2.,2.,usevar=usevar)[0]
    ci = cm.tconfint_diff(alpha=.1,usevar=usevar)
    result = compare_equivalence(ref,comp,delta=2,confidence_level=.9,variance_method=method)
    assert result['status'] == 'ok'
    assert result['p_tost'] == pytest.approx(p,abs=1e-12)
    assert (result['ci_low'],result['ci_high']) == pytest.approx(ci)
    assert result['equivalent'] == (p < .05)
    assert (decide_equivalence(*ci,2.) == '等效') == result['equivalent']


def test_role_swap_reverses_difference_and_ci_not_judgement():
    ref,comp = [3.,1.,2.,5.],[4.,7.,6.,8.,2.]
    kw = dict(delta=6.,confidence_level=.95,variance_method='welch')
    a,b = compare_equivalence(ref,comp,**kw),compare_equivalence(comp,ref,**kw)
    assert a['difference_direction'] == 'comparison_minus_reference'
    assert a['mean_diff'] == pytest.approx(np.mean(comp)-np.mean(ref))
    assert b['mean_diff'] == pytest.approx(-a['mean_diff'])
    assert (b['ci_low'],b['ci_high']) == pytest.approx((-a['ci_high'],-a['ci_low']))
    assert a['p_tost'] == pytest.approx(b['p_tost'])
    assert a['equivalent'] == b['equivalent']
    assert perform_tost(comp,ref,6,return_detail=True)['mean_diff'] == pytest.approx(a['mean_diff'])


def test_bf_threshold_changes_actual_formula():
    ref,comp = [1.,1.1,.9,1.2],[1.05,1.15,1.,1.1]
    kw = dict(delta=.4,confidence_level=.9,variance_method='brown_forsythe')
    a,b = compare_equivalence(ref,comp,bf_threshold=.05,**kw),compare_equivalence(ref,comp,bf_threshold=.3,**kw)
    assert .05 < a['bf_p_value'] < .3
    assert a['variance_method'] == 'pooled' and b['variance_method'] == 'welch'
    assert a['df'] == 6 and b['df'] < 6
    assert a['sd_pooled'] is not None and b['sd_pooled'] is None
    assert b['p_tost'] == pytest.approx(CompareMeans.from_data(comp,ref).ttost_ind(-.4,.4,usevar='unequal')[0])


@pytest.mark.parametrize('confidence,delta', [(.9,2.3717082451262845),(.9,3.),(.95,3.),(.8,2.3717082451262845)])
def test_tier1_and_main_share_parameters_and_result(confidence, delta):
    ref = np.arange(98.,103.)
    kw = dict(delta=delta,confidence_level=confidence,variance_method='welch')
    main = compare_equivalence(ref,ref+.7,**kw)
    tier = evaluate_similarity_pair(ref,ref+.7,tier='Tier1',**kw)
    for key in main:
        assert tier[key] == main[key]
    assert tier['judgement'] == ('Similar' if main['equivalent'] else 'Not Similar')
    assert tier_similarity_judge('X',['X'],100,np.sqrt(2.5),ref,ref+.7,**kw) == tier['judgement']


def test_old_conflict_now_consistent_manual_delta_effective():
    ref = np.arange(98.,103.)
    kw = dict(tier='Tier1',confidence_level=.9,variance_method='pooled')
    a = evaluate_similarity_pair(ref,ref+.7,delta=1.5*np.sqrt(2.5),**kw)
    assert a['equivalent'] is False and a['judgement'] == 'Not Similar'
    assert (a['ci_low'],a['ci_high']) == pytest.approx((-1.1595480375228424,2.5595480375228424))
    b = evaluate_similarity_pair(ref,ref+.7,delta=3.,**kw)
    assert b['equivalent'] is True and b['judgement'] == 'Similar'


def test_tier2_boundaries_and_manual_delta():
    kw = dict(tier='Tier2',confidence_level=.9,variance_method='pooled',prop_thresh=2/3)
    a = evaluate_similarity_pair([9,10,11],[9,11,12],delta=1,**kw)
    assert (a['lower'],a['upper'],a['band_hits']) == (9,11,2)
    assert a['band_ratio'] == 2/3 and a['judgement'] == 'Similar'
    assert evaluate_similarity_pair([9,10,11],[9,11,12],delta=2,**kw)['band_hits'] == 3
    assert tier_similarity_judge('X',[],10,1,[9,10,11],[9,11,12],delta=1,prop_thresh=.9) == 'Not Similar'


@pytest.mark.parametrize('ref,comp,reason', [([],[1,2],'insufficient_samples'),([1],[1,2],'insufficient_samples'),
    ([1,2],[1],'insufficient_samples'),([2,2],[3,3],'zero_standard_error'),
    ([np.nan,np.inf],[1,2],'insufficient_samples')])
def test_unestimable_returns_unknown(ref,comp,reason):
    a = evaluate_similarity_pair(ref,comp,tier='Tier1',delta=1,confidence_level=.9,variance_method='welch')
    assert a['equivalent'] is None and a['judgement'] == 'Unknown'
    assert a['status'] == 'not_evaluable' and a['reason'] == reason
    assert a['p_tost'] is None and a['ci_low'] is None


def test_single_point_does_not_claim_similarity():
    for tier1 in (['X'],[]):
        assert tier_similarity_judge('X',tier1,2,1,[1,2,3],[2]) == 'Unknown'


def test_finite_filter_and_scale_invariance_without_rounding():
    ref,comp = np.array([1.,2.,4.]),np.array([2.,3.,4.,6.])
    a = perform_tost(comp,ref,5,return_detail=True)
    b = perform_tost(comp*1e-8,ref*1e-8,5e-8,return_detail=True)
    assert b['mean_diff'] != 0
    assert b['mean_diff'] == pytest.approx(a['mean_diff']*1e-8,abs=1e-20)
    assert b['p_tost'] == pytest.approx(a['p_tost'])
    assert b['ci_low'] == pytest.approx(a['ci_low']*1e-8,abs=1e-20)
    c = perform_tost([*comp,np.nan,np.inf],[*ref,-np.inf],5,return_detail=True)
    assert c['excluded_n1'] == 2 and c['excluded_n2'] == 1
    assert c['p_tost'] == pytest.approx(a['p_tost'])


@pytest.mark.parametrize('kw', [dict(confidence_level=1),dict(confidence_level=0),dict(confidence_level=np.nan),
    dict(alpha=.5),dict(alpha=0),dict(alpha=-.1),dict(alpha=.05,confidence_level=.9)])
def test_bad_or_ambiguous_confidence(kw):
    with pytest.raises(ValueError):
        resolve_tost_alpha(**kw)


@pytest.mark.parametrize('delta', [0,-1,np.nan,np.inf])
def test_bad_delta(delta):
    with pytest.raises(ValueError):
        perform_tost([1,2],[2,3],delta)


def test_bad_method_dimensions_threshold():
    with pytest.raises(ValueError):
        perform_tost([1,2],[2,3],1,variance_method='TOST2')
    with pytest.raises(ValueError):
        perform_tost([[1,2]],[2,3],1)
    with pytest.raises(ValueError):
        levene_test([1,2],[2,3],bf_threshold=0)
    with pytest.raises(ValueError):
        evaluate_similarity_pair([1,2],[2,3],tier='Tier2',delta=1,confidence_level=.9,variance_method='pooled')


def test_ci_judgement_strict_and_invalid_bounds():
    assert decide_equivalence(-1,1,1) == '不等效'
    assert decide_equivalence(-.9,.9,1) == '等效'
    assert decide_equivalence(1,-1,2) == '不确定'
    assert decide_equivalence(-np.inf,1,2) == '不确定'
    assert decide_equivalence(0,0,0) == '不确定(未设Δ)'
