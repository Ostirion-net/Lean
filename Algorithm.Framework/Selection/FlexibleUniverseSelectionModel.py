#
# Original File:
# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect
# Corporation.
#
# Changes:
# The universe selection model is extended to take parameters as
# optional arguments.
# Ostirion.net Copyright 2021
# Hector Barrio - hbarrio@ostirion.net.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from QuantConnect.Data.UniverseSelection import *
from Selection.FundamentalUniverseSelectionModel import FundamentalUniverseSelectionModel
from itertools import groupby
from math import ceil
from clr import AddReference
import numpy as np
from typing import List, Set, Tuple, Dict
AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm.Framework")


class FlexibleUniverseSelectionModel(FundamentalUniverseSelectionModel):

    '''
    Class representing a parametrically selected securities universe.

    Attributes:
        n_coarse (int): Number of securities in the coarse selection.
        n_fine (int): Number of securities in fine selection.
        age (int): Minimum time since IPO.
        recent (int): Maximum time from IPO.
        vol_lim (float): Minimum daily volume of each security.
        min_price (float): Minimum price of each security.
        max_price (float): Maximum price of each security.
        period (str): "Month" or "Day". Recalculate the universe every period.
        m_cap_lim (float): Minimum market cap of security to be considered.
        markets (list[str]): Markets in which the security trades.
        c_id (str): Code of the country of origin of securities.
        from_top (bool): Take the top (True) or bottom (False) volume securities.
        restrict_country (bool): Restrict the country of origin and market for securities.
        verbose (bool): False for silent, True for announcing size and components.
    '''

    def __init__(self: None,
                 n_coarse: int=1000,
                 n_fine: int=500,
                 age: int=1250,
                 recent: int=-1,
                 vol_lim: int=0,
                 min_price: int=0,
                 max_price: float=np.Inf,
                 period: str='Month',
                 m_cap_lim: float=5e8,
                 markets: List[str]=["NYS", "NAS"],
                 c_id: str='USA',
                 from_top: bool=True,
                 restrict_country: bool=True,
                 verbose: bool=False,
                 filterFineData: bool=True,
                 universeSettings: UniverseSettings=None,
                 securityInitializer: SecurityInitializer=None) -> None:

        super().__init__(filterFineData, universeSettings, securityInitializer)

        # Parameter settings:
        self.n_symbols_coarse = n_coarse
        self.n_symbols_fine = n_fine
        self.age = age
        self.recent = recent
        self.vol_lim = vol_lim
        self.min_price = min_price
        self.max_price = max_price
        self.period = period
        self.m_cap_lim = m_cap_lim
        self.markets = markets
        self.c_id = c_id
        self.reverse = from_top
        self.restrict_country = restrict_country
        self.verbose = verbose

        self.usd_vol = {}
        self.last_month = -1

    def SelectCoarse(self,
                     algorithm: QCAlgorithm,
                     coarse: CoarseFundamental) -> FineFundamental:

        '''
        Coarse unviverse selection method.

        Args:
            algorithm (QCAlgorithm): Current algorithm instance.
            coarse (CoarseFundamental): QC Coarse universe object.

        Returns:
            fine (FineFundamental): QC fine universe object.
        '''

        if self.period == 'Month':
            if algorithm.Time.month == self.last_month:
                return Universe.Unchanged
        elif self.period != 'Day':
            algoithm.Log('Period not valid.. Choose "Day" or "Month". Defaulting to "Month".')

        c = coarse
        usd_vol = sorted([x for x in c if
                          x.HasFundamentalData and
                          x.Volume > self.vol_lim and
                          self.max_price > x.Price > self.min_price],
                         key=lambda x: x.DollarVolume,
                         reverse=self.reverse)[:self.n_symbols_coarse]

        self.usd_vol = {x.Symbol: x.DollarVolume for x in usd_vol}

        if len(self.usd_vol) == 0:
            return Universe.Unchanged

        return list(self.usd_vol.keys())

    def SelectFine(self,
                   algorithm: QCAlgorithm,
                   fine: FineFundamental) -> FineFundamental:

        '''
        Coarse unviverse selection method.

        Args:
            algorithm (QCAlgorithm): Current algorithm instance.
            fine (FineFundamental): QC fine universe object.

        Returns:
            new_universe (FineFundamental): QC fine universe object.
        '''

        f = fine
        a = algorithm
        sort_sector = sorted([x for x in f if
                              x.MarketCap > self.m_cap_lim],
                             key=lambda x: x.CompanyReference.IndustryTemplateCode)

        count = len(sort_sector)

        if count == 0:
            return Universe.Unchanged

        if self.recent != -1:
            sort_sector = [x for x in sort_sector if
                           (a.Time -
                            x.SecurityReference.IPODate).days < self.recent]
        else:
            sort_sector = [x for x in sort_sector if
                           (a.Time -
                            x.SecurityReference.IPODate).days > self.age]

        if self.restrict_country:
            sort_sector = [x for x in sort_sector if
                           x.CompanyReference.CountryId == self.c_id and
                           x.CompanyReference.PrimaryExchangeID in self.markets]

        self.last_month = a.Time.month

        percent = self.n_symbols_fine / count
        sort_usd_vol = []

        for c, g in groupby(sort_sector,
                            lambda x: x.CompanyReference.IndustryTemplateCode):
            y = sorted(g, key=lambda x: self.usd_vol[x.Symbol],
                       reverse=self.reverse)
            c = ceil(len(y) * percent)
            sort_usd_vol.extend(y[:c])

        sort_usd_vol = sorted(sort_usd_vol,
                              key=lambda x: self.usd_vol[x.Symbol],
                              reverse=self.reverse)
        new_universe = [x.Symbol for x in sort_usd_vol[:self.n_symbols_fine]]

        if self.verbose:
            for s in new_universe:
                algorithm.Log('Adding: '+str(s.Symbol))
            algorithm.Log('Universe members: ' + str(len(new_universe)))

        return new_universe
