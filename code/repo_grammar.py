
##repo_grammar.py composes the main aspects of the grammatic approach

'''
The following code is a simplified, non-executable representation of the grammar functionaliites. Many engineering details, optimizations, and auxiliary components have been omitted for clarity. Only the core process is shown.
'''


###########
# GRAMAMR #
###########

GRAMMAR = {
    "WORKFLOW": [
        ["NODE"],
        ["NODE", "->", "WORKFLOW"],
        ["WORKFLOW", "->", "NODE"],
        ["WORKFLOW", "->", "WORKFLOW"],
        ["NODE", "->", "NODE"]
    ],
    "NODE": [
        ["AGENT"],
        ["COMPLEX_NODE"],
    ],
    "COMPLEX_NODE": [
        ["SIMPLE_CONDITIONAL"],
    ],
    "AGENT": [ 
        ["CODER_DIRECT_LLM"],
        ["CODER_CONCISE"], ["CODER_DETAILED"], ["CODER_OPTIMIZED"], ["CODER_EDUCATIONAL"], ["CODER_ROBUST"],
        ["REVIEWER_QUICK"], ["REVIEWER_THOROUGH"],["REVIEWER_SECURITY"],["REVIEWER_PERFORMANCE"],["REVIEWER_MAINTAINABILITY"],
        ["FIXER_FAST"],["FIXER_COMPREHENSIVE"],["FIXER_MINIMAL"],["FIXER_REFACTOR"],["FIXER_DEFENSIVE"],
        ["ANALYST_ULTRA_BRIEF"], ["ANALYST_PLAIN_STRUCT"], ["ANALYST_BRIEF"],["ANALYST_COMPREHENSIVE"],["ANALYST_ALGORITHMIC"],["ANALYST_RISK"],["ANALYST_ARCHITECTURAL"],
        ["ARCHITECT_MINIMAL"], ["ARCHITECT_MODULAR"], ["ARCHITECT_PERFORMANCE"],["ARCHITECT_ROBUST"],["ARCHITECT_COMPREHENSIVE"]
    
    ],
    "SIMPLE_CONDITIONAL": [
        ["IF", "CONDITION", "THEN", "WORKFLOW", "ELSE", "WORKFLOW"],
        ["IF", "CONDITION", "THEN", "END", "ELSE", "WORKFLOW"],
    ],
    "CONDITION": [
        ["EXECUTION_VALID"],
        ["SYNTAX_VALID"],
        ["ERROR"] 
    ],
}

################
# DEPENDENCIES #
################

AGENT_DEPENDENCIES = {
    "ARCHITECT": {"ANALYST"},
    "CODER": {"ANALYST", "ARCHITECT"},
    "REVIEWER": {"CODER"},
    "FIXER": {"CODER", "REVIEWER"}
}

NODE_DEPENDENCIES = {
    "SIMPLE_CONDITIONAL": {"CODER"}
}

CONDITION_DEPENDENCIES = {
    "EXECUTION_VALID": {"CODER", "SYNTAX_VALID"},
    "SYNTAX_VALID": {"CODER"},
    #"ERROR": {"SYNTAX_VALID"}
}


##########
# OTHERS #
##########

def generate_agent(context):

    seen = context["seen_agents"]
    blocked_types = context["blocked_types"]

    valid_agents = []

    for agent in grammar_agents:

        if agent_type(agent) in blocked_types:
            continue

        if dependencies_satisfied(agent, seen):
            valid_agents.append(agent)

    if not valid_agents:
        return None

    agent = random.choice(valid_agents)

    seen.add(agent)
    blocked_types.add(agent_type(agent))

    return agent

######################
# TREE GENERATION    #
######################

def generate_individual(symbol="WORKFLOW", context=None):
    if context is None:
        context = {
            "seen_agents": set(),
            "blocked_types": set(),
            "seen_conditions": set(),
            "llm_node_count": 0
        }

    if context["llm_node_count"] >= MAX_LLM_NODES:
        return {"value": "END", "children": []}

    # Terminales
    if symbol == "AGENT":
        agent = generate_agent(context)
        if not agent:
            return {"value": "END", "children": []}

        context["llm_node_count"] += 1
        return {"value": "AGENT", "children": [{"value": agent, "children": []}]}

    if symbol == "CONDITION":
        cond = select_available_condition(context)
        if not cond:
            return {"value": "END", "children": []}

        context["llm_node_count"] += 1
        return {"value": "CONDITION", "children": [{"value": cond, "children": []}]}

    if symbol not in GRAMMAR:
        return {"value": symbol, "children": []}

    production = select_production(symbol, context)
    if not production:
        return {"value": "END", "children": []}

    node = {"value": symbol, "children": []}

    for sym in production:
        child = generate_individual(sym, context)

        if child["value"] == "END":
            return {"value": "END", "children": []}

        node["children"].append(child)

    return node

def select_production(symbol, context):
    if symbol == "NODE":
        options = GRAMMAR[symbol]

        return random.choice(options)

    if symbol == "COMPLEX_NODE":
        options = [
            p for p in GRAMMAR[symbol]
            if has_available_conditions(context)
        ]
        return random.choice(options) if options else None

    if symbol == "WORKFLOW":
        options = [
            p for p in GRAMMAR[symbol]
            if is_production_expandable(p, context)
        ]
        return random.choice(options) if options else None

    return random.choice(GRAMMAR[symbol])

