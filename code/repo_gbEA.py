##repo_gbEA.py composes the main functionalities of the evolutionary algorithm

'''
The following code is a simplified, non-executable representation of the algorithm. Many engineering details, optimizations, and auxiliary components have been omitted for clarity. Only the core evolutionary process is shown.
'''

#########
# UTILS #
##########

def compose_psb2_problem_prompt(problem_entry, max_train=None):
    description = problem_entry.get('problem', '').strip()
    edge_examples = problem_entry.get('input_output_edge', [])
    random_examples = problem_entry.get('input_output_random', [])

    # Keep task prompt compact and consistent: first 2 edge + first 2 random examples.
    edge_samples = edge_examples[:2]
    random_samples = random_examples[:2]
    train_samples = edge_samples + random_samples

    prompt_lines = [description, "", "Training examples:"]
    for ex in train_samples:
        inp, outp = _format_psb2_example(ex)
        prompt_lines.append(f"Input: {inp}")
        prompt_lines.append(f"Output: {outp}")
        prompt_lines.append("")

    prompt_lines.append("Use the examples above to implement a Python program that reads input values (one value per line or formatted as in the example) and prints the expected output.")
    prompt_lines.append("")
    prompt_lines.append("OUTPUT CONTRACT (STRICT):")
    prompt_lines.append("- Print exactly one final line and it must be valid JSON.")
    prompt_lines.append("- Do not print explanations, examples, logs, or extra lines.")
    prompt_lines.append("- Use print(json.dumps(result, ensure_ascii=False)).")
    prompt_lines.append("- In if __name__ == '__main__': read stdin and parse inputs exactly as shown by examples.")
    prompt_lines.append("- If expected outputs contain keys output1/output2, your JSON must include exactly those keys.")
    prompt_lines.append("- If expected output is a scalar/string, return JSON object with key output1 and that value.")
    prompt_lines.append("")
    prompt_lines.append("Example template:")
    prompt_lines.append("import sys, json")
    prompt_lines.append("def solve(...):")
    prompt_lines.append("    ...")
    prompt_lines.append("if __name__ == '__main__':")
    prompt_lines.append("    data = sys.stdin.read().strip().splitlines()")
    prompt_lines.append("    # parse data from lines as needed")
    prompt_lines.append("    result = solve(parsed_input)")
    prompt_lines.append("    print(json.dumps(result, ensure_ascii=False))")
    return "\n".join(prompt_lines)



#####################
# GENETIC ALGORITHM #
#####################

