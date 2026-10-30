from AlgorithmImports import *
from research_config import CONFIGURATION
from qresearch.runtime import readiness
from pathlib import Path
import base64
import json


class GenericResearchHost(QCAlgorithm):

    def initialize(self) -> None:
        self.set_time_zone(CONFIGURATION["research"]["timezone"])
        self._readiness = readiness(CONFIGURATION)
        self._engineering_state = None
        path = Path(__file__).resolve().parent / "_engineering_task_input.py"
        if path.is_file():
            # This generated file is inert job data, not an executable module.
            # Its bytes are separately pinned to the precharged submission.
            from qresearch.engineering_data import load_task_input, initialize_receiver
            payload = load_task_input(path)
            initialize_receiver(self, payload)
            return
        # This project hosts the Research library. It is never a portfolio
        # result; a frozen trading algorithm must bind the same library first.
        self.quit("Research infrastructure loaded. Trading adapter is not registered; use research.ipynb.")

    def on_data(self, data: Slice) -> None:
        if self._engineering_state is not None:
            from qresearch.engineering_data import receive_slice
            receive_slice(self, data)

    def on_order_event(self, order_event: OrderEvent) -> None:
        if self._engineering_state is not None:
            self._engineering_state["order_events"] += 1
            raise RuntimeError("Orders are forbidden in the engineering receiver")

    def on_end_of_algorithm(self) -> None:
        if self._engineering_state is None:
            return
        from qresearch.engineering_data import finish_receiver
        result = finish_receiver(self)
        # Small log chunks contain counts/hashes only. They permit a completed
        # backtest report read without another Research execution or row export.
        encoded = base64.b64encode(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).decode()
        chunks = [encoded[index:index + 500] for index in range(0, len(encoded), 500)]
        attempt = self._engineering_state["payload"]["identity"]["attempt_id"]
        for index, chunk in enumerate(chunks):
            self.log("AQRP_ENGINEERING " + attempt + " " + str(index) + "/" + str(len(chunks)) + " " + chunk)
