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
from .notifications import init_notifications
from .knowledge import init_knowledge_docs, init_knowledge_items
from .knowledge_bases import init_knowledge_bases
from .problem_modelings import init_problem_modelings
from .model_providers import init_model_providers


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
    init_notifications(conn)
    init_knowledge_docs(conn)
    init_knowledge_items(conn)
    init_knowledge_bases(conn)
    init_problem_modelings(conn)
    init_model_providers(conn)
    conn.commit()