class GeneticAlgorithm:
    def __init__(self, pop_size=10, generations=10, elite_size=2, seed=None):
        '''
        Simplified version of the gbEA
        '''

        self.seed = seed

        self.pop_size = pop_size
        self.generations = generations
        self.elite_size = elite_size
        self.fitness_function = None # Depending on MATH or PSB2

        self.model_family = model_family
        self.gpu = None # Depending on Lite, Heavy, Very Heavy or API models


        self.converged = False

    ##########
    # OTHERS #
    ##########

    def tournament_selection(self, tournament_size=3):
        tournament_ids = random.sample(list(self.population.keys()), tournament_size)

        def fitness_key(idx):
            m = self.population[idx]['metrics']
            return (
                m['correct_answers'],
                m['execution_valids'],
                m['syntax_valids'],
                -m['creating_times'],  # menor es mejor
                -m['program_times']    # menor es mejor
            )
        
        winner_id = max(tournament_ids, key=fitness_key)
        return winner_id

    def _evaluate_single_problem(self, workflow_module, ind_id, problem_entry, codes_folder, max_solve_time):
        problem_id = str(problem_entry["id"])
        expected = problem_entry["answer"]
        problem_level = int(problem_entry.get("level", 1))
        diagram_hash = self._diagram_signature(self.population[ind_id]["diagram"])
        individual_cache = self.fitness_cache.setdefault(diagram_hash, {})

        cached_report = individual_cache.get(problem_id)
        output_file = f"{codes_folder}/problem_{problem_id}.py"
        prompt_file = f"{codes_folder}/problem_{problem_id}_prompt.txt"

        if cached_report is not None:
            if cached_report.get("generated_code") and not os.path.exists(output_file):
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(cached_report["generated_code"])
            if not os.path.exists(prompt_file):
                with open(prompt_file, "w", encoding="utf-8") as pf:
                    pf.write(problem_entry.get("problem", ""))
            replayed = copy.deepcopy(cached_report)
            replayed["cached"] = True
            return replayed

        problem_report = {
            "problem_id": problem_id,
            "problem_level": problem_level,
            "path": output_file,
            "syntax_valid": False,
            "execution_valid": False,
            "all_passed": False,
            "error": None,
            "expected": expected,
            "result": None,
            "numbers_found": [],
            "execution_time": 0.0,
            "cached": False,
        }

        start_individual = time.time()
        try:
            compile_result = subprocess.run(
                ["python", "-m", "py_compile", output_file],
                capture_output=True,
                timeout=5,
            )
            if compile_result.returncode != 0:
                problem_report["error"] = "parse_error"
                problem_report["creating_time"] = time.time() - start_individual
                individual_cache[problem_id] = copy.deepcopy(problem_report)
                return problem_report
            problem_report["syntax_valid"] = True
        except Exception:
            problem_report["error"] = "parse_error"
            problem_report["creating_time"] = time.time() - start_individual
            individual_cache[problem_id] = copy.deepcopy(problem_report)
            return problem_report

        start_exec = time.time()
        try:
            run = subprocess.run(
                ["python", output_file],
                capture_output=True,
                text=True,
                timeout=max_solve_time,
            )
        except subprocess.TimeoutExpired:
            problem_report["error"] = "timeout"
            problem_report["execution_time"] = max_solve_time
            problem_report["creating_time"] = time.time() - start_individual
            individual_cache[problem_id] = copy.deepcopy(problem_report)
            return problem_report
        except Exception:
            problem_report["error"] = "runtime_error"
            problem_report["execution_time"] = time.time() - start_exec
            problem_report["creating_time"] = time.time() - start_individual
            individual_cache[problem_id] = copy.deepcopy(problem_report)
            return problem_report

        problem_report["execution_time"] = time.time() - start_exec
        problem_report["creating_time"] = time.time() - start_individual

        if run.returncode != 0:
            problem_report["error"] = run.stderr.strip() or "runtime_error"
            individual_cache[problem_id] = copy.deepcopy(problem_report)
            return problem_report

        problem_report["execution_valid"] = True
        output = run.stdout.strip().splitlines()
        if not output:
            individual_cache[problem_id] = copy.deepcopy(problem_report)
            return problem_report

        result = output[-1].strip()
        problem_report["result"] = result
        numbers_found = re.findall(r'-?\d+(?:\.\d+)?', result)
        problem_report["numbers_found"] = numbers_found

        matched = False
        for num_str in numbers_found:
            try:
                num_float = float(num_str)
                if abs(num_float - float(expected)) < 1e-3:
                    matched = True
                    problem_report["all_passed"] = True
                    break
            except ValueError:
                continue

        if not matched:
            problem_report["error"] = "value_mismatch"

        individual_cache[problem_id] = copy.deepcopy(problem_report)
        return problem_report

    def rank_population(self):
        '''Rank population based on metrics:
        the ranking is done by taking each metric priority and sorting it for each.
        Example, correct_answers > execution_valids > syntax_valids > creating_times (lower is better) > program_times (lower is better)
        ind_1 --> [5, 8, 10, 30.5, 12.3]
        ind_2 --> [6, 7, 9, 25.0, 10.0]
        ind_3 --> [5, 9, 10, 20.0, 15.0]
        Ranking: ind_2, ind_3, ind_1
        Because, ind_2 has more correct_answers, then ind_3 has same correct_answers as ind_1 but more execution_valids, etc.
        '''
        ranking = sorted(
            self.population.items(),
            key=lambda x: (
                x[1]["metrics"]["correct_answers"],
                x[1]["metrics"]["execution_valids"],
                x[1]["metrics"]["syntax_valids"],
                -x[1]["metrics"]["creating_times"], # Lower time is better
                -x[1]["metrics"]["program_times"] # Lower time is better
            ),
            reverse=True
        )
        ranked_ids = [item[0] for item in ranking]
        return ranked_ids

    def create_population(self):
        population = {
            f'ind_{i}': {'diagram': create_valid_individual(debug=True), 'metrics': {}}
            for i in range(self.pop_size)
        }

        self.id_last = self.pop_size - 1
        self.population = population

        return population#Not necessary

    def evaluate_population(self, gen):

        manifest = self._build_curriculum_manifest(gen) \
            if self.use_curriculum else None

        for ind_id in self.population:

            metrics = self.fitness_function(
                ind_id,
                self.generation_folder,
                curriculum_manifest=manifest, # In case of Expanded gbEA
            )

            self.population[ind_id]["metrics"] = metrics

        return self.population
        
    def has_converged(self, percentage=0.7, tree_similarity_threshold=0.1):

        if len(self.population) < 2:
            return False

        fitnesses = [
            (
                ind["metrics"].get("correct_answers", 0),
                ind["metrics"].get("syntax_valids", 0),
                ind["metrics"].get("execution_valids", 0),
            )
            for ind in self.population.values()
        ]

        best_fitness = max(fitnesses)

        fitness_similarity = (
            sum(1 for f in fitnesses if f == best_fitness)
            / len(fitnesses)
        )

        fitness_convergence = fitness_similarity >= percentage

        terminals = [
            set(get_terminals(ind["diagram"]))
            for ind in self.population.values()
        ]

        similarities = []

        for i in range(len(terminals)):
            for j in range(i + 1, len(terminals)):
                similarities.append(
                    jaccard_similarity(
                        terminals[i],
                        terminals[j]
                    )
                )

        avg_similarity = (
            sum(similarities) / len(similarities)
            if similarities else 0.0
        )

        tree_convergence = (
            avg_similarity >= (1 - tree_similarity_threshold)
        )

        return fitness_convergence and tree_convergence

    #####################
    # FITNESS FUNCTIONS #
    #####################

    def fitness_function_MATH(self, ind_id):

        # Cargar benchmark
        problems_db = pd.read_csv(self.problems_db_file)

        selected_problems = []
        for _, row in problems_db.iterrows():
            selected_problems.append({
                "id": str(row["id"]),
                "problem": row["problem"],
                "answer": row["answer"],
            })

        # Compilar workflow
        CrewaiCompiler(
            ind_id,
            self.population[ind_id]["diagram"],
            codes_folder,
        ).compile(workflow_file)

        # Cargar workflow generado
        workflow_module = load_module_from_path(workflow_file)

        problem_results = []

        # Evaluar benchmark
        for problem in selected_problems:

            report = evaluate_problem(
                workflow_module,
                problem,
            )

            problem_results.append(report)

        # Agregar métricas
        correct_answers = sum(
            1 for p in problem_results
            if p["all_passed"]
        )

        execution_valids = sum(
            1 for p in problem_results
            if p["execution_valid"]
        )

        syntax_valids = sum(
            1 for p in problem_results
            if p["syntax_valid"]
        )

        return {
            "correct_answers": correct_answers,
            "execution_valids": execution_valids,
            "syntax_valids": syntax_valids,
            "problem_results": problem_results,
        }

    def fitness_function_PSB2(self, ind_id):

        # Cargar benchmark
        problems = load_psb2_dataset()

        # Compilar workflow
        CrewaiCompiler(
            ind_id,
            self.population[ind_id]["diagram"],
            codes_folder,
        ).compile(workflow_file)

        workflow_module = load_module_from_path(workflow_file)

        test_suite = []

        # Generar programa para cada problema
        for problem in problems:

            code = workflow_module.kickoff(
                ind_id=ind_id,
                problem=problem,
            )

            save_program(problem["id"], code)

            test_suite.append(
                build_test_suite(problem)
            )

        # Ejecutar benchmark
        correct_answers, execution_valids, syntax_valids, test_results = (
            program_tester_io(
                codes_folder,
                test_suite,
            )
        )

        return {
            "correct_answers": correct_answers,
            "execution_valids": execution_valids,
            "syntax_valids": syntax_valids,
            "problem_results": test_results,
        }


    #############
    # CROSSOVER #
    #############

    def crossover(self, parent1_id, parent2_id, crossover_rate=0.7, restricted=True, max_size=15):

        if random.random() > crossover_rate:
            return parent1_id, parent2_id

        try:
            child1 = copy.deepcopy(self.population[parent1_id]['diagram'])
            child2 = copy.deepcopy(self.population[parent2_id]['diagram'])

            if not restricted:
                _, path1 = get_random_subtree(child1)
                _, path2 = get_random_subtree(child2)
            else:
                same_type_pairs = get_same_type_subtrees(child1, child2)

                if not same_type_pairs:
                    return parent1_id, parent2_id

                path1, path2 = random.choice(same_type_pairs)

            if not (path1 and path2):
                return parent1_id, parent2_id

            subtree1 = child1
            for step in path1:
                subtree1 = subtree1["children"][step]

            subtree2 = child2
            for step in path2:
                subtree2 = subtree2["children"][step]

            temp_child1 = copy.deepcopy(child1)
            temp_child2 = copy.deepcopy(child2)

            set_subtree(temp_child1, path1, copy.deepcopy(subtree2))
            set_subtree(temp_child2, path2, copy.deepcopy(subtree1))

            temp_child1 = apply_all_pruning(temp_child1)
            temp_child2 = apply_all_pruning(temp_child2)

            if temp_child1 is None or not is_valid_tree(temp_child1):
                temp_child1 = copy.deepcopy(self.population[parent1_id]['diagram'])

            if temp_child2 is None or not is_valid_tree(temp_child2):
                temp_child2 = copy.deepcopy(self.population[parent2_id]['diagram'])

            valid_child1 = count_llm_nodes(temp_child1) <= max_size
            valid_child2 = count_llm_nodes(temp_child2) <= max_size

            if not valid_child1 and not valid_child2:
                return parent1_id, parent2_id

            children = {}

            if valid_child1:
                self.id_last += 1
                child1_id = f"{self.id_last_prefix}ind_{self.id_last}"
                children[child1_id] = {
                    "diagram": temp_child1,
                    "metrics": {}
                }
            else:
                child1_id = parent1_id

            if valid_child2:
                self.id_last += 1
                child2_id = f"{self.id_last_prefix}ind_{self.id_last}"
                children[child2_id] = {
                    "diagram": temp_child2,
                    "metrics": {}
                }
            else:
                child2_id = parent2_id

            if children:
                self.population.update(children)
                self.evaluate_population(gen, update_curriculum=False)

                save_crossover_with_html(
                    self.population,
                    parent1_id,
                    parent2_id,
                    child1_id,
                    child2_id,
                    generation=gen,
                    crossover_path1=path1,
                    crossover_path2=path2,
                    output_dir=self.generation_folder
                )

            return child1_id, child2_id

        except Exception as e:
            print(f"Crossover error: {e}")
            return parent1_id, parent2_id


    ############
    # MUTATION #
    ############

    def mutation(self, ind_id, mutation_rate=0.3, max_llm_nodes=15):

        individual = self.population[ind_id]

        mutated = mutate_individual(
            individual["diagram"],
            mutation_rate=mutation_rate,
            subtree_mutation_prob=0.3,
            debug=True
        )

        if mutated == individual["diagram"]:
            return ind_id

        if not is_valid_tree(mutated):
            return ind_id

        if count_llm_nodes(mutated) > max_llm_nodes:
            return ind_id

        self.id_last += 1
        mutated_id = f"{self.id_last_prefix}ind_{self.id_last}"

        self.population[mutated_id] = {
            "diagram": mutated,
            "metrics": {}
        }

        self.evaluate_population(gen, update_curriculum=False)

        save_mutation_with_html(
            self.population,
            ind_id,
            mutated_id,
            generation=gen,
            changed_path=None,
            output_dir=self.generation_folder
        )

        return mutated_id

    def run(self):

    self.population = self.create_population()

    for gen in range(self.generations):

        self.evaluate_population(gen)

        ranking = self.rank_population()
        best = ranking[0]

        if self.has_converged():
            break

        offspring = {}

        while len(offspring) < (self.pop_size - self.elite_size):

            if random.random() < 0.7:
                p1 = self.tournament_selection()
                p2 = self.tournament_selection()

                c1, c2 = self.crossover(p1, p2)

                offspring[c1] = self.population[c1]
                offspring[c2] = self.population[c2]

            else:
                parent = self.tournament_selection()

                child = self.mutation(parent)

                offspring[child] = self.population[child]

        self.population.update(offspring)

        ranking = self.rank_population()

        self.population = {
            ind_id: copy.deepcopy(self.population[ind_id])
            for ind_id in ranking[:self.pop_size]
        }

    self.evaluate_population(self.generations)

    ranking = self.rank_population()

    return {
        "best_individual": ranking[0],
        "best_fitness": self.population[ranking[0]]["metrics"]
    }