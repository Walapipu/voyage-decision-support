"""Readable cargo rankings and explicit voyage selection."""
import json
from collections import Counter
from html import escape
import pandas as pd
import streamlit as st
from voyage.ranking import rank_cargo


@st.cache_data(show_spinner=False)
def cached_ranking(cargo_id, period, **kwargs):
    return rank_cargo(cargo_id, period, **kwargs)


def apply_option(vessel_id, tonnes):
    st.session_state.selected_vessel = vessel_id
    st.session_state.selected_lift = int(tonnes)


def use_selected_quantity():
    st.session_state.ranking_quantity_mode = 'selected'


def ranking_note(*paragraphs):
    """Use naturally sized paragraphs for explanatory text, including wrapped lines."""
    st.html('<div class="ranking-note">' + ''.join(
        f'<p>{escape(text)}</p>' for text in paragraphs) + '</div>')


def sync_recommendation(force=False):
    """Reset on cargo/month/grid changes; preserve deliberate manual edits."""
    cargo = st.session_state.selected_cargo
    if cargo is None:
        return
    period = st.session_state.price_period
    step = st.session_state.get('ranking_step', 1000)
    signature = (cargo, period, step)
    previous = st.session_state.get('ranking_selection_context')
    selected_mode = st.session_state.get('ranking_quantity_mode') == 'selected'
    context_changed = previous is None or previous[:2] != signature[:2]
    if force or context_changed or (not selected_mode and previous != signature):
        pick = cached_ranking(cargo, period, quantity_step=step)['recommendation']
        if pick:
            apply_option(pick['recommended_vessel'], pick['recommended_tonnes'])
        else:
            from voyage.data import load_tables
            row = next(c for c in load_tables()['committed_cargoes'] if c['cargo_id'] == cargo)
            st.session_state.selected_lift = int(row['nominal_quantity_tonnes'])
        st.session_state.ranking_selection_context = signature
        st.session_state.ranking_quantity_mode = 'optimal'


def option_card(row, selected_mode=False):
    recommended = row['vessel_rank'] == 1
    title = 'Recommended voyage' if recommended else f"Rank {row['vessel_rank']}"
    if recommended and selected_mode:
        title = 'Highest contribution at your selected quantity'
    metrics = [('Cargo quantity', f"{row['recommended_tonnes']:,.0f} t"),
               ('Baseline contribution', f"${row['profit_usd']:,.0f}"),
               ('Stress contribution', f"${row['stress_profit_usd']:,.0f}"),
               ('Voyage duration', f"{row['voyage_days']:.1f} days")]
    tiles = ''.join(f'<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>' for label, value in metrics)
    st.html(f'<article class="voyage-option {"recommended" if recommended else ""}">'
            f'<header><div><small>{escape(title)}</small><h3>{escape(row["vessel_id"])}</h3></div>'
            '<span class="tag good">Feasible · economical speed</span></header>'
            f'<dl class="voyage-option-metrics">{tiles}</dl><p>{escape(row["considerations"])}</p>'
            f'<footer>TCE before hire: ${row["tce_usd_per_day"]:,.0f}/day · '
            f'Draft headroom: {row["draft_margin_m"]:.2f} m · '
            f'Blended base/stress score: ${row["risk_adjusted_score"]:,.0f}</footer></article>')
    selected = (st.session_state.selected_vessel == row['vessel_id'] and
                st.session_state.selected_lift == row['recommended_tonnes'])
    st.button('Selected voyage' if selected else f"Use {row['vessel_id']} at {row['recommended_tonnes']:,.0f} t",
              key='use_ranked_' + row['vessel_id'], disabled=selected,
              on_click=apply_option, args=(row['vessel_id'], row['recommended_tonnes']))


def render_ranking(cargo_id, period):
    selected_mode = st.session_state.get('ranking_quantity_mode') == 'selected'
    st.subheader(f'Best voyages for {cargo_id}')
    if selected_mode:
        ranking_note(f"Comparing vessels at your selected quantity: {st.session_state.selected_lift:,.0f} tonnes.",
                     'Ranked by contribution after hire, using economical speed.')
        st.button('Find optimal quantity', key='restore_optimal_quantity',
                  on_click=sync_recommendation, kwargs={'force': True})
    else:
        ranking_note('Each vessel is shown at its best feasible quantity.',
                     'Edit the tonnes field above to compare all vessels at that exact quantity.')
    with st.expander('Adjust search and stress assumptions'):
        left, right = st.columns(2)
        with left:
            step = st.number_input('Quantity search step (tonnes)', min_value=100, value=1000, step=100, key='ranking_step', disabled=selected_mode)
            bunker = st.number_input('Bunker price increase (%)', min_value=0., value=20., key='ranking_bunker')
            delay = st.number_input('Additional port delay (days)', min_value=0., value=3., key='ranking_delay')
        with right:
            ports = st.number_input('Port cost increase (%)', min_value=0., value=15., key='ranking_ports')
            ballast = st.number_input('Additional ballast (nm)', min_value=0., value=0., key='ranking_ballast')
            weight = st.slider('Stress weight in blended score', 0., 1., .5, key='ranking_weight')
        ranking_note('Stress is a what-if scenario, not a forecast. The blended score does not change the profit ranking.',
                     'Search includes quantity limits, nominal lift and freight thresholds.')
    result = cached_ranking(cargo_id, period, quantity_step=step, bunker_increase=bunker/100,
                            port_delay_days=delay, port_cost_increase=ports/100,
                            additional_ballast_nm=ballast, risk_weight=weight,
                            lift_tonnes=st.session_state.selected_lift if selected_mode else None)
    if result['best_per_vessel']:
        for row in result['best_per_vessel']:
            with st.container(border=True):
                option_card(row, selected_mode)
    else:
        if selected_mode:
            st.warning('No vessel is feasible at your selected quantity. Review the accepted range and feasibility checks below, or find the optimal quantity.')
        else:
            st.warning('No feasible configuration. The top controls show nominal quantity for inspection only; it is not a recommendation.')
    ranking_note(f"{len(result['all_options'])} feasible configurations · {period} bunker prices.",
                 'Voyage durations differ; this is not a fleet allocation plan.',
                 'You can manually edit the selected lift above.')
    with st.expander('Feasibility checks and excluded options'):
        st.write('Feasible voyages pass cargo quantity, laycan, deadweight and minimum draft clearance checks.')
        reasons = Counter((r['vessel_id'], r['reason']) for r in result['excluded'])
        if not reasons:
            ranking_note('No configurations excluded.')
        for (vessel, reason), count in sorted(reasons.items()):
            st.markdown(f'**{vessel}** · {count} configurations excluded: {reason.replace("_", " ")}')
        ranking_note('Full configuration evidence is included in the JSON download.')
    with st.expander('Download results'):
        st.download_button('Download full analysis (JSON)', json.dumps(result, indent=2),
                           file_name=f'{cargo_id}_{period}_ranking.json', mime='application/json')
        st.download_button('Download vessel summary (CSV)', pd.DataFrame(result['best_per_vessel']).to_csv(index=False),
                           file_name=f'{cargo_id}_{period}_ranking.csv', mime='text/csv')
