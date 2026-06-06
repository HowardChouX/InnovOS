from .users import init_users
from .tasks import init_tasks
from .analyses import init_analyses
from .solutions import init_solutions
from .workflows import init_workflows
from .patents import init_patents
from .evaluations import init_evaluations
from .feedbacks import init_feedbacks
from .audit_logs import init_audit_logs
from .api_keys import init_api_keys


def init_all_tables(conn):
    init_users(conn)
    init_tasks(conn)
    init_analyses(conn)
    init_solutions(conn)
    init_workflows(conn)
    init_patents(conn)
    init_evaluations(conn)
    init_feedbacks(conn)
    init_audit_logs(conn)
    init_api_keys(conn)
    conn.commit()
