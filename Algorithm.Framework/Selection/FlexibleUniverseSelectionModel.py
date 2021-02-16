# Original File:
# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect
# Corporation.
#
# Changes: 
# The universe selection model is extended to take optional arguments:
#   - number: number of stocks to be returned.
#   - age: days since IPO
#   - restrict country: Selector to restrict stocks to US companies
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
AddReference("System")
AddReference("QuantConnect.Common")
AddReference("QuantConnect.Algorithm.Framework")


class FlexibleUniverseSelectionModel(FundamentalUniverseSelectionModel):

    def __init__(self, n=100, age=1250, restrict_country=True,
                 filterFineData=True, universeSettings=None,
                 securityInitializer=None):
        super().__init__(filterFineData, universeSettings, securityInitializer)
        self.n_symbols_coarse = 1000
        self.restrict_country = restrict_country
        self.age = age
        self.n_symbols_fine = n
        self.usd_vol = {}
        self.last_month = -1

    def SelectCoarse(self, algorithm, coarse):
        if algorithm.Time.month == self.last_month:
            return Universe.Unchanged

        c = coarse
        usd_vol = sorted([x for x in c if
                          x.HasFundamentalData and
                          x.Volume > 0 and
                          x.Price > 0],
                         key=lambda x: x.DollarVolume,
                         reverse=True)[:self.n_symbols_coarse]

        self.usd_vol = {x.Symbol: x.DollarVolume for x in usd_vol}

        if len(self.usd_vol) == 0:
            return Universe.Unchanged

        return list(self.usd_vol.keys())

    def SelectFine(self, algorithm, fine):
        f = fine
        a = algorithm
        sort_sector = sorted([x for x in f if
                             (a.Time -
                              x.SecurityReference.IPODate).days > self.age and
                              x.MarketCap > 5e8],
                             key=lambda x: x.CompanyReference.IndustryTemplateCode)

        markets = ["NYS", "NAS"]
        c_id = 'USA'
        if self.restrict_country:
            sort_sector = [x for x in sort_sector if
                           x.CompanyReference.CountryId == c_id and
                           x.CompanyReference.PrimaryExchangeID in markets]

        count = len(sort_sector)

        if count == 0:
            return Universe.Unchanged

        self.last_month = a.Time.month

        percent = self.n_symbols_fine / count
        sort_usd_vol = []

        for code, g in groupby(sort_sector,
                               lambda x: x.CompanyReference.IndustryTemplateCode):
            y = sorted(g, key=lambda x: self.usd_vol[x.Symbol],
                       reverse=True)
            c = ceil(len(y) * percent)
            sort_usd_vol.extend(y[:c])

        sort_usd_vol = sorted(sort_usd_vol,
                              key=lambda x: self.usd_vol[x.Symbol],
                              reverse=True)

        return [x.Symbol for x in sort_usd_vol[:self.n_symbols_fine]]