def is_production_expandable(production, context):
    for s in production:
        if s == "AGENT" and not has_available_agents(context):
            return False
        if s == "CONDITION" and not has_available_conditions(context):
            return False
        if s == "COMPLEX_NODE" and not has_available_conditions(context):
            return False

    return True

def generate_critical_node(symbol, production, context):
    old_blocked = context["blocked_types"]
    context["blocked_types"] = set()

    children = []

    try:
        for sym in production:
            child = generate_individual(sym, context)

            if child["value"] == "END":
                return {"value": "END", "children": []}

            children.append(child)

        return {"value": symbol, "children": children}

    finally:
        context["blocked_types"] = old_blocked

def is_valid_tree(tree):
    if not grammaticaly_correct(tree):
        return False

    llm_count = count_llm_nodes(tree)
    return MIN_LLM_NODES <= llm_count <= MAX_LLM_NODES

###########
# PRUNING #
###########

def apply_all_pruning(tree):
    if tree is None:
        return None

    tree = prune_incomplete_branches(tree)
    if tree is None:
        return None

    tree = collapse_consecutive_duplicates(tree)
    if tree is None:
        return None

    tree = validate_conditional_structure(tree)
    if tree is None:
        return None

    tree = prune_redundant_code_producers(tree)
    if tree is None:
        return None

    return None

######################
# CREATE INDIVIDUAL #
######################


def create_minimal_individual():
    base = [
        "ANALYST_BRIEF", "CODER_CONCISE", "REVIEWER_QUICK", "FIXER_FAST",
        "CODER_DETAILED", "REVIEWER_THOROUGH", "FIXER_COMPREHENSIVE", "CODER_OPTIMIZED"
    ]

    while len(base) < MIN_LLM_NODES:
        base += [
            "ANALYST_COMPREHENSIVE",
            "CODER_ROBUST",
            "REVIEWER_SECURITY",
            "FIXER_REFACTOR"
        ]

    base = base[:MIN_LLM_NODES]

    def build(agents):
        if not agents:
            return None

        head = {
            "value": "WORKFLOW",
            "children": [
                {
                    "value": "NODE",
                    "children": [
                        {
                            "value": "AGENT",
                            "children": [{"value": agents[0], "children": []}]
                        }
                    ]
                }
            ]
        }

        if len(agents) == 1:
            return head

        return {
            "value": "WORKFLOW",
            "children": [
                head,
                {"value": "->", "children": []},
                build(agents[1:])
            ]
        }

    return build(base)

def create_valid_individual():
    retries = MAX_RETRIES if not driven else max(50, MAX_RETRIES // 2)

    for _ in range(retries):
        tree = generate_individual())

        if tree["value"] == "END":
            continue

        tree = apply_all_pruning(tree)
        if tree is None:
            continue

        if not validate_tree(tree):
            continue

        size = count_llm_nodes(tree)

        if size < MIN_LLM_NODES or size > MAX_LLM_NODES:
            continue

        return tree

    return create_minimal_individual()

####################################################
# CROSSOVER Does not need of extra functionalities #
####################################################

############
# MUTATION #
############

def mutate_point(tree, debug=False):
    mutable = []

    def collect(node, path=None):
        path = path or []

        if node["value"] == "AGENT" and node.get("children"):
            v = node["children"][0]["value"]
            if v != "CODER_DIRECT_LLM":
                mutable.append((node, "AGENT"))

        elif node["value"] == "CONDITION" and node.get("children"):
            mutable.append((node, "CONDITION"))

        for i, c in enumerate(node.get("children", [])):
            collect(c, path + [i])

    collect(tree)

    if not mutable:
        return tree

    node, t = random.choice(mutable)
    current = node["children"][0]["value"]

    if t == "AGENT":
        agent_type = get_agent_type(current)

        options = [
            p[0] for p in GRAMMAR["AGENT"]
            if p[0] != current
            and p[0] != "CODER_DIRECT_LLM"
            and get_agent_type(p[0]) == agent_type
        ]

    else:  # CONDITION
        options = [p[0] for p in GRAMMAR["CONDITION"] if p[0] != current]

    if options:
        node["children"][0]["value"] = random.choice(options)

    return tree

def mutate_subtree(tree, debug=False):
    points = []

    def collect(node, parent=None, idx=None, depth=0):
        if parent and node["value"] in ("WORKFLOW", "NODE"):
            points.append((node, parent, idx, depth))

        for i, c in enumerate(node.get("children", [])):
            collect(c, node, i, depth + 1)

    collect(tree)

    if not points:
        return tree

    node, parent, idx, depth = random.choice(points)

    current = count_llm_nodes(tree)
    available = MAX_LLM_NODES - current + count_llm_nodes(node)

    if available < 1:
        return tree

    new_subtree = create_valid_mutation(
        max_llm_nodes=min(available, 5)
    )

    if new_subtree is None:
        return tree

    parent["children"][idx] = new_subtree
    return tree

def mutate_individual(tree, mutation_rate=0.3, subtree_prob=0.3):
    """
    Muta un individuo con dos estrategias:
    1. Mutación puntual (70%): Cambia un agente por otro del mismo tipo
    2. Mutación de subárbol (30%): Reemplaza un subárbol completo
    """
    if random.random() > mutation_rate:
        return tree

    mutated = copy.deepcopy(tree)

    if random.random() < subtree_prob:
        mutated = mutate_subtree(mutated, debug)
    else:
        mutated = mutate_point(mutated, debug)

    return apply_all_pruning(mutated)


































