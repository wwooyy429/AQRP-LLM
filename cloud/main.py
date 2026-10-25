from AlgorithmImports import *
from research_config import CONFIGURATION
from qresearch.runtime import readiness


class GenericResearchHost(QCAlgorithm):

    def initialize(self) -> None:
        self.set_time_zone(CONFIGURATION["research"]["timezone"])
        self._readiness = readiness(CONFIGURATION)
        # This project hosts the Research library. It is never a portfolio
        # result; a frozen trading algorithm must bind the same library first.
        self.quit("Research infrastructure loaded. Trading adapter is not registered; use research.ipynb.")
