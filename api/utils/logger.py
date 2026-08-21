import logging
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get()
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | trace_id=%(trace_id)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("smart_dunning")
logger.addFilter(TraceFilter())