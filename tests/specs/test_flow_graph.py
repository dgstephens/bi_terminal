"""Statically checks that every action/choice value a spec builder can emit
is a real edge in core.flow.FLOW_GRAPH — catches "dangling edge" bugs (like
the confirmed real shared_bin_items_view -> item_detail bins=[] bug in
bi_python) at test time instead of by manual audit.

Deliberately does NOT check FormSpec-producing builders (specs/forms.py) —
forms return a result dict on submit, not a dispatched action tag, so they
don't participate in this specific graph-edge model. See core/flow.py's
FLOW_GRAPH docstring.
"""

from bi_terminal.core.flow import FLOW_GRAPH
from bi_terminal.specs import menus
from bi_terminal.specs.fields import ActionMenuSpec, ListPickerSpec

BIN = {
    "id": "b1",
    "binName": "Shelf A",
    "description": "Art supplies",
    "location": "Workshop",
    "type": "physical",
    "public": False,
    "items": [],
    "image": "https://example.com/bin.png",  # truthy, so view_image is included
    "sharedWith": [],
}
ITEM = {
    "id": "i1",
    "item": "Widget",
    "binId": "b1",
    "prevBin": "b0",  # truthy, so move_prev is included
    "images": ["https://example.com/item.png"],  # truthy, so view_image is included
    "image": "",
    "description": "A widget",
    "type": "part",
    "quantity": "3",
    "manufacturer": "Acme",
    "serialNumber": "SN123",
}
USER = {
    "name": "Daniel",
    "email": "d@example.com",
    "about": "",
    "showOnUsersPage": False,
    "image": "https://example.com/user.png",
}

# builder -> (flow-graph node name, args)
MENU_SPECS = {
    "login": (menus.login_choice_spec, ()),
    "main": (menus.main_menu_spec, ("5",)),
    "bins": (menus.my_bins_spec, ([BIN],)),
    "bin_detail": (menus.bin_detail_menu_spec, (BIN,)),
    "items_in_bin": (menus.items_in_bin_spec, ([ITEM], BIN)),
    "all_items": (menus.all_items_spec, ([ITEM],)),
    "item_detail": (menus.item_detail_menu_spec, (ITEM,)),
    "search": (menus.search_results_spec, ([ITEM, dict(ITEM, id="i2")], "widget")),
    "shared_bins": (menus.shared_bins_spec, ([BIN],)),
    "shared_bin_items": (menus.shared_bin_items_spec, ([ITEM], BIN)),
    "profile": (menus.profile_menu_spec, (USER,)),
    "settings": (menus.settings_menu_spec, ("none",)),
}


def _action_values(spec):
    if isinstance(spec, ActionMenuSpec):
        return [item.value for item in spec.items if not item.separator]
    if isinstance(spec, ListPickerSpec):
        tags = []
        for choice in spec.choices:
            v = choice.value
            tags.append(v[0] if isinstance(v, tuple) else v)
        return tags
    raise TypeError(f"Unhandled spec type for flow-graph checking: {type(spec)}")


def test_every_menu_spec_builder_has_a_flow_graph_node():
    missing = [name for name in MENU_SPECS if name not in FLOW_GRAPH]
    assert not missing, f"No FLOW_GRAPH entry for: {missing}"


def test_every_emitted_action_value_is_a_real_flow_graph_edge():
    problems = []
    for node_name, (builder, args) in MENU_SPECS.items():
        spec = builder(*args)
        emitted = set(_action_values(spec))
        allowed = set(FLOW_GRAPH[node_name].keys())
        dangling = emitted - allowed
        if dangling:
            problems.append(f"{builder.__name__} ({node_name}): dangling values {dangling}")
    assert not problems, "\n".join(problems)


def test_flow_graph_next_node_targets_all_exist_or_are_terminal():
    all_nodes = set(FLOW_GRAPH.keys())
    problems = []
    for node_name, edges in FLOW_GRAPH.items():
        for action, target in edges.items():
            if target is not None and target not in all_nodes:
                problems.append(f"{node_name}.{action} -> unknown node {target!r}")
    assert not problems, "\n".join(problems)
