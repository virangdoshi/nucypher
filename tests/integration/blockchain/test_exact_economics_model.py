"""
This file is part of nucypher.

nucypher is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nucypher is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nucypher.  If not, see <https://www.gnu.org/licenses/>.
"""


from decimal import Decimal, localcontext
from math import log

import pytest

from nucypher.blockchain.economics import Economics


@pytest.mark.skip("remove me")
def test_exact_economics():
    """
    Formula for staking in one period:
    (totalSupply - currentSupply) * (lockedValue / totalLockedValue) * (k1 + allLockedPeriods) / d / k2

    d - Coefficient which modifies the rate at which the maximum issuance decays
    k1 - Numerator of the locking duration coefficient
    k2 - Denominator of the locking duration coefficient

    if allLockedPeriods > awarded_periods then allLockedPeriods = awarded_periods
    kappa * log(2) / halving_delay === (k1 + allLockedPeriods) / d / k2

    kappa = small_stake_multiplier + (1 - small_stake_multiplier) * min(T, T1) / T1
    where allLockedPeriods == min(T, T1)
    """

    #
    # Expected Output
    #
    one_year_in_periods = 365 / 7

    # Supply
    expected_total_supply = 3885390081748248632541961138
    expected_supply_ratio = Decimal('3.885390081748248632541961138')
    expected_initial_supply = 1000000000000000000000000000
    expected_phase1_supply = 1829579800000000000000000000

    # Reward
    expected_reward_supply = 2885390081748248632541961138
    reward_saturation = 1

    # Staking 2 phase
    decay_half_life = 2
    multiplier = 0.5
    expected_lock_duration_coefficient_1 = one_year_in_periods
    expected_lock_duration_coefficient_2 = 2 * expected_lock_duration_coefficient_1
    expected_phase2_coefficient = 150
    expected_minting_coefficient = expected_phase2_coefficient * expected_lock_duration_coefficient_2

    assert int(expected_lock_duration_coefficient_1 * decay_half_life) == \
           round(expected_minting_coefficient * log(2) * multiplier / one_year_in_periods)

    #
    # Sanity
    #

    # Sanity check ratio accuracy
    expected_scaled_ratio = str(expected_supply_ratio).replace('.', '')
    assert str(expected_total_supply) == expected_scaled_ratio

    # Sanity check denomination size
    expected_scale = 28
    assert len(str(expected_total_supply)) == expected_scale
    assert len(str(expected_initial_supply)) == expected_scale
    assert len(str(expected_reward_supply)) == expected_scale

    # Use same precision as economics class
    with localcontext() as ctx:
        ctx.prec = Economics._precision

        # Sanity check expected testing outputs
        assert Decimal(expected_total_supply) / expected_initial_supply == expected_supply_ratio
        assert expected_reward_supply == expected_total_supply - expected_initial_supply
        assert reward_saturation * one_year_in_periods * multiplier == expected_lock_duration_coefficient_1 * (1 - multiplier)
        assert int(one_year_in_periods ** 2 * reward_saturation * decay_half_life / log(2) / (1-multiplier) / expected_lock_duration_coefficient_2) == \
            expected_phase2_coefficient



    # After sanity checking, assemble expected test deployment parameters
    expected_deployment_parameters = (24,       # Hours in single period at genesis
                                      24 * 7,   # Hours in single period
                                      150,     # Coefficient which modifies the rate at which the maximum issuance decays (d)
                                      52,      # Numerator of the locking duration coefficient (k1)
                                      52 * 2,  # Denominator of the locking duration coefficient (k2)
                                      52,      # Max periods that will be additionally rewarded (awarded_periods)
                                      2829579800000000000000000000,   # Total supply for the first phase
                                      7017566356164383151812537,      # Max possible reward for one period for all stakers in the first phase
                                      4,       # Min amount of periods during which tokens can be locked
                                      15000000000000000000000,        # min locked NuNits
                                      30000000000000000000000000,     # max locked NuNits
                                      2)        # Min worker periods
    #
    # Token Economics
    #

    # Check creation
    e = Economics()

    with localcontext() as ctx:
        ctx.prec = Economics._precision
        one_year_in_periods = Decimal(one_year_in_periods)

        # Check that total_supply calculated correctly
        assert Decimal(e.erc20_total_supply) / e.initial_supply == expected_supply_ratio
        assert e.erc20_total_supply == expected_total_supply

        # Check reward rates for the second phase
        initial_rate = (e.erc20_total_supply - int(e.first_phase_total_supply)) * (e.lock_duration_coefficient_1 + one_year_in_periods) / \
                       (e.issuance_decay_coefficient * e.lock_duration_coefficient_2)
        assert int(initial_rate) == int(e.first_phase_max_issuance)
        assert int(LOG2 / (e.token_halving * one_year_in_periods) * (e.erc20_total_supply - int(e.first_phase_total_supply))) == \
               int(initial_rate)

        initial_rate_small = (e.erc20_total_supply - int(e.first_phase_total_supply)) * e.lock_duration_coefficient_1 / \
                             (e.issuance_decay_coefficient * e.lock_duration_coefficient_2)
        assert int(initial_rate_small) == int(initial_rate / 2)

        # Check reward supply
        assert e.reward_supply == expected_total_supply - expected_initial_supply

        # Check deployment parameters
        assert e.pre_application_deployment_parameters == expected_deployment_parameters
        assert e.erc20_initial_supply == expected_initial_supply
        assert e.erc20_reward_supply == expected_reward_supply

        # Additional checks on supply
        assert e.token_supply_at_period(period=0) == expected_initial_supply
        assert e.cumulative_rewards_at_period(0) == 0

        # Check phase 1 doesn't overshoot
        switch_period = 5 * 52
        assert e.first_phase_final_period() == switch_period
        assert e.token_supply_at_period(period=switch_period) <= expected_phase1_supply + expected_initial_supply
        assert e.token_supply_at_period(period=switch_period + 1) > expected_phase1_supply + expected_initial_supply
        assert e.token_supply_at_period(period=switch_period) < e.token_supply_at_period(period=switch_period + 1)

        assert e.rewards_during_period(period=1) == round(e.first_phase_max_issuance)
        assert e.rewards_during_period(period=switch_period) == round(e.first_phase_max_issuance)
        assert e.rewards_during_period(period=switch_period + 1) < int(e.first_phase_max_issuance)

        # Last NuNit is minted after 188 years (or 9800 periods).
        # That's the year 2208, if token is launched in 2020.
        # 23rd century schizoid man!
        assert abs(expected_total_supply - e.token_supply_at_period(period=9800)) < e.first_phase_max_issuance
        assert e.erc20_total_supply == expected_total_supply

        # After 1 year:
        expected_reward_one_year = 52 * 7017566356164383151812537
        assert abs((expected_initial_supply + expected_reward_one_year) - e.token_supply_at_period(period=52)) <= 100
        assert abs(expected_reward_one_year - e.cumulative_rewards_at_period(period=52)) <= 100
        assert e.erc20_initial_supply + e.cumulative_rewards_at_period(52) == e.token_supply_at_period(period=52)

        # Checking that the supply function is monotonic in phase 1
        todays_supply = e.token_supply_at_period(period=0)
        for t in range(9800):
            tomorrows_supply = e.token_supply_at_period(period=t + 1)
            assert tomorrows_supply >= todays_supply
            todays_supply = tomorrows_supply
