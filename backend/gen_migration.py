# gen_migration.py
from alembic.autogenerate import render_python_code
from alembic.operations import ops
from app.core.database import Base

import app.models.user
import app.models.sotradies
import app.models.sent_log
import app.models.audit_log
import app.models.known_buyer
import app.models.system_action_log
import app.models.configuration

tables = Base.metadata.sorted_tables
print(f"Tables : {[t.name for t in tables]}\n")

up = ops.UpgradeOps(ops=[ops.CreateTableOp.from_table(t) for t in tables])
down = ops.DowngradeOps(ops=[ops.DropTableOp.from_table(t) for t in reversed(list(tables))])

print("### UPGRADE ###")
print(render_python_code(up))
print("\n### DOWNGRADE ###")
print(render_python_code(down))