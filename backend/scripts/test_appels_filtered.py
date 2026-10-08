import ast
import inspect
import app.api.tenders as t


def test_appels_filtered_for_client_complets():
    params = list(inspect.signature(t._filtered_for_client).parameters)
    for c in [n for n in ast.walk(ast.parse(inspect.getsource(t)))
              if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_filtered_for_client"]:
        given = params[:len(c.args)] + [k.arg for k in c.keywords]
        assert len(given) == len(set(given)), "argument donné deux fois"
        assert set(given) == set(params), set(params) - set(given)
